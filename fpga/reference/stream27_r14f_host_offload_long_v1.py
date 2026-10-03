"""R14-F ON-only continuous pilot; exact matched source, no inherited forecast."""
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r14f_host_offload_long_v1.py'
CPP='rtl/tb/stream27_r14f_host_offload_long_v1.cpp'
HEADER='rtl/tb/s4_p16_two_context_full_config.h'
DONOR=ROOT/'results/throughput-20260929/trackS-r14f-host-offload-equivalence-v1/full-normal-v1'
DONOR_PIN='3e5e07da3cb16ca7b1d9e96aa58857f833450a6234d8e9b1dfca77abd05322e2'
GATE='s4-r14f-b-equivalence-full-normal-q1-v1'
ID='s4-r14f-host-offload-own100-q1-v1'
BASE=ROOT/'results/throughput-20260929/trackS-r14f-host-offload-ownlong-v1'
def need(ok,why):
    if not ok:raise ValueError('R14F_LONG_'+why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def once(text,old,new):
    need(text.count(old)==1,'ANCHOR:'+old);return text.replace(old,new,1)
def bits(count):
    need(type(count) is int and count in (100,1000),'COUNT')
    rows=[]
    for c,seed in enumerate((0x1732f5a9,0x7b28c361)):
        row=[c];s=seed
        for _ in range(1,count):
            s^=(s<<13)&0xffffffff;s^=s>>17;s^=(s<<5)&0xffffffff;row.append(s&1)
        rows.append(row)
    return rows
def config(count=100):return dict(count=count,threads=1,interval=8461,carry_done=12558,first=[204,4434],n=65536)
def validate(stdout,stderr,returncode,config,assets):
    count=config.get('count');need(config==globals()['config'](count) and assets=={},'CONFIG')
    need(returncode==0 and stderr=='' and stdout.startswith('R14F_LONG_PASS ') and stdout.endswith('\n') and '\n' not in stdout[:-1],'TYPED_NORMAL')
    value=json.loads(stdout[len('R14F_LONG_PASS '):]);warm=[x+(count-1)*8461+12559 for x in (204,4434)];done=[x+2 for x in warm]
    fixed=dict(count=count,squares=count*2,descriptors=2*(count-1),doubles=sum(map(sum,bits(count))),
        input_words=2*(3*65536+96),raw_words=2*(65536+32),checked_words=131072,initial_resets=1,model_threads=1,
        cycles=done[1],warm_edges=warm,done_edges=done)
    dynamic={'overlap_edges','reference_seconds','model_seconds','seconds'}
    need(set(value)==set(fixed)|dynamic and all(type(value[k]) is type(v) and value[k]==v for k,v in fixed.items()),'EXACT_VALUE_CALENDAR')
    need(type(value['overlap_edges']) is int and 0<value['overlap_edges']<done[0],'ACTUAL_OVERLAP')
    need(all(type(value[k]) in (int,float) and math.isfinite(value[k]) and 0<value[k]<10450 for k in dynamic-{'overlap_edges'}),'FINITE_PHASES')
    need(abs(value['reference_seconds']+value['model_seconds']-value['seconds'])<.05,'PHASE_SUM')
    return dict(status='PASS_expected_contracts',measurements=value,actual_ON_only=True,
        all_N_host_finalized_words_against_independent_reference=True,uninterrupted_descriptors=True,
        full_twins_equivalence_separate=GATE,host_phase_excluded_from_FPGA=True,promotion_allowed=False)
def role(count=100):
    from fpga.reference import stream27_host_offload_field100_v1 as chip
    raw=(DONOR/'manifest.json').read_bytes();need(sha(raw)==DONOR_PIN,'FROZEN_FULL_DONOR')
    m=json.loads(raw);files={n:(DONOR/'source/fpga'/n).read_bytes() for n in m['sources']}
    b=chip.prepare(65536,host_offload=1)
    need(len(b['files'])==66 and all(m['sources']['rtl/'+n]==pin for n,pin in b['generated_sha256'].items()),'ALL66_SOURCE_MATCH')
    top=b['top'];old=m['build']['top'];h=files[HEADER].decode()
    need(h.count(old)==2,'MODEL_ALIAS');h=h.replace(old,top)
    h=once(h,'COUNT=2,INTERVAL',f'COUNT={count},INTERVAL')
    h=once(h,'MAX_EDGES=3*11ull*N+100000','MAX_EDGES=COUNT*uint64_t(INTERVAL)+CARRY_DONE+10000')
    h=once(h,'BITS[2][2]={{0,1},{1,0}}','BITS[2][COUNT]={'+','.join('{'+','.join(map(str,r))+'}' for r in bits(count))+'}')
    files[HEADER]=h.encode();files[CPP]=(ROOT/CPP).read_bytes();files[SELF]=(ROOT/SELF).read_bytes()
    need(files[CPP].decode().index('gfn16_runtime::configure(context,argc,argv)')<files[CPP].decode().index('DUT d(&context)'),'RUNTIME_FIRST')
    m['build'].update(top=top,cpp_source=CPP,sv_sources=['rtl/'+n for n in b['files']],runtime_threads=1)
    m['steps']=[dict(name=f'r14f-host-offload-own{count}-continuous',argv=['{exe}'],expected_returncode=0,
        validator=dict(source=SELF,function='validate',config=config(count),assets={}))]
    m['sources']={n:sha(v) for n,v in files.items()};m['source_root']='UNBOUND';m['output_parent']='UNBOUND'
    m.pop('r14f_b_equivalence',None)
    m['r14f_own_long']=dict(normal_gate=GATE,production66_unchanged=True,passive_twin_removed=True,
        count_per_context=count,initial_resets=1,no_reload=True,host_C_cold_final=True,independent_NTT_reference=True,
        original_canonical_publication_ledger_NOT_used=True,raw_done_warm_plus=2,own_runtime_unmeasured=True)
    snapshot={'rtl/'+n:p for n,p in b['generated_sha256'].items()}
    m['rtl_readiness']=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=ID,source_snapshot=snapshot,
        candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),rtl_ready_at_utc='2026-10-03T03:10:21Z')
    return m,files
