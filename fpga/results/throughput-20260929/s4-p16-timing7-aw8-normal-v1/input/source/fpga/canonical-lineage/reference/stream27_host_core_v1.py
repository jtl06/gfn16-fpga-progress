"""Source-visible scalar S4 host/image controller with finite fast batching.

Legacy start uses one square and publishes the actual canonical copied image
before done. Explicit batch_mode/count/mask pays finalization once per stopped
chain. Warm completion is never a host read-ready promise. The existing carry
component is P16-only; P8 whole composition is rejected, not silently replaced.
Frozen historical generators and native-qualified components are unchanged.
"""
import ast
import hashlib
import json
from . import stream27_threefield_carry_v1 as three
from . import stream27_warm_recurrence_v1 as warm
from . import stream27_warm_canonical_v1 as canon
from . import stream27_warm_canonical_v2 as canon2
from . import stream27_shared_field_v3 as shared

ROOT=three.ROOT
PINS={
    'reference/stream27_threefield_carry_v1.py':'361edd39be8ba787275a19167bc188de4f87489b9df7c6558b587dc4814619bd',
    'reference/stream27_warm_recurrence_v1.py':'8a137b94a910f94f7db556cd41f31aaf4c0ef8e8b9345008703a460fcef39044',
    'reference/stream27_warm_canonical_v1.py':'c9d868a3f8ef3377499108c00732d103ae4cb409b19a11649b116690ece03682',
    'reference/stream27_warm_canonical_v2.py':'b7ab92d9f3c002bab54930e7f67077a7f91439f5ec8eb78db86127a4befd4b96',
    'reference/stream27_shared_field_v3.py':'42d786e62801476c1444861973bae16c98b5d8a74b5d22c1d50c5043d83de546',
    'rtl/kernel/genefer_stream27_host_image_ports_v1.sv':'2d1dbcd3d923323481b920d1354127306cf19253ee98ad60c0a87626cb1ba11e',
}
HOST='rtl/kernel/genefer_stream27_host_image_ports_v1.sv'


def sha(path):return hashlib.sha256((ROOT/path).read_bytes()).hexdigest()


def bind(module,**overrides):
    """Rebind only a frozen additive compiler's prepare entry point."""
    path='reference/'+module.__name__.rsplit('.',1)[-1]+'.py';raw=(ROOT/path).read_text()
    if sha(path)!=PINS[path]:raise ValueError('S4_HOST_FROZEN_COMPILER_DRIFT:'+path)
    nodes=[node for node in ast.parse(raw).body if isinstance(node,ast.FunctionDef) and node.name=='prepare']
    if len(nodes)!=1:raise ValueError('S4_HOST_COMPILER_ENTRY:'+path)
    node=nodes[0];body=''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    namespace=dict(vars(module));namespace.update(overrides)
    exec(compile(body,str(ROOT/path)+'[signed scalar host composition]','exec'),namespace)
    return namespace['prepare']


def renamed(factory):
    def build(*args):
        top,text=factory(*args);new=top+'_host_v1'
        anchor='module '+top+' #'
        if text.count(anchor)!=1:raise ValueError('S4_HOST_MODULE_ANCHOR')
        return new,text.replace(anchor,'module '+new+' #',1)
    return build


def signed_chain(n,p,*,contexts=1,allow_full_constants=False):
    def field(n,p,field,**kwargs):
        kwargs['mode']='warm_signed';return shared.prepare(n,p,field,**kwargs)
    arithmetic=bind(three,compile_field=field,source=renamed(three.source))
    recurrence=bind(warm,compile_core=arithmetic,source=renamed(warm.source))
    finalizer=bind(canon,compile_warm=recurrence,source=renamed(canon2.source))
    return finalizer(n,p,paired=False,contexts=contexts,allow_full_constants=allow_full_constants)


