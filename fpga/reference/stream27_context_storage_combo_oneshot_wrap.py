"""Native-only R6 host-timestamp wrap seam; real datapath time is never forced.

AW8 reuses the exact seventeen-square independent-image corpus. A monitor-only
host clone exports accepted cold transactions and all three real root-cache
owners. C++ jumps only the host's public cycles register, not protocol clocks,
payload, owner, arithmetic state, or worker watchdog time. The old negative
restores ONLY the frozen pre-R6 proposal equation. No billions-of-edges claim.
"""
from datetime import datetime, timezone
import copy
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fpga.reference import stream27_context_storage_combo_oneshot_native as normal
from fpga.reference import stream27_context_storage_combo_oneshot_bind as core

ROOT=normal.ROOT
SELF='reference/stream27_context_storage_combo_oneshot_wrap.py'
BASE=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-oneshot-wrap-v1'
TOP='genefer_stream27_c2_oneshot_wrap_probe_v1'
CPP='rtl/tb/stream27_c2_oneshot_wrap.cpp'
PORT_ANCHOR=' output logic [1:0] waiting_final,output logic [63:0] final_image_rows);\n'
PORT_NEW=''' output logic [1:0] waiting_final,output logic [63:0] final_image_rows,
 output logic probe_cold_proposal,probe_cold_accept,probe_cold_context,
 output logic probe_second,probe_sent,probe_pending,
 output logic [31:0] probe_anchor,
 output logic [1:0] probe_seen,
 output logic [2:0] probe_cache_ready,
 output logic [95:0] probe_cache_owners);
'''
MONITOR=''' // Native-only continuous observation; no FF, acceptance or payload change.
 assign probe_cold_proposal=cold_correction;
 assign probe_cold_accept=child_correction_accept;
 assign probe_cold_context=cold_correction_context;
 assign probe_second=cold_second_correction;
 assign probe_sent=second_correction_sent;
 assign probe_pending=second_correction_pending;
 assign probe_anchor=anchor_cycle;
 assign probe_seen=engine.initial_correction_seen;
 assign probe_cache_ready={engine.arithmetic.field2.term_cache_ready,
  engine.arithmetic.field1.term_cache_ready,engine.arithmetic.field0.term_cache_ready};
 assign probe_cache_owners={5'd0,engine.arithmetic.field2.term_cache_owner,
  5'd0,engine.arithmetic.field1.term_cache_owner,5'd0,engine.arithmetic.field0.term_cache_owner};
'''
INSTRUMENT='''
static unsigned round_index=0,cold_accepts=0,aliases=0;
static std::array<unsigned,2> cold_by_context{};
static std::array<std::array<unsigned,2>,3> cache_counts{};
static bool negative_caught=false;
static void wrap_tick(DUT& d,unsigned age){
 // Actual protocol/frame time and watchdog remain monotone real-edge time.
 // Only the host timestamp is moved to the edge BEFORE its modulo alias.
 if(age==600||age==604||age==608){
  need(cold_accepts==2&&d.probe_sent&&!d.probe_pending&&d.probe_seen==3&&
       lane32(d.operations_started,1)>=2,"R6_WRAP_AFTER_GENUINE_COLD_AND_WARM");
  uint64_t k=1+(age-600)/4;
  d.cycles=(k<<32)+uint64_t(d.probe_anchor)+SECOND_CORRECTION-1;
 }
 d.clk=0;d.eval();
 bool alias=age==601||age==605||age==609;
 if(alias){
  need(uint32_t(d.cycles-d.probe_anchor)==SECOND_CORRECTION&&
       (d.cycles>>32)==1+(age-601)/4,"R6_ACTUAL_HOST_COUNTER_ALIAS");
  aliases++;
  if(OLD_PROPOSAL)need(d.probe_second&&!d.probe_cold_accept,"R6_OLD_PROPOSAL_STALE_OWNER");
  else need(!d.probe_second&&!d.probe_cold_proposal&&!d.probe_pending&&d.probe_sent,
            "R6_ONE_SHOT_NO_SECOND_TRANSACTION");
 }
 if(d.probe_cold_accept){
  need(d.probe_cold_proposal&&cold_accepts<2,"R6_EXTERNAL_ACCEPT_NOT_INTERNAL_FEEDBACK");
  unsigned c=d.probe_cold_context;cold_accepts++;cold_by_context[c]++;
  need(cold_by_context[c]==1,"R6_ONE_COLD_ACCEPT_PER_CONTEXT");
 }
 for(unsigned f=0;f<3;f++)if(d.probe_cache_ready&(1u<<f)){
  uint32_t tag=d.probe_cache_owners[f];unsigned c=(tag>>24)&1u;
  uint16_t expected_epoch=uint16_t(EPOCHS[c]+round_index*COUNTS[c]+cache_counts[f][c]);
  need((tag&255u)==round_index+1&&uint16_t(tag>>8)==expected_epoch&&
       cache_counts[f][c]<COUNTS[c],"R6_ACTUAL_TABLE_FULL_OWNER");
  cache_counts[f][c]++;
 }
 d.clk=1;d.eval();
 if(OLD_PROPOSAL&&alias){
  need(d.error&&!d.done&&!d.canonical_ready&&!d.read_valid&&cold_accepts==2,
       "R6_OLD_PROPOSAL_ACTUAL_ABORT");
  for(unsigned q=0;q<24;q++){clear(d);edge(d);
   need(d.error&&!d.done&&!d.canonical_ready&&!d.read_valid,"R6_OLD_ABORT_NO_PUBLICATION_TAIL");}
  negative_caught=true;
  std::cout<<"R6_OLD_PROPOSAL_WRAP_CAUGHT aliases=1 cold_accepts=2 actual_abort=1 publication=0 quiet_edges=24 simulation_only=1\\n";
 }
}
'''


