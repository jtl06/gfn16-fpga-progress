"""Bounded fresh/same-history native reset observer; DUT RTL stays exact."""
import hashlib
import json
from pathlib import Path
import tarfile
from . import stream27_host_chain_native_v3 as parent

PIN='4d42f2328b63f849d8f0ac5ea5d17542035c7d7c9f53057cae6ef7e92829c104'
ROOT=parent.parent.parent.ROOT
RAW=ROOT/'queue/evidence/s4-aw5-long-host-q1-v3/attempt-0/collected/output/native'
FIELDS={
 'state':'state','raw_child_error':'child_error','raw_child_feed_error':'child_feed_error',
 'raw_source_valid':'source_valid','raw_row_valid':'row_read_valid',
 'copy_bad':'copy_bad','completion_bad':'completion_bad','ingress_bad':'ingress_bad','request_bad':'request_bad',
 'warm_error':'engine__DOT__warm_error','canonical_error':'engine__DOT__canonical_error','canonical_controller_error':'engine__DOT__controller_error',
 'local_error':'engine__DOT__recurrence__DOT__local_error','raw_fifo_valid':'engine__DOT__recurrence__DOT__fifo_valid',
 'raw_arithmetic_error':'engine__DOT__recurrence__DOT__child_error','raw_arithmetic_pending':'engine__DOT__recurrence__DOT__child_pending',
 'command_bad':'engine__DOT__recurrence__DOT__command_bad','count_bad':'engine__DOT__recurrence__DOT__count_bad',
 'setup_error':'engine__DOT__recurrence__DOT__arithmetic__DOT__setup_error',
 'join_bad':'engine__DOT__recurrence__DOT__arithmetic__DOT__join_bad','carry_bad':'engine__DOT__recurrence__DOT__arithmetic__DOT__carry_bad',
 'field_controller_error':'engine__DOT__recurrence__DOT__arithmetic__DOT__field0__DOT__controller_error',
 'field_admission_bad':'engine__DOT__recurrence__DOT__arithmetic__DOT__field0__DOT__admission_bad',
 'field_join_bad':'engine__DOT__recurrence__DOT__arithmetic__DOT__field0__DOT__join_bad',
 'protocol_error':'engine__DOT__recurrence__DOT__arithmetic__DOT__field0__DOT__protocol_error',
 'protocol_pending':'engine__DOT__recurrence__DOT__arithmetic__DOT__field0__DOT__protocol_pending',
 'protocol_bad':'engine__DOT__recurrence__DOT__arithmetic__DOT__field0__DOT__epoch_protocol__DOT__bad',
 'protocol_owners':'engine__DOT__recurrence__DOT__arithmetic__DOT__field0__DOT__epoch_protocol__DOT__valid',
 'fwd_slot':'engine__DOT__recurrence__DOT__arithmetic__DOT__field0__DOT__fwd_slot',
 'fwd_start':'engine__DOT__recurrence__DOT__arithmetic__DOT__field0__DOT__fwd_start',
 'inv_slot':'engine__DOT__recurrence__DOT__arithmetic__DOT__field0__DOT__inv_slot',
 'small_slot':'engine__DOT__recurrence__DOT__arithmetic__DOT__field0__DOT__small_slot',
}