def source(n,child):
    aw=n.bit_length()-1;top=f'genefer_stream27_host_core_aw{aw}_p16_v1'
    return top,f'''// Same scalar digit/readback contract; explicit finite batch extension.
// Host done includes real canonicalization AND copying every signed32 word.
module {top} #(parameter int AW={aw},P=16,CONTEXTS=1) (
 input logic clk,rst_n,load_we,read_en,start,
 input logic [AW-1:0] host_addr,input logic signed [31:0] write_data,
 input logic [31:0] base,input logic double_bit,
 input logic batch_mode,input logic [31:0] warm_count,double_mask,
 output logic read_valid,output logic signed [95:0] read_data,
 output logic busy,done,error,
 output logic [63:0] cycles,conversion_cycles,root_cycles,ntt_cycles,crt_cycles,carry_cycles,
 output logic [6:0] carry_passes,output logic profile_cache_valid,profile_loads,profile_hits,
 output logic [15:0] profile_words_loaded,output logic [63:0] seed_setup_cycles,
 output logic warm_done,output logic [31:0] completed_squares,
 output logic [63:0] canonical_cycles,image_copy_cycles,
 output logic canonical_ready);
 localparam int N=1<<AW,ROW_W=AW-4,ROWS=1<<ROW_W,K=2*N+384;
 localparam int MIN_PROOF=(2*K+2)/3+1,MIN_BASE=(2*N+5)>MIN_PROOF ? (2*N+5) : MIN_PROOF;
 typedef enum logic [3:0] {{IDLE,SETUP,WAIT_SETUP,COLD,WARM,CANON_WAIT,COPY,COPY_DRAIN,FAILED}} state_t;
 state_t state;
 logic [31:0] job_base,job_count,job_mask,cache_base;logic job_double;
 logic [7:0] job_generation;
 logic [ROW_W-1:0] cold_row,request_row_d,source_row;
 logic source_valid;logic [P*32-1:0] source_data;
 logic [AW:0] copy_requested,copy_committed;
 wire setup_done,config_valid,child_error,child_pending,child_done,child_busy,child_cancelled;
 wire child_read_valid,child_ready,child_warm_done;
 wire signed [95:0] child_read_data;wire [AW-1:0] child_read_address;
 wire [63:0] child_canonical_cycles;
 wire row_read_valid,scalar_read_valid;wire signed [95:0] scalar_read_data;
 wire [P*32-1:0] row_read_data;
 wire row_request=(state==COLD) && !error;
 wire source_start=source_valid && source_row==0;
 wire read_request=(state==COPY) && copy_requested<(AW+1)'(N) && !error;
 wire copy_bad=(state==COPY && child_read_valid) &&
  (copy_committed>=(AW+1)'(N) || child_read_address!=copy_committed[AW-1:0] ||
   child_read_data[95:32]!={{64{{child_read_data[31]}}}});
 wire copy_fire=(state==COPY) && child_read_valid && !copy_bad && !error && !child_error;
 wire request_bad=state==IDLE && start &&
  (base<32'(MIN_BASE) || base>32'd1000000000 || (batch_mode && (warm_count==0 || warm_count>32'd32)));
 assign busy=state!=IDLE && state!=FAILED;
 assign read_valid=scalar_read_valid && !busy && !error;
 assign read_data=scalar_read_data;
 assign profile_cache_valid=config_valid && !error;
 assign profile_words_loaded=0; // Static compiled roots, not runtime T5b root-bundle loads.
 assign crt_cycles=0; // CRT overlaps streaming NTT/carry; no double-counted phase sum.
 assign seed_setup_cycles=root_cycles;
 assign canonical_cycles=child_canonical_cycles;
 assign warm_done=child_warm_done && !error;
 assign canonical_ready=state==IDLE && child_ready && !error;
 genefer_stream27_host_image_ports_v1 #(.AW(AW),.P(P),.ROW_W(ROW_W)) host_image (
  .clk,.rst_n,.host_access(state==IDLE && !start && !error),.load_we,.read_en,.host_addr,.write_data,
  .row_read_req(row_request),.row_read_address(cold_row),
  .commit_we(copy_fire),.commit_address(child_read_address),.commit_word(child_read_data[31:0]),
  .read_valid(scalar_read_valid),.read_data(scalar_read_data),.row_read_valid,.row_read_data);
 // The actual synchronous row RAM q at E0 crosses one source FF at E1;
 // the common field accepts at E2. Natural block -> physical reverse4 is static.
 for(genvar lane=0;lane<P;lane=lane+1)begin: cold_route
  localparam int NATURAL=((lane&1)<<3)|((lane&2)<<1)|((lane&4)>>1)|((lane&8)>>3);
  always_ff @(posedge clk)if(row_read_valid)source_data[32*lane+:32]<=row_read_data[32*NATURAL+:32];
 end
 {child} #(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) engine (
  .clk,.rst_n,.begin_setup(state==SETUP && !error),.in_slot_valid(source_valid && !error),
  .frame_start(source_start),.context_enabled(!error),.double_in(job_double),
  .generation_in(job_generation),.live_generation(job_generation),.base_in(job_base),
  .epoch_in(16'd0),.correction_epoch(16'd0),.correction_valid(source_start && !error),
  .correction_generation(job_generation),.data_in(source_data),.c0_in({{(P*32){{1'b0}}}}),.c1_in({{(P*32){{1'b0}}}}),
  .square_count(job_count),.double_mask(job_mask),.config_valid,.setup_done,
  .out_error(child_error),.fault_pending(child_pending),.frame_accept(),.correction_accept(),
  .internal_frame_accept(),.internal_correction_accept(),.active(),.warm_done(child_warm_done),
  .warm_cancelled(),.completed_frames(completed_squares),
  .coefficient_valid(),.coefficient_start(),.coefficient_data(),.coefficient_row(),
  .digit_valid(),.digit_start(),.digit_eligible(),.digit_data(),.digit_row(),.digit_epoch(),.digit_generation(),
  .boundary_valid(),.boundary_eligible(),.next_c0(),.next_c1(),.next_epoch(),.next_generation(),.frame_done(),.done_epoch(),
  .read_req(read_request),.read_address(copy_requested[AW-1:0]),.busy(child_busy),.done(child_done),
  .cancelled(child_cancelled),.canonical_ready(child_ready),.read_valid(child_read_valid),
  .read_address_out(child_read_address),.read_data(child_read_data),.canonical_cycles(child_canonical_cycles));
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   state<=IDLE;done<=0;error<=0;job_base<=0;job_count<=0;job_mask<=0;job_double<=0;cache_base<=0;job_generation<=0;
   cold_row<=0;request_row_d<=0;source_row<=0;source_valid<=0;copy_requested<=0;copy_committed<=0;
   cycles<=0;conversion_cycles<=0;root_cycles<=0;ntt_cycles<=0;carry_cycles<=0;carry_passes<=0;
   profile_loads<=0;profile_hits<=0;image_copy_cycles<=0;
  end else begin
   done<=0;source_valid<=row_read_valid && !error;
   if(row_request)request_row_d<=cold_row;
   if(row_read_valid)source_row<=request_row_d;
   if(busy)begin
    cycles<=cycles+64'd1;
    if(state==SETUP || state==WAIT_SETUP)root_cycles<=root_cycles+64'd1;
    if(state==COLD)conversion_cycles<=conversion_cycles+64'd1;
    if(state==WARM)ntt_cycles<=ntt_cycles+64'd1;
    if(state==CANON_WAIT || state==COPY || state==COPY_DRAIN)carry_cycles<=carry_cycles+64'd1;
    if(state==COPY || state==COPY_DRAIN)image_copy_cycles<=image_copy_cycles+64'd1;
   end
   case(state)
    IDLE:if(start)begin
     job_base<=base;job_double<=double_bit;job_count<=batch_mode ? warm_count : 32'd1;
     job_mask<=batch_mode ? double_mask : 32'd0;job_generation<=job_generation+8'd1;
     cycles<=0;conversion_cycles<=0;root_cycles<=0;ntt_cycles<=0;carry_cycles<=0;carry_passes<=0;image_copy_cycles<=0;
     cold_row<=0;copy_requested<=0;copy_committed<=0;profile_loads<=0;profile_hits<=0;
     if(config_valid && cache_base==base)begin state<=COLD;profile_hits<=1;end
     else begin state<=SETUP;profile_loads<=1;end
    end
    SETUP:state<=WAIT_SETUP;
    WAIT_SETUP:if(setup_done && config_valid && !child_error)begin cache_base<=job_base;state<=COLD;end
    COLD:if(row_request)begin
     if(cold_row==ROW_W'(ROWS-1))state<=WARM;else cold_row<=cold_row+ROW_W'(1);
    end
    WARM:if(child_warm_done)state<=CANON_WAIT;
    CANON_WAIT:if(child_done && child_ready && !child_cancelled)begin
     state<=COPY;copy_requested<=0;copy_committed<=0;
     carry_passes<=child_canonical_cycles==64'(7*N) ? 7'd4 : 7'd3;
    end
    COPY:begin
     if(read_request)copy_requested<=copy_requested+(AW+1)'(1);
     if(copy_fire)begin
      copy_committed<=copy_committed+(AW+1)'(1);
      if(copy_committed==(AW+1)'(N-1))state<=COPY_DRAIN;
     end
    end
    COPY_DRAIN:begin state<=IDLE;done<=1;end
    FAILED:begin end
    default:begin state<=FAILED;error<=1;done<=1;end
   endcase
   // Fault notification is a legacy done+error event, not canonical SUCCESS.
   // The frozen barrier itself never fabricates successful done on a fault.
   if(!error && (request_bad || child_error || copy_bad || child_cancelled))begin
    state<=FAILED;error<=1;done<=1;source_valid<=0;
   end
  end
 end
 // synthesis translate_off
 initial if(AW!={aw} || P!=16 || CONTEXTS!=1)$fatal(1,"S4_HOST_CORE_GEOMETRY");
 always @(posedge clk)if(rst_n && done && !error)begin
  if(busy || !canonical_ready || copy_committed!=(AW+1)'(N))$fatal(1,"S4_HOST_DONE_BEFORE_COPIED_IMAGE");
  if(cycles!=root_cycles+conversion_cycles+ntt_cycles+carry_cycles)$fatal(1,"S4_HOST_PHASE_ACCOUNTING");
 end
 // synthesis translate_on
endmodule
'''