def dump(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2);f.write('\n')
def prepare():
    from fpga.tools import candidate_ladder,native_class_package_v2 as package
    out=BASE/'own100-v1';need(not out.exists() and not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')),'FRESH_UNPAUSED')
    m,files=role();source=out/'source/fpga';source.mkdir(parents=True)
    for n,raw in files.items():
        p=source/n;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    m['source_root']=str(source.resolve());dump(out/'manifest.json',m);dump(out/'host-hours.json',candidate_ladder.budget_from_hourly());variants=[]
    for pair in ('01','23'):
        profile='gcp-c4d-static'+pair+'-v1';worker='s4-r14f-own100-'+pair+'-v1';packet=out/('packet-'+pair)
        result=package.prepare(out/'manifest.json',source,profile,worker,'run',packet,out/'host-hours.json');ticket=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],ticket_sha256=result['ticket_sha256'],
            manifest_sha256=sha((packet/'manifest.json').read_bytes()),worker_id=worker,profile=profile,native_root=ticket['native_root'],
            runner='tools/native_class_package_v2.py',runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/n),sha256=sha((ROOT/n).read_bytes())) for n in ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    logical=dict(schema='gfn16-global-ticket-v1',id=ID,owner='stream-interface',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        priority='P1',kind='sim',needs='verilator',tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',allowed_hosts=['gfn16-pilot-c4d'],
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=8,
        minimum_ram_rationale='Own ON-only full-N100 pilot: no twin or parent runtime forecast; finite OOM/timeout preserved.',
        est_minutes=45,promotion_bound=False,test_role='normal',rtl_readiness=m['rtl_readiness'],packages=variants,after=[GATE],on='PASS_expected_contracts')
    dump(out/'global-ticket.json',logical);return dict(id=ID,ticket=str(out/'global-ticket.json'),status='SOURCE_READY_NOT_SUBMITTED')
if __name__=='__main__':print(json.dumps(prepare(),indent=2))