def prepare(destination):
    if parent.parent.parent.sha(ROOT/'reference/stream27_host_chain_native_v3.py')!=PIN:raise ValueError('RESET_OBSERVER_PARENT_DRIFT')
    r=parent.prepare(destination,n=32);destination=Path(destination).resolve();source=destination/'inputs/fpga'
    top=r['top'];prefix=top+'__DOT__candidate__DOT__';header=top+'___024root.h'
    with tarfile.open(RAW/'generated-sources.tar.gz','r:gz') as archive:
        raw_header=archive.extractfile(header).read().decode()
    for name in FIELDS.values():
        if prefix+name not in raw_header:raise ValueError('RESET_OBSERVER_MEMBER_NOT_ACTUAL:'+name)
    public=['rst_n','start','load_we','read_en','feed_mode','command_valid','command_double','command_index','command_generation',
      'busy','done','error','warm_done','read_valid','canonical_ready','profile_cache_valid','feed_error_code','feed_level',
      'operations_started','commands_enqueued','commands_consumed','completed_squares','final_image_rows']
    entries=[(name,'d.'+name) for name in public]+[(name,'d.rootp->'+prefix+member) for name,member in FIELDS.items()]
    emit='\n'.join(' std::cout<<",\\"'+name+'\\":"<<uint64_t('+expression+');' for name,expression in entries)
    cpp=f'''#define main retained_long_main
#include "stream27_host_chain_v1.cpp"
#undef main
#include "{header}"
#include <sstream>
static bool first_snapshot=true;
static void snapshot(DUT& d,unsigned history,unsigned age,unsigned step,const char* phase){{
 std::cout<<(first_snapshot?"":",")<<"{{\\"history\\":"<<history<<",\\"age\\":"<<age<<",\\"step\\":"<<step<<",\\"phase\\":\\""<<phase<<"\\"";first_snapshot=false;
{emit}
 std::cout<<"}}";
}}
static void observe_abort(DUT& d,unsigned history,unsigned age){{
 reset(d);Image zero{{}};load(d,zero);feed_clear(d);d.base=MIN_BASE;d.batch_mode=1;d.feed_mode=1;d.warm_count=20;d.start=1;edge(d);
 unsigned next=1;
 for(unsigned elapsed=1;elapsed<=age;++elapsed){{feed_clear(d);d.command_valid=next<20;d.command_index=next;d.command_generation=d.accepted_generation;
  d.clk=0;d.eval();bool push=d.command_accept;edge(d);if(push)++next;need(d.busy&&!d.error&&!d.done,"RESET_OBSERVER_ACTIVE_PREFIX");}}
 need(d.feed_level==4,"RESET_OBSERVER_NONEMPTY_FIFO");snapshot(d,history,age,0,"before_reset");reset(d);snapshot(d,history,age,1,"released");
 need(d.feed_level==0&&d.commands_enqueued==0&&d.commands_consumed==0&&d.operations_started==0&&!d.command_ready,"RESET_OBSERVER_ELIGIBILITY");
 for(unsigned k=2;k<10;++k){{feed_clear(d);d.clk=0;d.eval();snapshot(d,history,age,k,"pre");d.clk=1;d.eval();snapshot(d,history,age,k,"rise");d.clk=0;d.eval();snapshot(d,history,age,k,"fall");}}
 // Diagnostic-only dirty observations are preserved, never qualified as a
 // functional PASS. Reset again only if needed to exercise the next observer.
 if(d.error||d.busy||d.done||d.warm_done||d.read_valid)reset(d);
 load(d,zero);Job recovered{{}};recovered.base=MIN_BASE;recovered.count=1;candidate(d,recovered,false,12,age);production(d,recovered);Counts old;compare(d,recovered,12,age,false,old);
}}
int main(int argc,char** argv){{try{{
 if(argc==2&&std::string(argv[1])=="--runtime-probe")return retained_long_main(argc,argv);
 need(argc==3,"RESET_OBSERVER_ARGUMENTS");
 std::ostringstream scalar;auto* old=std::cout.rdbuf(scalar.rdbuf());int rc=scalar_regression_main(2,argv);std::cout.rdbuf(old);need(rc==0&&scalar.str()==SCALAR_BASELINE_FOOTER,"RESET_OBSERVER_SCALAR_BASELINE");
 std::cout<<"{{\\"schema\\":\\"s4-reset-observation-v1\\",\\"rows\\":[";
 {{VerilatedContext context;context.threads(1);DUT fresh{{&context}};observe_abort(fresh,0,10);observe_abort(fresh,0,236);fresh.final();}}
 {{VerilatedContext context;context.threads(1);DUT d{{&context}};auto list=programs(argv[2]);reset(d);FeedCounts c;bool hit=false;
  for(const auto& p:list){{load(d,p.initial);chain_run(d,p,hit,c);hit=true;if(p.paired)long_production(d,p);long_compare(d,p,c);}}
  for(unsigned type=0;type<4;++type)feed_fault(d,type,c);
  observe_abort(d,1,10);observe_abort(d,1,236);d.final();}}
 std::cout<<"]}}\\n";return 0;
}}catch(const std::exception& e){{std::cerr<<e.what()<<"\\n";return 1;}}}}
'''
    bench='rtl/tb/stream27_host_chain_reset_observer_v1.cpp';(source/bench).write_text(cpp)
    h=source/'rtl/tb/s4_host_config_v1.h';s=h.read_text();m=json.loads((destination/'manifest.json').read_text())
    s+='constexpr const char* SCALAR_BASELINE_FOOTER='+json.dumps(m['steps'][0]['expected_stdout'].split('S4_LONG_HOST')[0])+';\n';h.write_text(s)
    validator='reference/stream27_host_chain_reset_validate_v1.py';target=source/validator;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/validator).read_bytes())
    for name in ('reference/stream27_host_chain_reset_native_v1.py',validator):
        target=source/'lineage'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
    m['build']['cpp_source']=bench;m['steps']=[dict(name='s4-long-reset-observation',argv=['{exe}','{root}/assets/host-corpus-v1.txt','{root}/assets/long-program-v1.txt'],expected_returncode=0,
      validator=dict(source=validator,function='validate',config=dict(aw=5,purpose='reset-observation'),assets={}))]
    m['sources']={str(path.relative_to(source)):parent.parent.parent.sha(path) for path in sorted(source.rglob('*')) if path.is_file()}
    (destination/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');r.update(manifest_sha256=parent.parent.parent.sha(destination/'manifest.json'),source_count=len(m['sources']),
      scope='Reset DIAGNOSTIC observation only: exact frozen DUT; fresh and same-history age10/236, release edges2..9 pre/rise/fall. Does not waive failed functional reset contract.',
      root_header_sha256=hashlib.sha256(raw_header.encode()).hexdigest(),observer_fields=entries,native_run_performed=False,promotion_allowed=False)
    (destination/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    r=prepare(sys.argv[1]);print(json.dumps({k:r[k] for k in ('status','manifest_sha256','source_count','top','scope')},indent=2))
