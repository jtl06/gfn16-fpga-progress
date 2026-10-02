"""Materialized final image after finite S4 recurrence; explicit stream API.

No canonicalization occurs between warm squares. This completes the hardware
value/readback barrier for a stream-fed chain, not scalar Track A host mutation
semantics or a silent immediate-read ABI substitution.
"""
import hashlib
import json
from .stream27_warm_recurrence_v1 import ROOT,prepare as compile_warm

CANON='rtl/kernel/genefer_stream27_canonical_image_v1.sv'
CANON_PIN='c6e59a385ed187dceb9b392c096cc1d7cfc5a71ba820326b9b441f1df8093e74'
RAM='rtl/kernel/genefer_sdp_ram32.sv'
RAM_PIN='993567fb68fdc216b9ff04489d1810f743b86564434e4b48261ad606b25d53b0'
PRODUCTION='results/throughput-20260929/core27-t5b-provisional64-aws-fit-v1/manifest.json'
PRODUCTION_PIN='1a1a67980f1744be70c0b089dcdf7e20c4cdd8714cbac26bd5798c28abbcc011'


def sha(path):return hashlib.sha256((ROOT/path).read_bytes()).hexdigest()


def source(n,child,text):
    aw=n.bit_length()-1;top=f'genefer_stream27_warm_canonical_aw{aw}_p16_v1'
    header=text.split(' localparam',1)[0]
    header=header.replace('module '+child+' #','module '+top+' #',1)
    anchor='output logic frame_done,output logic [15:0] done_epoch);'
    if header.count(anchor)!=1:raise ValueError('S4_CANONICAL_HEADER_ANCHOR')
    header=header.replace(anchor,'''output logic frame_done,output logic [15:0] done_epoch,
 input logic read_req,input logic [AW-1:0] read_address,
 output logic busy,done,cancelled,canonical_ready,read_valid,
 output logic [AW-1:0] read_address_out,output logic signed [95:0] read_data,
 output logic [63:0] canonical_cycles);''')
    return top,header+f''' localparam int ROW_W=AW-4;
 wire warm_error,warm_pending,canonical_busy,canonical_done,canonical_error,canonical_image_valid;
 wire [7:0] canonical_error_code;logic controller_error,finalizing,metadata_ready;
 logic [15:0] final_epoch;logic [7:0] chain_generation;logic [31:0] chain_base;
 logic [P*32-1:0] final_c0,final_c1;
 {child} #(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) recurrence (.out_error(warm_error),.fault_pending(warm_pending),.*);
 assign out_error=warm_error || canonical_error || controller_error;
 assign fault_pending=out_error || warm_pending || (warm_done && !warm_cancelled && !metadata_ready);
 wire publish_ok=!cancelled && context_enabled && chain_generation==live_generation;
 wire final_row=digit_valid && digit_eligible && digit_epoch==final_epoch && digit_generation==chain_generation;
 wire canonical_request=warm_done && !warm_cancelled && publish_ok && metadata_ready && !out_error;
 // warm_done is a drained arithmetic diagnostic, not host completion. Busy
 // bridges it through the actual once-per-chain materialization. No idle gap.
 assign busy=(active || finalizing || warm_done) && !canonical_done && !out_error;
 assign done=canonical_done && publish_ok && !out_error;
 assign canonical_ready=canonical_image_valid && !busy && publish_ok && !out_error;
 genefer_stream27_canonical_image_v1 #(.AW(AW),.P(P),.ROW_W(ROW_W)) final_image (
  .clk,.rst_n,.load_valid(final_row && !out_error),.load_row(digit_row),.load_data(digit_data),
  .begin_canonical(canonical_request),.base(chain_base),.c0(final_c0),.c1(final_c1),
  .read_req(read_req && canonical_ready),.read_address,.busy(canonical_busy),.done(canonical_done),
  .error(canonical_error),.error_code(canonical_error_code),.image_valid(canonical_image_valid),
  .cycles(canonical_cycles),.read_valid,.read_address_out,.read_data);
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin controller_error<=0;finalizing<=0;metadata_ready<=0;cancelled<=0;
   final_epoch<=0;chain_generation<=0;chain_base<=0;final_c0<=0;final_c1<=0;end
  else begin
   if(busy && (!context_enabled || chain_generation!=live_generation))cancelled<=1;
   if(frame_accept)begin
    final_epoch<=epoch_in+16'(square_count-32'd1);chain_generation<=generation_in;chain_base<=base_in;
    metadata_ready<=0;cancelled<=0;
   end
   if(boundary_valid && next_epoch==final_epoch+16'd1 && next_generation==chain_generation)begin
    final_c0<=next_c0;final_c1<=next_c1;metadata_ready<=1;
   end
   if(warm_done)begin
    if(warm_cancelled || !publish_ok)cancelled<=1;
    else if(!metadata_ready)controller_error<=1;
    else finalizing<=1;
   end
   if(canonical_done)finalizing<=0;
  end
 end
 // synthesis translate_off
 initial if(AW!={aw} || P!=16 || CONTEXTS!=1)$fatal(1,"S4_FINAL_IMAGE_GEOMETRY");
 always @(posedge clk)if(rst_n && done && (busy || !canonical_ready || out_error))$fatal(1,"S4_CANONICAL_DONE_PUBLICATION");
 // synthesis translate_on
endmodule
'''


