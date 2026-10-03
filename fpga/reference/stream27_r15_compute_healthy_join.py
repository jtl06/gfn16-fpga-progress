"""Own R15 compute60 source/native healthy calendar join, no native replay.

Reuses a pure scalar event function as arithmetic only. It never supplies
FIELD100 or other cohorts' execution, clock, fault, GL or host-I/O credit.
"""
import argparse
import json
from pathlib import Path
from fpga.reference import stream27_context_feedback12_model as arithmetic
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_compute_healthy_join.py'
CAPTURE='results/throughput-20260929/trackS-r15-compute-native-v1/full-normal-v2/production-bundle.json'
CAPTURE_PIN='079ea8523f4599bd521d3a3b3c513001b4e537912fb75ad5a2894447e4c7d428'
FLAGS=dict(FIXED_SCHEDULE=1,LEAN_BUILD=1,PROGRESS_WATCHDOG=1,STORAGE_TO_RAM=1,DIRECT_COLD=0,PCIE_SHELL=0)
K=1911814
JOBS={
 2:('s4-p16-c2-r15-compute-full-normal-q1-v1','normal-full-r15-compute-alone-and-joint','R84_C2_FULL_PASS '),
 100:('s4-p16-c2-r15-compute-own100-serial-q1-v1','normal-full-r15-compute-own100-percontext','R84_C2_THREAD100_PASS '),
 1000:('s4-p16-c2-r15-compute-continuous1000-q1-v1','normal-full-r15-compute-own1000-percontext','R84_C2_THREAD100_PASS '),
}


def source():
    raw=(ROOT/CAPTURE).read_bytes();need(sha(raw)==CAPTURE_PIN,'R15_LEDGER_OWN_CAPTURE')
    b=json.loads(raw);g=b['geometry'];contract=b['r15_all']
    need(len(b['files'])==60 and {n:sha(t.encode()) for n,t in b['files'].items()}==b['generated_sha256'] and
         contract['source_ready'] and contract['flags']==FLAGS and contract['healthy_internal_latency_delta']==0 and
         contract['internal_compute_geometry']==g,'R15_LEDGER_OWN60_SOURCE_FLAGS_CALENDAR')
    need(tuple(g[k] for k in ('n','p','warm_interval','pointwise_accept','sink_accept','first_digit','carry_done',
         'correction_cache_latency','term_seed_first','term_seed_last'))==(65536,16,8461,4207,8417,8459,12558,78,71,74),
         'R15_LEDGER_OWN_COMPUTE_GEOMETRY')
    need(all(b['parameters'].get(k)==v for k,v in FLAGS.items()),'R15_LEDGER_COMPILED_FLAG_ROSTER')
    pins={p:b['source_sha256'][p] for p in ('reference/stream27_r15_all_bind.py',
       'reference/stream27_r15_fixed_schedule_bind.py','reference/stream27_r15_lean_watchdog_bind.py',
       'reference/stream27_r15_storage_ram_bind.py','rtl/kernel/genefer_stream27_r15_progress_watchdog_v1.sv')}
    for p,pin in pins.items():need(sha((ROOT/p).read_bytes())==pin,'R15_LEDGER_FROZEN_SOURCE:'+p)
    return b,pins


def calendar(g,count,special=(False,False)):
    return arithmetic.event_calendar(g,count,special=special)


