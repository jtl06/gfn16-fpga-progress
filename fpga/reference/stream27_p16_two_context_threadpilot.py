"""Own R84 C2 source/thread100 pilot; no C1 duration or clock inherited.

The production53 RTL files and zero-edge native observer stay byte-identical
to the collected two-base normal. Only native count/feed/program/threading
change; all100 launches per context, FIFO admission and final signed96 words
are checked on the worker. No full-N arithmetic executes in this preparer.
"""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_p16_two_context_threadpilot.py'
CPP='rtl/tb/stream27_p16_two_context_threadpilot.cpp'
COUNT=100
NORMAL_CPP_PIN='d5d3978374dcaa3b5d30f6ef87d8e5432ef936d3c510b597949a39aa553df897'
READY='2026-10-02T03:17:02Z'
BASES=[604832956,999999937]
def need(ok,why):
    if not ok:raise ValueError('R84_THREAD100_'+why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def dump(path,v):
    with Path(path).open('x') as f:json.dump(v,f,indent=2);f.write('\n')
def bits():
    result=[]
    for ctx,seed in enumerate((0x1732f5a9,0x7b28c361)):
        row=[ctx];state=seed
        for k in range(1,COUNT):
            state^=(state<<13)&0xffffffff;state^=state>>17;state^=(state<<5)&0xffffffff
            row.append(state&1)
        result.append(row)
    return result

def calendar(g):
    """Own finite100-frame port proof, not the frozen model's16-frame cap."""
    from fpga.reference import s4_two_context_model_v1 as ports
    interval=g['warm_interval'];offset=interval//2;rows=g['rows']
    need(interval==8459 and g['first_digit']+1==interval and g['feedback_delay']==0,'DIRECT_FEEDBACK_ALIGNMENT')
    frames=sorted([ports.Frame(c,1,((65534,42)[c]+k)&65535,k,k*interval+c*offset,BASES[c])
        for c in (0,1) for k in range(COUNT)],key=lambda f:f.start)
    for label,first,width in (('INPUT',0,rows),('PW',g['pointwise_accept'],rows),
            ('SINK',g['sink_accept'],rows),('DIGIT',g['first_digit'],rows),
            ('CARRY',g['sink_accept'],g['carry_done']-g['sink_accept']+1)):
        ports.disjoint([(f.start+first,f.start+first+width-1,f.tag) for f in frames],label)
    corrections=ports.correction_calendar(frames,g,pair_interval=g['correction_pair_interval'])
    live={};peak=0;allocation=[]
    for f in frames:
        live={b:old for b,old in live.items() if old.start+g['last_sink']>=f.start}
        free=[b for b in range(4) if b not in live];need(bool(free),'PREEDGE_FOUR_LEASE_CAPACITY')
        bank=free[0];live[bank]=f
        peak=max(peak,len(live));allocation.append([f.context,f.ordinal,f.start,bank])
    # For all rows r: predecessor FIRST_DIGIT+1+r == next INPUT+r.
    # The exact same-context I therefore gives direct bypass with no queue.
    return dict(status='PASS_SOURCE_EDGE_MODEL_ONLY',frames=2*COUNT,per_context_interval=interval,
        launch_gaps=[offset,interval-offset],window_widths=dict(input=rows,pw=rows,sink=rows,digit=rows,
            carry=g['carry_done']-g['sink_accept']+1),correction_pair_interval=g['correction_pair_interval'],
        correction=corrections,lease_allocation=allocation,lease_peak=peak,
        feedback_peak_rows=[0,0],feedback_identity='previous_start+FIRST_DIGIT+1+r == next_start+r for every0<=r<T',
        full_N_numeric_performed=False,physical_or_runtime_forecast=False)

MAIN=r'''int main(int argc,char**argv){try{
 VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d{&context};
 if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
 need(argc==1&&gfn16_runtime::matches(context,d),"R84_THREAD100_ARGUMENTS_THREADS");
 auto begin=std::chrono::steady_clock::now();s4_full_reference::self_check();
 std::array<Image,2> input={initial(0),initial(1)},reference=input;
 unsigned doubles=0;
 for(unsigned ctx=0;ctx<2;ctx++)for(unsigned k=0;k<COUNT;k++){
  reference[ctx]=s4_full_reference::square(reference[ctx],BASES[ctx],BITS[ctx][k]);doubles+=BITS[ctx][k];
 }
 need(reference[0]!=reference[1]&&reference[0][0]!=-1&&reference[1][0]!=-1,"R84_THREAD100_DISTINCT_ORDINARY_REFERENCE");
 const auto reference_end=std::chrono::steady_clock::now();
 Result joint=run(d,3,input,reference);
 need(joint.launches[0].size()==COUNT&&joint.launches[1].size()==COUNT&&joint.descriptors==2*(COUNT-1),"R84_THREAD100_ALL_LAUNCHES_DESCRIPTORS");
 auto end=std::chrono::steady_clock::now();
 std::cout<<"R84_C2_THREAD100_PASS {\"aw\":16,\"p\":16,\"contexts\":2,\"bases\":["<<BASES[0]<<","<<BASES[1]
  <<"],\"count_per_context\":"<<COUNT<<",\"squares\":"<<2*COUNT<<",\"descriptors\":"<<joint.descriptors
  <<",\"doubles\":"<<doubles<<",\"reads\":"<<joint.reads<<",\"signed96\":true,\"independent_reference\":true,\"initial_resets\":1,\"initial_load_words\":"<<2*N
  <<",\"interval\":"<<INTERVAL<<",\"peer_live_reads\":"<<joint.peer_reads<<",\"model_threads\":"<<d.threads()<<",\"launches\":[";
 for(unsigned c=0;c<2;c++){if(c)std::cout<<",";std::cout<<"[";for(unsigned k=0;k<COUNT;k++){if(k)std::cout<<",";std::cout<<joint.launches[c][k];}std::cout<<"]";}
 std::cout<<"],\"joint_cycles\":"<<joint.cycles<<",\"overlap_edges\":"<<joint.overlap
  <<",\"done_edges\":["<<joint.done[0]<<","<<joint.done[1]<<"],\"warm_edges\":["<<joint.warm[0]<<","<<joint.warm[1]
  <<"],\"setup_edges\":["<<joint.setup[0]<<","<<joint.setup[1]<<"],\"reference_seconds\":"<<std::chrono::duration<double>(reference_end-begin).count()
  <<",\"model_seconds\":"<<std::chrono::duration<double>(end-reference_end).count()<<",\"seconds\":"<<std::chrono::duration<double>(end-begin).count()<<"}\n";
 d.final();return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
'''

def driver(raw):
    text=raw.decode();start=text.index('int main(int argc,char**argv)')
    text=text[:start]+MAIN
    changes=[
      (' uint64_t cycles=0,reads=0,overlap=0,peer_reads=0;',
       ' uint64_t cycles=0,reads=0,overlap=0,peer_reads=0,descriptors=0;'),
      (' clear(d);d.start_contexts=d.batch_mode=mask;',
       ' clear(d);d.start_contexts=d.batch_mode=d.feed_mode=mask;'),
      (' d.double_mask=uint64_t(BITS[0][1]<<1)|(uint64_t(BITS[1][1]<<1)<<32);',' d.double_mask=0;'),
      (' std::array<uint64_t,2> first{};',
       ' std::array<uint64_t,2> first{};std::array<unsigned,2> next_command={1,1};'),
      ('  clear(d);int selected=-1;unsigned address=0;',
       '''  clear(d);int selected=-1;unsigned address=0;
  const unsigned command_ctx=unsigned(age&1u);
  if(next_command[command_ctx]<COUNT){
   d.command_context=command_ctx;d.command_valid=1;d.command_generation=1;
   d.command_index=next_command[command_ctx];d.command_double=BITS[command_ctx][next_command[command_ctx]];
  }'''),
      ('  edge(d);need(!d.error,"R84_ACTUAL_C2_ERROR age="+std::to_string(age));',
       '''  d.clk=0;d.eval();const bool accepted_command=d.command_accept;
  d.clk=1;d.eval();d.clk=0;d.eval();
  if(accepted_command){next_command[command_ctx]++;result.descriptors++;}
  need(!d.error,"R84_ACTUAL_C2_ERROR age="+std::to_string(age));'''),
      ('  need(!d.command_accept&&!d.operation_accept&&!d.feed_level,"R84_MASK_MODE_NO_FEED");',
       '  need((d.feed_level&7u)<=4&&((d.feed_level>>3)&7u)<=4,"R84_THREAD100_FIFO_CAPACITY");'),
      (' need(result.cycles>0&&!d.busy,"R84_BOUNDED_ACTUAL_COMPLETION");',
       ''' need(result.cycles>0&&!d.busy&&!d.feed_level,"R84_BOUNDED_ACTUAL_COMPLETION");
 for(unsigned c=0;c<2;c++)need(next_command[c]==COUNT,"R84_THREAD100_ALL_DESCRIPTORS_ACCEPTED");''')]
    for a,b in changes:need(text.count(a)==1,'EXACT_NORMAL_DRIVER_SITE');text=text.replace(a,b,1)
    return text

def config():return dict(aw=16,p=16,contexts=2,bases=BASES,count=COUNT,threads=8,doubles=sum(map(sum,bits())))
def validate(stdout,stderr,rc,config,assets):
    need(config==globals()['config']() and assets=={},'CONFIG')
    need(type(rc) is int and rc==0 and stderr=='' and stdout.startswith('R84_C2_THREAD100_PASS '),'TYPED_OUTPUT')
    v=json.loads(stdout.removeprefix('R84_C2_THREAD100_PASS '))
    expected=dict(aw=16,p=16,contexts=2,bases=BASES,count_per_context=COUNT,squares=2*COUNT,
        descriptors=2*(COUNT-1),doubles=config['doubles'],reads=4*65536,signed96=True,independent_reference=True,
        initial_resets=1,initial_load_words=2*65536,interval=8459,peer_live_reads=65536,model_threads=8)
    variables={'launches','joint_cycles','overlap_edges','done_edges','warm_edges','setup_edges','reference_seconds','model_seconds','seconds'}
    need(set(v)==set(expected)|variables and all(v[k]==x and type(v[k]) is type(x) for k,x in expected.items()),'EXACT_LONG_NUMERIC_COUNTS')
    need(stdout.endswith('\n') and '\n' not in stdout[:-1],'ONE_FOOTER')
    for name in ('launches','done_edges','warm_edges','setup_edges'):
        need(type(v[name]) is list and len(v[name])==2,'EDGE_PAIR')
    a,b=v['launches'];need(all(type(row) is list and len(row)==COUNT and all(type(x) is int and x>0 for x in row) for row in (a,b)),'ALL_LAUNCH_EDGES')
    need(b[0]-a[0]==4229 and all(row[k]-row[k-1]==8459 for row in (a,b) for k in range(1,COUNT)),'ALL_PAIR_LEASE_CALENDAR')
    need(all(type(v[name][c]) is int and v[name][c]>0 for name in ('done_edges','warm_edges','setup_edges') for c in (0,1)),'MEASURED_EDGES')
    need(all(v['warm_edges'][c]==v['launches'][c][-1]+12558 and v['setup_edges'][c]<v['launches'][c][0]
        and v['done_edges'][c]>v['warm_edges'][c]+10*65536 for c in (0,1)),'FINAL_PUBLICATION')
    need(type(v['joint_cycles']) is int and max(v['done_edges'])+65536<=v['joint_cycles']<COUNT*8459+33*65536+100000,'SIMULATED_EDGE_BOUND')
    need(type(v['overlap_edges']) is int and v['overlap_edges']>0,'ACTUAL_OVERLAP')
    need(all(type(v[k]) in (int,float) and math.isfinite(v[k]) and 0<v[k]<1800 for k in ('reference_seconds','model_seconds','seconds')),'MEASURED_FINITE_PHASES')
    need(abs(v['reference_seconds']+v['model_seconds']-v['seconds'])<0.05,'PHASE_SUM')
    return dict(status='PASS_expected_contracts',measurements=v,promotion_allowed=False,
        scope='Own source/thread100 percontext pilot with unchanged C2RTL, distinctbases, real FIFO feed and all final signed96; not1000/PRP/clock/wholeRAM qualification.')

def role():
    from fpga.reference import stream27_p16_two_context_full_native as normal
    m,files=normal.role();need(COUNT==100,'FINITE_OWN100_PILOT')
    need(sha(files[normal.CPP])==NORMAL_CPP_PIN,'EXACT_COLLECTED_NORMAL_CPP_DONOR')
    files[CPP]=driver(files[normal.CPP]).encode()
    header=files[normal.HEADER].decode()
    header=header.replace('COUNT=2,INTERVAL','COUNT=100,INTERVAL',1).replace('MAX_EDGES=3*11ull*N+100000','MAX_EDGES=COUNT*uint64_t(INTERVAL)+3*11ull*N+100000',1)
    first=header.index('BITS[2][2]=');header=header[:first]+'BITS[2][COUNT]={'+','.join('{'+','.join(map(str,row))+'}' for row in bits())+'};\n'
    files[normal.HEADER]=header.encode();files[SELF]=(ROOT/SELF).read_bytes()
    m['build']['cpp_source']=CPP;m['build'].pop('runtime_threads',None)
    m['steps']=[dict(name='normal-full-c2-own100-percontext-threadpilot',argv=['{exe}'],expected_returncode=0,
        validator=dict(source=SELF,function='validate',config=config(),assets={}))]
    m['sources']={name:sha(raw) for name,raw in files.items()}
    m['test_role']='normal';m['r84']['comparison']='One reset/load joint100/ctx, independent native fullreference/final signed96; no C1 timing donor.'
    m['r84']['own100_calendar']=calendar(m['r84']['geometry'])
    m['r84']['native_thread_pilot']=dict(count=COUNT,threads=8,feed_mode=True,own_duration_required=True,
        reference_cpu_seconds_in_forecast=False,baseline_C1_forecast_used=False,normal_donor_cpp_sha256=sha(files[normal.CPP]))
    snapshot={name:sha(raw) for name,raw in files.items() if name.endswith('.sv')}
    m['rtl_readiness']=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-p16-c2-explicit-own100-threadpilot-v1',
        source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),rtl_ready_at_utc=READY)
    return m,files

