"""Private R15 raw direct-cold composition; no default-source changes.

Direct mode is source-ready/native-unqualified. The ungenerated PCIe branch
fails explicitly rather than producing a black-box shell fit.
"""
import copy
import hashlib
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ACK='rtl/kernel/genefer_stream27_r15_host_image_ack_v1.sv'
GUARD='rtl/kernel/genefer_stream27_r15_direct_write_guard_v1.sv'
LOADER='rtl/kernel/genefer_stream27_r15_raw_loader_v1.sv'

PORTS=''' input logic dc_link_drained,dc_begin,dc_cancel,dc_commit,dc_word_valid,dc_context,
 input logic [55:0] dc_owner,
 input logic [31:0] dc_session,dc_lease,dc_current_session,dc_count,dc_mask,
 input logic [2:0] dc_mode,input logic [255:0] dc_profile,
 input logic [AW+1:0] dc_index,input logic [31:0] dc_word,
 input logic dc_transport_empty,
 output logic dc_word_ready,dc_active,dc_error,
 output logic [1:0] dc_loaded,dc_idle,
 output logic [31:0] dc_next_epoch,dc_next_lease,
 output logic [15:0] dc_job_generation,
 output logic [AW+2:0] dc_applied,
'''


def expose_host_ports(bundle):
    """Private root clone exposing actual host arbitration/core-issued lease state.

    Integration helper only, NOT a DIRECT_COLD-ready returned top. Its caller
    must install the transaction guard, prevent legacy unguarded load/START,
    and wire invalidate only to accepted idle-context BEGIN/cancel/reset.
    No arithmetic/field source is touched and each edit has exact reversal.
    """
    b=copy.deepcopy(bundle)
    oldtop=b['top'];newtop=oldtop+'_r15_host_ports_v1'
    key=oldtop+'.sv'
    if key not in b['files']:raise ValueError('R15_HOST_ROOT_FILE')
    original=b['files'][key];text=original;edits=[]
    def edit(before,after):
        nonlocal text
        if text.count(before)!=1:raise ValueError('R15_HOST_ANCHOR '+before[:70])
        text=text.replace(before,after,1);edits.append((before,after))
    edit('module '+oldtop+' #','module '+newtop+' #')
    edit(' input logic clk,rst_n,host_context,load_we,read_en,',
         ' input logic [1:0] r15_invalidate,\n'
         ' output logic [1:0] r15_idle,\n'
         ' output logic [31:0] r15_next_epoch,\n'
         ' output logic [15:0] r15_job_generation,\n'
         ' output logic r15_write_ready,r15_write_ack,\n'
         ' input logic clk,rst_n,host_context,load_we,read_en,')
    edit(' wire [1:0] owner_enabled=jobs;',
         ' wire [1:0] owner_enabled=jobs;\n'
         ' assign r15_idle={phase[1]==IDLE,phase[0]==IDLE} & {2{!safety_error}};\n'
         ' assign r15_next_epoch={next_epoch[1],next_epoch[0]};\n'
         ' assign r15_job_generation={job_generation[1],job_generation[0]};')
    edit(' genefer_stream27_host_image_rowwrite_v1 #(',
         ' genefer_stream27_r15_host_image_ack_v1 #(')
    edit('.row_write_ack(shadow_capture_ack),.rejected(shadow_rejected));',
         '.row_write_ack(shadow_capture_ack),.rejected(shadow_rejected),\n'
         '  .host_write_ready(r15_write_ready),.host_write_ack(r15_write_ack));')
    edit('   if(load_we && phase[host_context]==IDLE)published[host_context]<=0;',
         '   if(load_we && phase[host_context]==IDLE)published[host_context]<=0;\n'
         '   for(int c=0;c<2;c++)if(r15_invalidate[c])begin\n'
         '    if(phase[c]!=IDLE || start_contexts[c])local_error<=1;\n'
         '    else published[c]<=0;\n'
         '   end')
    check=text
    for before,after in reversed(edits):
        if check.count(after)!=1:raise ValueError('R15_HOST_REVERSE')
        check=check.replace(after,before,1)
    if check!=original:raise ValueError('R15_HOST_LITERAL_REVERSAL')
    b['files'][newtop+'.sv']=text
    leaf=Path(ACK).name
    b['files'][leaf]=(ROOT/ACK).read_text()
    b['rtl_sources'] += [leaf,newtop+'.sv']
    b['top']=newtop
    b['generated_sha256']={p:hashlib.sha256(t.encode()).hexdigest() for p,t in b['files'].items()}
    for dep in ('reference/stream27_r15_direct_cold_bind.py',ACK):
        if dep not in b['source_dependencies']:b['source_dependencies'].append(dep)
        b['source_sha256'][dep]=hashlib.sha256((ROOT/dep).read_bytes()).hexdigest()
    b['r15_host_port_instrumentation']={'status':'SOURCE_ONLY_NOT_DIRECT_READY',
        'parent_top':oldtop,'parent_root_sha256':hashlib.sha256(original.encode()).hexdigest(),
        'edits':edits,'literal_reversal':True,
        'scope':'Six root/ACK observations and idle-only publication invalidation; no field/arithmetic edits.'}
    return b