def native(b,count):
    id,step,prefix=JOBS[count];e=ROOT/'queue/evidence'/id;n=e/'attempt-0/collected/output/native'
    gp,rp,mp,lp=e/'gate-receipt.json',n/'report.json',n/'approved-manifest.json',n/(step+'.log')
    gate,r,m=[json.loads(p.read_bytes()) for p in (gp,rp,mp)]
    need(gate['status']=='PASS_expected_contracts' and gate['manifest_sha256']==sha(mp.read_bytes())==r['manifest_sha256'] and
         gate['report_sha256']==sha(rp.read_bytes()),'R15_LEDGER_ACTUAL_TYPED_RECEIPT')
    need(len(m['build']['sv_sources'])==61 and m['build']['parameters']==dict(b['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),
         'R15_LEDGER_ACTUAL61_COMPILED_PARAMETERS')
    for name,pin in b['generated_sha256'].items():
        need(m['sources']['rtl/'+name]==pin==r['sources']['rtl/'+name] and 'rtl/'+name in m['build']['sv_sources'],
             'R15_LEDGER_ALL60_COMPILED:'+name)
    build=[s for s in r['steps'] if s['name']=='build']
    need(len(build)==1 and build[0]['returncode']==0 and
         all('-G'+k+'='+str(v) in build[0]['command'] for k,v in m['build']['parameters'].items()),'R15_LEDGER_BUILD_ARGV')
    need(r['artifacts'][step+'.log']==sha(lp.read_bytes()),'R15_LEDGER_LOG_RECEIPT_PIN')
    text=lp.read_text();need(text.startswith(prefix) and len(text.splitlines())==1,'R15_LEDGER_RAW_FOOTER')
    v=json.loads(text.removeprefix(prefix));c=calendar(b['geometry'],count)
    need(v['interval']==8461 and v['warm_edges']==c['warm_edges'] and v['done_edges']==c['publication_edges'] and
         v['joint_cycles']==c['full_read_completion_cycles'] and v['setup_edges']==[99,199] and
         v['launches']==[[first+j*8461 for j in range(count)] for first in c['first_edges']],
         'R15_LEDGER_EVERY_OWN_LAUNCH_WARM_PUBLICATION')
    need(v['signed96'] is True and v['independent_reference'] is True and v['model_threads']==1 and
         v['bases']==[604832956,999999937] and v['peer_live_reads']==65536,'R15_LEDGER_OWN_REFERENCE_SCOPE')
    if count==2:
        need(v['squares']==8 and v['reads']==393216 and v['context_alone_bit_identical'] is True and
             v['single_cycles']==[746125,746125],'R15_LEDGER_ALONE_JOINT')
    else:
        need(v['count_per_context']==count and v['squares']==2*count and v['descriptors']==2*(count-1) and
             v['reads']==262144 and v['initial_resets']==1 and v['initial_load_words']==131072,
             'R15_LEDGER_UNINTERRUPTED_SOURCE_OWN_COUNT')
    return dict(id=id,gate_sha256=sha(gp.read_bytes()),report_sha256=sha(rp.read_bytes()),
      manifest_sha256=sha(mp.read_bytes()),log_name=step+'.log',log_sha256=sha(lp.read_bytes()),
      compiled_parameters=m['build']['parameters'],measurements=v,calendar=c)


def close(counts=(2,)):
    need(tuple(counts) in ((2,),(2,100),(2,100,1000)),'R15_LEDGER_FINITE_JOIN_ROSTER')
    b,pins=source();cal={str(k):calendar(b['geometry'],k) for k in (2,100,1000,K)}
    need(cal[str(K)]['pair_completion_cycles']==16177181485,'R15_LEDGER_SOURCE_DERIVED_HEALTHY_PAIR')
    return dict(schema='r15-own-compute-source-native-healthy-ledger-v1',status='OWN_SOURCE_NATIVE_'+('_'.join(map(str,counts)))+'_JOIN_PASS',
      producer=dict(path=SELF,sha256=sha((ROOT/SELF).read_bytes())),
      production=dict(top=b['top'],sv_count=60,bundle=dict(path=CAPTURE,sha256=CAPTURE_PIN),
        generated_sha256=b['generated_sha256'],source_pins=pins,flags=FLAGS),
      jobs={str(k):native(b,k) for k in counts},calendars=cal,sample=cal[str(K)],
      native100_pending=100 not in counts,native1000_pending=1000 not in counts,
      selected_period_ns=None,projected_pair_seconds=None,projected_amortized_seconds=None,promotion_allowed=False,
      scopes=['Own lean compute60 ordinary equal-K1911814 timely-feed internal pair only; host GL assumed (unimplemented).',
        'Own finite outputs/source parameters/launch-warm-publication ledger mechanically joined, without numeric replay.',
        'Scalar function arithmetic only; conditional model/sample flags preserved, full sample not measured.',
        'Includes setup/canonical/PUB1/copyN+4; external scalar LOAD/readback, DIRECT cold transport, host finalization excluded.',
        'Special minus-one adds N per affected job. No individual latency, hardware/PrimeGrid, clock, PCIe/CDC, GL/rollback or protected-fault claim.',
        'Fresh protected twin/PRP/wrap/minimal framing faults/own1000/reviews and physical/advisor remain distinct gates.'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--counts',choices=('2','2,100','2,100,1000'),default='2')
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve()
    need(out.is_relative_to(ROOT) and not out.exists(),'R15_LEDGER_FRESH_ADDITIVE_OUTPUT')
    value=close(tuple(map(int,a.counts.split(','))));out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(path=str(out),sha256=sha(out.read_bytes()),status=value['status'],pair_cycles=value['sample']['pair_completion_cycles'],period_ns=None)))