def cycle_contract(n,geometry,*,count=1,cache_hit=False,special=False):
    if not 1<=count<=32:raise ValueError('S4_HOST_FINITE_COUNT')
    first=3 if cache_hit else 102
    final=first+(count-1)*geometry['warm_interval']+geometry['carry_done']
    barrier=(7 if special else 6)*n
    return dict(cold_first_field_accept=first,final_carry_done=final,warm_done=final+1,
        canonical_begin=final+2,canonical_done=final+2+barrier,
        first_image_commit=final+barrier+6,host_done=final+2+barrier+n+4,
        canonical_busy_cycles=barrier,image_copy_cycles=n+3,canonical_done_to_host_done=n+4,
        scope='Source/event proposal awaiting actual scalar-host native qualification; no clock claim')


def prepare(n=32,p=16,*,paired=False,contexts=1,allow_full_constants=False):
    if p!=16:raise ValueError('S4_HOST_P8_CARRY_WRAPPER_NOT_QUALIFIED')
    if contexts!=1:raise ValueError('S4_HOST_CONTEXTS2_REQUIRES_S5')
    for path,pin in PINS.items():
        if sha(path)!=pin:raise ValueError('S4_HOST_COMPONENT_DRIFT:'+path)
    b=signed_chain(n,p,contexts=contexts,allow_full_constants=allow_full_constants)
    child=b['top'];top,text=source(n,child);b['files'][top+'.sv']=text
    b['files']['genefer_stream27_host_image_ports_v1.sv']=(ROOT/HOST).read_text()
    deps=b['source_dependencies']+[HOST,'reference/stream27_warm_canonical_v2.py','reference/stream27_host_core_v1.py']
    if paired:
        if sha(canon.PRODUCTION)!=canon.PRODUCTION_PIN:raise ValueError('S4_HOST_T5B_MANIFEST_DRIFT')
        m=json.loads((ROOT/canon.PRODUCTION).read_text())
        for name,pin in m['source_sha256'].items():
            path='rtl/kernel/'+name
            if sha(path)!=pin:raise ValueError('S4_HOST_T5B_RTL_DRIFT:'+name)
            value=(ROOT/path).read_text()
            if name in b['files'] and b['files'][name]!=value:raise ValueError('S4_HOST_T5B_SHARED_COLLISION:'+name)
            b['files'][name]=value;deps.append(path)
        deps.append(canon.PRODUCTION)
        pairtop=top.replace('host_core','host_t5b_paired');header=text.split(' localparam',1)[0]
        header=header.replace('module '+top+' #','module '+pairtop+' #',1)
        anchor='output logic canonical_ready);'
        if header.count(anchor)!=1:raise ValueError('S4_HOST_PAIRED_HEADER')
        header=header.replace(anchor,'''output logic canonical_ready,
 input logic t5b_load_we,t5b_read_en,t5b_start,t5b_double_bit,
 input logic [AW-1:0] t5b_host_addr,input logic signed [31:0] t5b_write_data,
 output logic t5b_read_valid,t5b_busy,t5b_done,t5b_error,
 output logic signed [95:0] t5b_read_data);''')
        b['files'][pairtop+'.sv']=header+f''' {top} #(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) candidate (.*);
 {m['top']} #(.AW(AW),.NTT_LANES(64)) production (
  .clk,.rst_n,.load_we(t5b_load_we),.read_en(t5b_read_en),.start(t5b_start),
  .host_addr(t5b_host_addr),.write_data(t5b_write_data),.base,.double_bit(t5b_double_bit),
  .read_valid(t5b_read_valid),.read_data(t5b_read_data),.busy(t5b_busy),.done(t5b_done),.error(t5b_error),
  .cycles(),.conversion_cycles(),.root_cycles(),.ntt_cycles(),.crt_cycles(),.carry_cycles(),.carry_passes(),
  .profile_cache_valid(),.profile_loads(),.profile_hits(),.profile_words_loaded(),.seed_setup_cycles());
endmodule
''';top=pairtop
    b['top']=top;b['rtl_sources']=[name for name in b['files'] if name.endswith('.sv')]
    b['source_dependencies']=list(dict.fromkeys(deps));b['source_sha256']={path:sha(path) for path in b['source_dependencies']}
    b['generated_sha256']={name:hashlib.sha256(value.encode()).hexdigest() for name,value in b['files'].items()}
    b['scope']='Scalar host image source integration; complete old value/idle arbitration plus explicit finite1..32 batch extension. Await native gates; long PRP pending.'
    b['host_contract']=dict(read='Accepted idle scalar E0 actual RAM q/signextended96; writes win simultaneous reads.',
        busy='Host load/read/start ignored while busy; start has priority in idle.',
        legacy='batch_mode0: one square per start; done only after6N/7N canonicalization plus N actual copy writes/handoff/drain.',
        batch='batch_mode1: explicit1..32 count/mask command; one final barrier and copy per stopped chain; NOT full long PRP.',
        errors='One registered done+error notification then quarantined until reset/fullreload; frozen canonical done remains SUCCESS-only.',
        cold_signed='Exact signed-1 or unsigned0..base-1; idle stores arbitrary signed32 and validation occurs at start.',
        profile_guard='max(2N+5,ceil(2*(2N+384)/3)+1)..1e9; stricter than T5b at small AW, identical fullN lowerguard.',
        diagnostics='Disjoint outer phase counters; parallel CRT overlaps ntt/carry so crt_cycles0. Static roots words_loaded0; cache means shared reciprocal/base setup, not runtime T5b root bundles.',
        extra_shadow_bits=32*n,canonical_bits=32*n)
    b['cycle_contract']=cycle_contract(n,b['geometry'])
    return b