def bind(bundle, *, direct_cold=0, pcie_shell=0):
    if type(direct_cold) is not int or direct_cold not in (0, 1):
        raise ValueError('R15_DIRECT_COLD_FLAG')
    if type(pcie_shell) is not int or pcie_shell not in (0, 1):
        raise ValueError('R15_PCIE_SHELL_FLAG')
    if not direct_cold and not pcie_shell:
        return copy.deepcopy(bundle)
    if pcie_shell:
        raise ValueError('R15_PCIE_NOT_READY: exact generated Gen3x8 DMA IP, CDC and real-I/O constraints pending')
    b=expose_host_ports(bundle)
    parent=bundle['top'];private=b['top'];top=parent+'_r15_direct_v1'
    source=bundle['files'][parent+'.sv']
    start=source.index('module '+parent+' #(')
    header=source[start:source.index(');',start)+2]
    params=re.findall(r'\b([A-Z][A-Z0-9_]*)=\d+',header)
    if len(params)!=len(set(params)):raise ValueError('R15_WRAPPER_PARAMETERS')
    header=header.replace('module '+parent+' #(','module '+top+' #(',1)
    header=header.replace('parameter int AW=','parameter int DIRECT_COLD=0,AW=',1)
    header=header.replace(' input logic clk,rst_n,host_context,load_we,read_en,',
                          PORTS+' input logic clk,rst_n,host_context,load_we,read_en,',1)
    connections=','.join('.'+p+'('+p+')' for p in params)
    text=header+'\n generate if(DIRECT_COLD==0)begin: protected_parent\n'
    text+=f' {parent} #({connections}) candidate (.*);\n'
    for name in ('dc_word_ready','dc_active','dc_error','dc_loaded','dc_idle',
                 'dc_next_epoch','dc_next_lease','dc_job_generation','dc_applied'):
        text+=f" assign {name}='0;\n"
    text+=' end else begin: direct_cold\n'
    text+=''' wire core_error,image_write,image_context,image_ready,image_ack;
 wire [AW-1:0] image_address;wire [31:0] image_data;
 wire [1:0] invalidate,admitted_start,saved_batch,saved_feed,saved_double;
 wire [63:0] saved_base,saved_count,saved_mask;
 wire [2*P*32-1:0] saved_c0,saved_c1;
 wire [111:0] saved_owner;
 wire candidate_read_valid;wire [1:0] candidate_canonical_ready;
 wire shadow_context=dc_active ? image_context:host_context;
 wire [AW-1:0] shadow_address=dc_active ? image_address:host_addr;
 assign error=core_error || dc_error;
 assign read_valid=candidate_read_valid && dc_link_drained && !dc_error;
 assign canonical_ready=candidate_canonical_ready & {2{dc_link_drained && !dc_error}};
 genefer_stream27_r15_raw_loader_v1 #(.AW(AW),.P(P)) loader(
  .clk,.rst_n,.link_drained(dc_link_drained),.core_idle(dc_idle),
  .core_generation(dc_job_generation),.core_next_epoch(dc_next_epoch),.core_error,
  .begin_valid(dc_begin),.cancel(dc_cancel),.commit_valid(dc_commit),.word_valid(dc_word_valid),
  .context_in(dc_context),.owner(dc_owner),.session(dc_session),.lease(dc_lease),
  .current_session(dc_current_session),.count(dc_count),.double_mask(dc_mask),.mode(dc_mode),.profile(dc_profile),
  .word_index(dc_index),.word_data(dc_word),.transport_empty(dc_transport_empty),
  .word_ready(dc_word_ready),.active(dc_active),.error(dc_error),.next_lease(dc_next_lease),
  .loaded(dc_loaded),.invalidate,.image_write,.image_context,.image_address,.image_data,.image_ready,.image_ack,
  .saved_base,.saved_count,.saved_mask,.saved_batch,.saved_feed,.saved_double,.saved_c0,.saved_c1,.saved_owner,
  .requested_start(start_contexts),.admitted_start,.applied_count(dc_applied));
'''
    text+=f' {private} #({connections}) candidate (\n'
    text+='''  .host_context(shadow_context),.host_addr(shadow_address),.load_we(image_write),.write_data(image_data),
  .read_en(read_en && !dc_active && !dc_begin && dc_link_drained && !dc_error),
  .start_contexts(admitted_start),.base(saved_base),.warm_count(saved_count),.double_mask(saved_mask),
  .batch_mode(saved_batch),.feed_mode(saved_feed),.double_bit(saved_double),.initial_c0(saved_c0),.initial_c1(saved_c1),
  .error(core_error),.read_valid(candidate_read_valid),.canonical_ready(candidate_canonical_ready),
  .r15_invalidate(invalidate),.r15_idle(dc_idle),.r15_next_epoch(dc_next_epoch),.r15_job_generation(dc_job_generation),
  .r15_write_ready(image_ready),.r15_write_ack(image_ack),.*);
 end endgenerate
 // synthesis translate_off
 initial if(DIRECT_COLD!=0 && DIRECT_COLD!=1)$fatal(1,"R15_DIRECT_FLAG");
 // synthesis translate_on
endmodule
'''
    for dep in (GUARD,LOADER):
        name=Path(dep).name;b['files'][name]=(ROOT/dep).read_text()
        b['rtl_sources'].append(name)
        b['source_dependencies'].append(dep)
        b['source_sha256'][dep]=hashlib.sha256((ROOT/dep).read_bytes()).hexdigest()
    b['files'][top+'.sv']=text;b['rtl_sources'].append(top+'.sv');b['top']=top
    b['parameters']['DIRECT_COLD']=1
    b['generated_sha256']={p:hashlib.sha256(t.encode()).hexdigest() for p,t in b['files'].items()}
    b['r15_direct_cold']={'status':'SOURCE_ONLY_NATIVE_PENDING','default_off_literal_parent':True,
        'format':'raw32-natural-digits-c0-c1-v1','no_image_staging':True,
        'setup_recomputed_after_start':True,'legacy_load_and_header_inputs':'Inactive when DIRECT_COLD=1; use dc interface.',
        'current_session':'Trusted reset/drain controller input, not MMIO DATA-supplied authority.',
        'reset_contract':'Common reset plus two-domain drain before current_session reuse; finite lease wrap fails closed.',
        'checkpoint_final':'Retained protected canonical publication/readback; no raw-export/copy-removal claim.',
        'ready':False,'real_pcie_shell':False}
    b['r15_host_link']={'source_ready':True,'real_pcie_ip_ready':False,
        'native_qualified':False,'direct_cold':True,'pcie_shell':False}
    return b
