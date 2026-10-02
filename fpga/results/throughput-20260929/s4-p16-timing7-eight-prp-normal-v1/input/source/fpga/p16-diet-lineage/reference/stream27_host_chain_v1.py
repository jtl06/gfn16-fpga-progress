"""Additive scalar-compatible long-chain host with a four-descriptor FIFO.

The FIFO feeds only control; every dependent digit/correction remains on the
native on-chip arithmetic feedback path. Legacy scalar starts still complete
one canonical copied image. Explicit feed jobs finalize only their true last
32-bit operation ordinal, never an aliased 16-bit physical epoch.
"""
import ast
import hashlib
from . import stream27_host_core_v1 as root
from . import stream27_host_core_v5 as parent
from . import stream27_chain_canonical_v1 as canonical

ROOT=root.ROOT
PINS={
 'reference/stream27_host_core_v1.py':'7a6cee18c198d09a473e24a89f651b94a32402fbb14ea21cd66717cf106dca20',
 'reference/stream27_host_core_v5.py':'e842a3212aefef0f7defc64b38c901dfbc065e56e97868f94159c9f379aaaf72',
}


def source(n,child):
    top,s=parent.source(n,child);new=top.replace('host_core','host_chain').replace('_v5','_v1')
    changes=[('module '+top+' #','module '+new+' #'),
      ('output logic canonical_ready);', '''input logic feed_mode,command_valid,command_double,
 input logic [31:0] command_index,input logic [7:0] command_generation,
 output logic command_ready,command_accept,operation_accept,
 output logic [7:0] accepted_generation,output logic [2:0] feed_level,
 output logic [31:0] operations_started,commands_enqueued,commands_consumed,final_image_rows,
 output logic [3:0] feed_error_code,
 output logic canonical_ready);'''),
      ('logic [7:0] job_generation;', '''logic [7:0] job_generation;
 logic job_feed,first_operation_seen;
 logic [1:0] feed_read,feed_write;logic [2:0] feed_count;
 logic [31:0] feed_index[0:3],next_write_index;
 logic [7:0] feed_generation[0:3];logic feed_double[0:3];
 wire feed_pop,cold_accept,final_load_valid;wire [31:0] child_started,final_load_sequence;
 wire [3:0] child_feed_error;
 wire feed_state=state==SETUP || state==WAIT_SETUP || state==COLD || state==WARM;
 assign command_ready=job_feed && feed_state && !error && (feed_count<3'd4 || feed_pop);
 wire ingress_bad=command_valid && command_ready &&
  (command_generation!=job_generation || command_index!=next_write_index || command_index==0 || command_index>=job_count);
 wire feed_push=command_valid && command_ready && !ingress_bad;
 assign command_accept=feed_push;assign operation_accept=feed_pop;
 assign accepted_generation=job_generation;assign feed_level=feed_count;
 assign operations_started=first_operation_seen ? child_started : 32'd0;'''),
      ("warm_count==0 || warm_count>32'd32", "warm_count==0 || (!feed_mode && warm_count>32'd32)"),
      ('.square_count(job_count),.double_mask(job_mask),.config_valid,.setup_done,', '''.square_count(job_count),.double_mask(job_mask),.config_valid,.setup_done,
  .feed_mode(job_feed),.command_valid(feed_count!=0),.command_double(feed_double[feed_read]),
  .command_index(feed_index[feed_read]),.command_generation(feed_generation[feed_read]),
  .command_accept(feed_pop),.started_frames(child_started),.chain_error_code(child_feed_error),
  .digit_sequence(),.boundary_sequence(),.final_load_valid,.final_load_sequence,'''),
      ('.frame_accept(),.correction_accept(),', '.frame_accept(cold_accept),.correction_accept(),'),
      ('job_generation<=0;', '''job_generation<=0;
   job_feed<=0;first_operation_seen<=0;feed_read<=0;feed_write<=0;feed_count<=0;next_write_index<=1;
   commands_enqueued<=0;commands_consumed<=0;final_image_rows<=0;feed_error_code<=0;'''),
      ('done<=0;source_valid<=row_read_valid && !error;', '''done<=0;source_valid<=row_read_valid && !error;
   if(cold_accept)first_operation_seen<=1;
   if(final_load_valid)final_image_rows<=final_image_rows+32'd1;
   if(feed_push)begin
    feed_index[feed_write]<=command_index;feed_generation[feed_write]<=command_generation;feed_double[feed_write]<=command_double;
    feed_write<=feed_write+2'd1;next_write_index<=next_write_index+32'd1;commands_enqueued<=commands_enqueued+32'd1;
   end
   if(feed_pop)begin feed_read<=feed_read+2'd1;commands_consumed<=commands_consumed+32'd1;end
   case({feed_push,feed_pop})
    2'b10:feed_count<=feed_count+3'd1;
    2'b01:feed_count<=feed_count-3'd1;
    default:begin end
   endcase
   if(feed_error_code==0)begin
    if(ingress_bad)feed_error_code<=command_generation!=job_generation ? 4'd2 :
     ((command_index==0 || command_index>=job_count) ? 4'd4 : 4'd3);
    else if(child_feed_error!=0)feed_error_code<=child_feed_error;
   end'''),
      ('job_mask<=batch_mode ? double_mask : 32\'d0;', '''job_mask<=batch_mode ? double_mask : 32'd0;
     job_feed<=batch_mode && feed_mode;first_operation_seen<=0;
     feed_read<=0;feed_write<=0;feed_count<=0;next_write_index<=1;
     commands_enqueued<=0;commands_consumed<=0;final_image_rows<=0;feed_error_code<=0;'''),
      ('child_cancelled || completion_bad', 'child_cancelled || completion_bad || ingress_bad'),
      ('if(cycles!=root_cycles+conversion_cycles+ntt_cycles+carry_cycles)', '''if(final_image_rows!=32'(ROWS))$fatal(1,"S4_LONG_TRUE_LAST_IMAGE_ROW_COUNT");
  if(job_feed && (commands_enqueued!=job_count-32'd1 || commands_consumed!=job_count-32'd1 || feed_count!=0))$fatal(1,"S4_LONG_DONE_COMMAND_ACCOUNTING");
  if(cycles!=root_cycles+conversion_cycles+ntt_cycles+carry_cycles)'''),
      (' // synthesis translate_on', ''' always @(posedge clk)if(rst_n && !error)begin
  if(feed_count>3'd4 || (feed_pop && feed_count==0))$fatal(1,"S4_LONG_FIFO_ELIGIBILITY");
  if(final_load_valid && final_load_sequence!=job_count-32'd1)$fatal(1,"S4_LONG_PREMATURE_FINAL_IMAGE");
 end
 // synthesis translate_on''')]
    for old,newtext in changes:
        if s.count(old)!=1:raise ValueError('S4_LONG_HOST_ANCHOR:'+old)
        s=s.replace(old,newtext)
    return new,s