def prepare(output):
    from fpga.tools import native_threaded_wide_package_v3 as package
    from fpga.tools import native_thread_config_v1 as runtime
    from fpga.tools import global_queue_v1 as queue
    need(READY!='SOURCE_NOT_YET_FROZEN','SOURCE_FREEZE_REQUIRED')
    out=Path(output).resolve();need(out.is_relative_to(ROOT) and not out.exists(),'FRESH_OUTPUT')
    need(not any((ROOT/n).exists() for n in ('docs/briefs/PAUSE','queue/PAUSE')),'PAUSE')
    original,files=role();source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    variants=[]
    # One exact eight-core variant. The prior optional dual-wide submission
    # was rejected before claim on functional identity; its packets remain.
    for group in ('815',):
        profile_id='azure-burst16-thread-wide'+group+'-v1';profile=package.runtime().profile(profile_id)
        m=deepcopy(original);m['build']=runtime.configure_build(m['build'],8);m['probe']['expected_json']=runtime.expected_probe(8)
        contract={key:deepcopy(original[key]) for key in ('build','probe','steps','sources')}
        m['wide_thread_pilot']=dict(schema='gfn16-fixed-wide-thread-pilot-role-v1',thread_count=8,fixed_profile=profile_id,
            placement=profile['fixed_placement'],purpose='R84 OWN distinct-base C2 interrupted-free100/ctx source/threadpilot',
            serial_contract=contract,serial_contract_sha256=sha(json.dumps(contract,sort_keys=True,separators=(',',':'),allow_nan=False).encode()))
        manifest=out/('manifest-'+group+'.json');dump(manifest,m)
        reference=queue.provider_capture_ref()
        descriptor=package.meter().make_budget(profile['host'],3715,str(Path(reference['path']).relative_to(ROOT)),reference['sha256'],
            package.source_identity(m),profile['hardware_profile_sha256'],
            transition_path='results/throughput-20260929/azure-sim-resize-r49-v1/rate-transition-v1.json',
            transition_sha256='c4923266e1fabaeeca7cbf6e5f2444455c299accf5ed89c122927c47ed56ac92')
        budget=out/('budget-'+group+'.json');dump(budget,descriptor)
        packet=out/('packet-'+group);worker='s4-p16-c2-explicit-own100-wide'+group+'-v1'
        r=package.prepare(manifest,source,profile_id,worker,'run',packet,budget)
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
            manifest_sha256=sha((packet/'manifest.json').read_bytes()),worker_id=worker,profile=profile_id,native_root=r['native_root'],
            runner='tools/native_threaded_wide_package_v3.py',runner_sha256=sha((ROOT/'tools/native_threaded_wide_package_v3.py').read_bytes()),
            stager=str(ROOT/'tools/native_threaded_wide_stage_v3.py'),stager_sha256=sha((ROOT/'tools/native_threaded_wide_stage_v3.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/n),sha256=sha((ROOT/n).read_bytes())) for n in ('tools/native_threaded_wide_stage_v1.py','tools/native_package_v3.py','tools/native_package_v2.py')],
            max_seconds=3700,placement=profile['fixed_placement']))
    q=dict(schema='gfn16-global-ticket-v1',id='s4-p16-c2-explicit-own100-threadpilot-q2-v1',owner='merged-ntt-model',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
        tool_identity='azure-burst16-verilator5032-gcc13-python312-v1',resources=dict(cores=8,threads=8,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=8,minimum_ram_rationale='Bounded OWN source/thread100 pilot, no8thread C2 memory/time inherited.',
        est_minutes=35,promotion_bound=False,test_role='normal',rtl_readiness=original['rtl_readiness'],packages=variants,
        after=['s4-p16-c2-explicit-full-normal-q2-v1'],on='PASS_expected_contracts')
    dump(out/'global-ticket.json',q)
    return dict(id=q['id'],ticket=str(out/'global-ticket.json'),status='prepared_not_native')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(prepare(a.output),indent=2))