def role(old=False):
    need=normal.need
    m,files,production=normal.role('aw8')
    before=copy.deepcopy(m)
    original=production['files'][production['top']+'.sv']
    host=normal.once(original,'module '+production['top']+' #','module '+TOP+' #')
    host=normal.once(host,PORT_ANCHOR,PORT_NEW)
    # Put hierarchical observation after all declarations, before the first FF.
    mark=' always_ff @(posedge clk or negedge rst_n)begin\n'
    host=normal.once(host,mark,MONITOR+mark)
    if old:
        host=normal.once(host,core.PROPOSAL_AFTER,core.PROPOSAL_BEFORE)
    reverse=host
    if old: reverse=normal.once(reverse,core.PROPOSAL_BEFORE,core.PROPOSAL_AFTER)
    reverse=normal.once(reverse,MONITOR,'')
    reverse=normal.once(reverse,PORT_NEW,PORT_ANCHOR)
    reverse=normal.once(reverse,'module '+TOP+' #','module '+production['top']+' #')
    need(reverse==original,'WRAP_MONITOR_AND_OLD_PROPOSAL_ONLY_REVERSE')
    oldhost='rtl/'+production['top']+'.sv'
    newhost='rtl/'+TOP+'.sv'
    files.pop(oldhost);files[newhost]=host.encode()
    m['build']['sv_sources']=[newhost if n==oldhost else n for n in m['build']['sv_sources']]
    m['build']['top']=TOP
    header='rtl/tb/s4_host_contexts_config_v1.h'
    text=files[header].decode().replace(production['top'],TOP)
    second=int(original.split('SECOND_CORRECTION=',1)[1].split(';',1)[0])
    files[header]=(text+f'constexpr unsigned SECOND_CORRECTION={second};\nconstexpr bool OLD_PROPOSAL={str(old).lower()};\n').encode()
    cpp=files[m['build']['cpp_source']].decode()
    cpp=normal.once(cpp,'static uint64_t owner(unsigned ctx){return (uint64_t(COUNTS[ctx]-1)<<24)|(uint64_t(uint16_t(EPOCHS[ctx]+COUNTS[ctx]-1))<<8)|1u;}',
        'static unsigned round_index;\nstatic uint64_t owner(unsigned ctx){return (uint64_t(COUNTS[ctx]-1)<<24)|(uint64_t(uint16_t(EPOCHS[ctx]+(round_index+1)*COUNTS[ctx]-1))<<8)|(round_index+1);}')
    cpp=normal.once(cpp,'static unsigned launched(',INSTRUMENT.replace('static unsigned round_index=0,cold_accepts=0,aliases=0;',
        'static unsigned cold_accepts=0,aliases=0;')+'\nstatic unsigned launched(')
    cpp=normal.once(cpp,'static void run(DUT& d){','static void run(DUT& d,bool reset_before){\n    cold_accepts=aliases=0;cold_by_context={};cache_counts={};')
    reset='    clear(d);d.clk=0;d.rst_n=0;d.eval();edge(d);need(!d.busy&&!d.done&&!d.canonical_ready&&!d.read_valid&&!d.error&&!d.operations_started&&!d.completed_squares,"S4_HOST_CONTEXT_RESET");d.clk=0;d.rst_n=1;d.eval();'
    cpp=normal.once(cpp,reset,'    if(reset_before){'+reset.strip()+'need(!d.probe_sent&&!d.probe_pending,"R6_RESET_CLEARS_SENT_PENDING");}\n    else need(!d.busy&&!d.error&&d.probe_sent&&!d.probe_pending,"R6_COMPLETED_PREVIOUS_JOB");')
    cpp=normal.once(cpp,'!d.error&&!d.read_valid&&!d.canonical_ready,"S4_HOST_CONTEXT_COLD_LOAD"',
                    '!d.error&&!d.read_valid&&!(d.canonical_ready&(1u<<ctx)),"S4_HOST_CONTEXT_COLD_LOAD"')
    cpp=cpp.replace('d.accepted_generation==0x0101','d.accepted_generation==0x0101*(round_index+1)')
    cpp=cpp.replace('unsigned(d.accepted_generation)==0x0101','unsigned(d.accepted_generation)==0x0101*(round_index+1)')
    cpp=normal.once(cpp,'"S4_HOST_CONTEXT_JOINT_START");','"S4_HOST_CONTEXT_JOINT_START");need(!d.probe_sent&&!d.probe_pending,"R6_NEWJOB_CLEARS_SENT_PENDING");')
    cpp=normal.once(cpp,'        edge(d);need(!d.error,"S4_HOST_CONTEXT_MODEL_ERROR age="+std::to_string(age));',
                    '        wrap_tick(d,age);if(negative_caught)return;need(!d.error,"S4_HOST_CONTEXT_MODEL_ERROR age="+std::to_string(age));')
    # The real warm wrapper resets launched/completed at accepted cold-frame
    # start, NOT host new-job acceptance. Preserve prior completed counters
    # before FIRST on the no-reset second job; require exact new counters after.
    cpp=normal.once(cpp,'lane32(d.operations_started,ctx)==launched(age,ctx)&&lane32(d.completed_squares,ctx)==completed(age,ctx)',
        'lane32(d.operations_started,ctx)==((round_index&&age<FIRST[ctx])?COUNTS[ctx]:launched(age,ctx))&&'
        'lane32(d.completed_squares,ctx)==((round_index&&age<FIRST[ctx])?COUNTS[ctx]:completed(age,ctx))')
    cpp=normal.once(cpp,'    std::cout<<"S4_HOST_CONTEXTS_PASS kind="',
        '    need(aliases==3&&cold_accepts==2&&cold_by_context[0]==1&&cold_by_context[1]==1&&d.probe_sent&&!d.probe_pending,"R6_WRAP_COUNTS_STATE");\n'
        '    for(unsigned f=0;f<3;f++)for(unsigned c=0;c<2;c++)need(cache_counts[f][c]==COUNTS[c],"R6_ONE_TABLE_EVENT_PER_TRUE_FRAME");\n'
        '    std::cout<<"S4_HOST_CONTEXTS_PASS kind="')
    cpp=normal.once(cpp,'run(d);return 0;',
        'round_index=0;run(d,true);if(negative_caught)return 0;round_index=1;run(d,false);round_index=0;run(d,true);'
        'std::cout<<"R6_WRAP_PASS wraps_per_job=3 jobs=3 cold_accepts=6 cache_events_per_field=51 reads=3072 newjob_clear=1 reset_clear=1 real_datapath_edges=1 simulation_only=1\\n";return 0;')
    files[CPP]=cpp.encode();m['build']['cpp_source']=CPP
    footer=before['steps'][0]['expected_stdout']
    need(footer.startswith('S4_HOST_CONTEXTS_PASS '),'CAPTURED_NORMAL_STDOUT')
    output=('R6_OLD_PROPOSAL_WRAP_CAUGHT aliases=1 cold_accepts=2 actual_abort=1 publication=0 quiet_edges=24 simulation_only=1\n' if old else
            footer*3+'R6_WRAP_PASS wraps_per_job=3 jobs=3 cold_accepts=6 cache_events_per_field=51 reads=3072 newjob_clear=1 reset_clear=1 real_datapath_edges=1 simulation_only=1\n')
    m['steps']=[dict(name='oneshot-wrap-old-proposal-negative' if old else 'oneshot-wrap-three-aliases',
                     argv=['{exe}'],expected_returncode=0,expected_stdout=output,expected_stderr='')]
    files['lineage/'+SELF]=(ROOT/SELF).read_bytes()
    m['sources']={n:normal.sha(raw) for n,raw in files.items()}
    m.update(source_root='UNBOUND',test_role='deliberate_fault' if old else 'normal')
    snapshot={n:pin for n,pin in m['sources'].items() if n.endswith('.sv')}
    m['rtl_readiness']=dict(schema='gfn16-candidate-rtl-ready-v1',
        candidate_id='s4-p16-c2-combo-r6-aw8-wrap-'+('old-proposal' if old else 'normal')+'-v3',
        source_snapshot=snapshot,
        candidate_source_sha256=normal.sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
        rtl_ready_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'))
    m['oneshot_wrap']=dict(normal_source_gate=normal.IDS['aw8'],n=256,three_counter_aliases=True,
        only_forced_value='host cycles64 public register',real_protocol_arithmetic_payload_owners_unchanged=True,
        monitor_only_ports=True,host_literal_reverse=True,old_proposal_only_mutant=old,
        cold_accept_not_proposal_or_internal_feedback=True,all_three_real_table_owner_sequences=True,
        admitted_normal_expected_images=True,newjob_and_reset_clear_checked=not old,
        simulation_fastforward_not_billions_of_edges=True,full_geometry_native_claim=False,promotion_allowed=False)
    return m,files,production


def prepare(old=False):
    from fpga.tools import candidate_ladder,native_class_package_v2 as package
    mode='old-proposal' if old else 'normal'
    out=BASE/('aw8-'+mode+'-v3')
    normal.need(not out.exists() and not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')),'WRAP_FRESH_UNPAUSED')
    m,files,_=role(old)
    source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    m['source_root']=str(source)
    normal.dump(out/'manifest.json',m);normal.dump(out/'host-hours.json',candidate_ladder.budget_from_hourly())
    variants=[]
    for pair in ('01','23'):
        profile='gcp-c4d-static'+pair+'-v1';worker='s4-p16-c2-combo-r6-aw8-wrap-'+mode+'-'+pair+'-v3'
        packet=out/('packet-'+pair)
        result=package.prepare(out/'manifest.json',source,profile,worker,'run',packet,out/'host-hours.json')
        ticket=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'],manifest_sha256=normal.sha((packet/'manifest.json').read_bytes()),
            worker_id=worker,profile=profile,native_root=ticket['native_root'],runner='tools/native_class_package_v2.py',
            runner_sha256=normal.sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=normal.sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/p),sha256=normal.sha((ROOT/p).read_bytes()))
                for p in ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    identity='s4-p16-c2-combo-r6-aw8-wrap-'+mode+'-q1-v3'
    logical=dict(schema='gfn16-global-ticket-v1',id=identity,owner='merged-ntt-model',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=4,minimum_ram_rationale='Bounded N256 timestamp-seam normal/negative; unchanged normal arithmetic geometry, preserve OOM/timeout.',
        allowed_hosts=['gfn16-pilot-c4d','aethia'],est_minutes=10,promotion_bound=False,
        test_role='deliberate_fault' if old else 'normal',rtl_readiness=m['rtl_readiness'],packages=variants,
        after=[normal.IDS['aw8']],on='PASS_expected_contracts')
    normal.dump(out/'global-ticket.json',logical)
    return dict(id=identity,ticket=str(out/'global-ticket.json'),status='PREPARED_NOT_NATIVE')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--old',action='store_true')
    args=parser.parse_args();print(json.dumps(prepare(args.old),indent=2))