def cycle_contract(n,g,*,count=1,cache_hit=False,special=False):
    if not 1<=count<=0xffffffff:raise ValueError('S4_LONG_COUNT_RANGE')
    first=3 if cache_hit else 102;final=first+(count-1)*g['warm_interval']+g['carry_done'];barrier=(7 if special else 6)*n
    return dict(cold_first_field_accept=first,final_carry_done=final,warm_done=final+1,
      canonical_begin=final+2,canonical_done=final+2+barrier,first_image_commit=final+barrier+6,
      host_done=final+2+barrier+n+4,canonical_busy_cycles=barrier,image_copy_cycles=n+3,
      canonical_done_to_host_done=n+4,scope='Exact source/event ledger, not native or clock evidence')


def prepare(n=32,p=16,*,paired=False,contexts=1,allow_full_constants=False):
    for path,pin in PINS.items():
        if root.sha(path)!=pin:raise ValueError('S4_LONG_HOST_PARENT_DRIFT:'+path)
    raw=(ROOT/'reference/stream27_host_core_v1.py').read_text()
    node=next(x for x in ast.parse(raw).body if isinstance(x,ast.FunctionDef) and x.name=='prepare')
    body=''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    def child(n,p,**kwargs):return canonical.prepare(n,p,**kwargs)
    # The frozen paired emitter recognizes host_core in the root's identifier.
    # Use a temporary unique name during composition, then rename identifiers
    # and matching filenames together; never overwrite the root with its pair.
    def composable_source(n,child):
        top,s=source(n,child);temporary=top.replace('host_chain','host_core_long')
        return temporary,s.replace(top,temporary)
    namespace=dict(vars(root));namespace.update(source=composable_source,signed_chain=child)
    exec(compile(body,'[S4 additive long host]','exec'),namespace)
    b=namespace['prepare'](n,p,paired=paired,contexts=contexts,allow_full_constants=allow_full_constants)
    def rename(s):return s.replace('host_t5b_paired_long','host_chain_t5b_paired').replace('host_core_long','host_chain')
    b['files']={rename(name):rename(s) for name,s in b['files'].items()}
    b['top']=rename(b['top']);b['rtl_sources']=[name for name in b['files'] if name.endswith('.sv')]
    if paired:
        name=b['top']+'.sv';s=b['files'][name];old='#(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) candidate (.*);'
        if s.count(old)!=1:raise ValueError('S4_LONG_PAIRED_SEED_ANCHOR')
        b['files'][name]=s.replace(old,'#(.EPOCH_SEED(EPOCH_SEED),.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) candidate (.*);')
    for path in ('reference/stream27_host_core_v2.py','reference/stream27_host_core_v3.py',
                 'reference/stream27_host_core_v4.py','reference/stream27_host_core_v5.py',
                 'reference/stream27_host_chain_v1.py'):
        b['source_dependencies'].append(path)
    b['source_dependencies']=list(dict.fromkeys(b['source_dependencies']))
    b['source_sha256']={path:root.sha(path) for path in b['source_dependencies']}
    b['generated_sha256']={name:hashlib.sha256(s.encode()).hexdigest() for name,s in b['files'].items()}
    b['scope']='Additive scalar-compatible streamed-control long-chain host SOURCE only; native qualification pending; P16 current carry, P8 remains explicitly rejected.'
    b['host_contract'].update(
      feed='batch_mode && feed_mode enables count1..UINT32_MAX; four ordered generation/index/double descriptors, indices1..count-1. Initial bit is double_bit. No empty bypass.',
      backpressure='command_ready during setup/cold/warm iff slot free or actual same-edge consumer pop. Full valid is held stable by producer, not an error.',
      starvation='Missing/wrong head at required first warm-row edge suppresses that frame and registers error; no slower fallback or fabricated zero bit.',
      final='Full32-bit physical result ordinal qualifies final raw rows and late boundaries. Only true last operation triggers canonical6N/7N and N-copy/handoff.',
      publication='Host done remains canonical copied-image completion. Warm_done/operation_accept are diagnostics, not immediate read-ready promises.',
      fifo_bits=4*(32+8+1),fifo_reset='Eligibility/pointers/count cleared on reset/new job; payload not reset.',
      epoch='Persistent completed-cold ledger modulo16, default0/range-guarded seed; descriptor indices and final selector are full32 independent of physical epoch.')
    b['cycle_contract']=cycle_contract(n,b['geometry'])
    return b