def prepare(n=32,p=16,*,paired=False,contexts=1,allow_full_constants=False):
    if sha(CANON)!=CANON_PIN or sha(RAM)!=RAM_PIN:raise ValueError('S4_CANONICAL_NATIVE_COMPONENT_DRIFT')
    b=compile_warm(n,p,contexts=contexts,allow_full_constants=allow_full_constants)
    child=b['top'];top,text=source(n,child,b['files'][child+'.sv']);b['files'][top+'.sv']=text
    b['files']['genefer_stream27_canonical_image_v1.sv']=(ROOT/CANON).read_text()
    b['files']['genefer_sdp_ram32.sv']=(ROOT/RAM).read_text()
    deps=b['source_dependencies']+[CANON,RAM,'reference/stream27_warm_canonical_v1.py']
    if paired:
        if sha(PRODUCTION)!=PRODUCTION_PIN:raise ValueError('S4_T5B_PARENT_MANIFEST_DRIFT')
        m=json.loads((ROOT/PRODUCTION).read_text())
        for name,pin in m['source_sha256'].items():
            path='rtl/kernel/'+name
            if sha(path)!=pin:raise ValueError('S4_T5B_PARENT_RTL_DRIFT:'+name)
            value=(ROOT/path).read_text()
            if name in b['files'] and b['files'][name]!=value:raise ValueError('S4_T5B_SHARED_SOURCE_COLLISION:'+name)
            b['files'][name]=value;deps.append(path)
        deps.append(PRODUCTION)
        paired_top=top.replace('warm_canonical','t5b_paired')
        header=text.split(' localparam',1)[0].replace('module '+top+' #','module '+paired_top+' #',1)
        anchor='output logic [63:0] canonical_cycles);'
        if header.count(anchor)!=1:raise ValueError('S4_PAIRED_HEADER_ANCHOR')
        header=header.replace(anchor,'''output logic [63:0] canonical_cycles,
 input logic t5b_load_we,t5b_read_en,t5b_start,t5b_double_bit,
 input logic [AW-1:0] t5b_host_addr,input logic signed [31:0] t5b_write_data,
 output logic t5b_read_valid,t5b_busy,t5b_done,t5b_error,
 output logic signed [95:0] t5b_read_data);''')
        body=header+f''' {top} #(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) candidate (.*);
 {m['top']} #(.AW(AW),.NTT_LANES(64)) production (
  .clk,.rst_n,.load_we(t5b_load_we),.read_en(t5b_read_en),.start(t5b_start),
  .host_addr(t5b_host_addr),.write_data(t5b_write_data),.base(base_in),.double_bit(t5b_double_bit),
  .read_valid(t5b_read_valid),.read_data(t5b_read_data),.busy(t5b_busy),.done(t5b_done),.error(t5b_error),
  .cycles(),.conversion_cycles(),.root_cycles(),.ntt_cycles(),.crt_cycles(),.carry_cycles(),.carry_passes(),
  .profile_cache_valid(),.profile_loads(),.profile_hits(),.profile_words_loaded(),.seed_setup_cycles());
endmodule
'''
        b['files'][paired_top+'.sv']=body;top=paired_top
    b['top']=top;b['rtl_sources']=[name for name in b['files'] if name.endswith('.sv')]
    b['source_dependencies']=list(dict.fromkeys(deps));b['source_sha256']={path:sha(path) for path in b['source_dependencies']}
    b['generated_sha256']={name:hashlib.sha256(value.encode()).hexdigest() for name,value in b['files'].items()}
    b['scope']='Stream-fed finite chain + hardware canonical readback and optional actual T5b value comparison; scalar host/image mutation adapter and long PRP controller remain explicit pending gates.'
    b['canonical_cost']=dict(normal=6*n,special=7*n,read_accept_to_response=1,
        request_accept_relative_to_final_carry_done=2,payment='once per stopped chain; not per warm square')
    b['paired_production']=dict(manifest_sha256=PRODUCTION_PIN,RTL_sha256=m['source_sha256'] if paired else None)
    return b
