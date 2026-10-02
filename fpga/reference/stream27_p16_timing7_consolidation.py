"""Read-only timing7 P16 promotion metadata; no numerical/native rerun.

The original partial snapshot stays immutable. A terminal --delta-for appends
only the later source-matched1000 evidence; selected clock remains separate.
"""
import argparse
from decimal import Decimal
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1]
COMMON='reference/stream27_p16_diet_consolidation.py'
COMMON_PIN='dbcd884316fe552319d1fc73d27fad0c10e8f6c5f5c0e9d0e02e39303307732d'
FIT='queue/standing-fit-state/terminal/s4-p16-timing-whole-9000-high-effort-v1'
FIT_RECEIPT='2d4b20bac40bda37a35a03dec7eecb88eb625ca7fd39a9afefefe65f95508b0e'
FIT_ARCHIVE='40847903bb1e8bc3245c7c63c7056601dc05618e447878ffc7499547a8107da1'
FIT_MANIFEST='2bc778183dcb2e4fd0e98726839edfda4a60aad76155607b35814a013ce0cf76'
TOP='genefer_stream27_host_chain_aw16_p16_diet_v1_descriptor_ff_v1_timing_r75_v1_term_select_v1.sv'
TOP_PIN='0011468ec67d7ca7ebb86fac88103fd19ea0207dc75685289da64d508228ea28'
FLAGS=dict(BOUNDARY_INPUTREG=1,DESCRIPTOR_FIFO_FF=1,QUARANTINE_REPLICAS=1,
    FINAL_GS_INPUTREG=1,CANONICAL_LOCALBASE=1,CARRY_LOCALBASE=1,TERM_SELECT_TOKEN=1)
PARAMETERS=dict(AW=16,P=16,CONTEXTS=1,EPOCH_SEED=65534,CORR_SERIAL_BFS=2,
    COMM_STAGE_SHARED_MLAB=1,MONT_FACTORED=1,CANONICAL_PIPE_STAGES=1,**FLAGS)
JOBS=dict(full9_two_stopped_jobs='s4-aw16-p16-timing-host-normal-q1-v1',
    eight_small_prps='s4-p16-timing7-eight-prp-normal-q1-v1',
    cold_short='s4-p16-timing7-short-normal-q1-v1',
    serial_continuous100='s4-p16-timing7-continuous100-normal-q1-v1',
    aw8_dense_calendar='s4-p16-timing7-aw8-dense-normal-q1-v1',
    whole_host_faults_and_special='s4-p16-timing7-whole-host-faults-q1-v1',
    thread8_continuous100='r75-p16-timing7-threads8-q1-v1')
LONG='s4-p16-timing7-continuous1000-thread8-normal-q1-v1'


def need(ok,why):
    if not ok:raise ValueError('TIMING7_CONSOLIDATION_'+why)


def sha(raw):return hashlib.sha256(raw).hexdigest()
def digest(value):return sha(json.dumps(value,sort_keys=True).encode())
def ref(path,root=ROOT):return dict(path=path,sha256=sha((root/path).read_bytes()))


def common(root=ROOT):
    path=root/COMMON;need(sha(path.read_bytes())==COMMON_PIN,'COMMON_METADATA_SOURCE')
    spec=importlib.util.spec_from_file_location('_metadata_scalar_only',path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def scalar_ledger(root=ROOT):
    c=common(root);n,base,k=65536,604832956,1911814
    need(math.floor(n*math.log2(base))+1==k,'LEADING_BIT_COUNT')
    geo=dict(warm_interval=8460,carry_done=12558)
    get=lambda count,hit=False,special=False:c.source_cycles(n,geo,count,hit,special,root)['host_done']
    need([get(x) for x in (1,100,1000)]==[668026,1505566,9119566],'OWN_FINITE_CYCLES')
    cold,cached,special=get(k),get(k,True),get(k,False,True)
    need((cold,cached,special)==(16174606006,16174605907,16174671542),'OWN_SAMPLE_CYCLES')
    need(get(1)+get(8,True)==1395173,'OWN_TWO_STOPPED_JOB_COUNTS')
    return dict(n=n,p=16,base=base,operations=k,bit_convention='K=floor(N*log2(base))+1 includes leading exponent bit, starting x0=1. Full-size sample PRP was not executed.',
        cold_primary_cycles=cold,cached_alternate_cycles=cached,special_alternate_cycles=special,
        cold_ordinary_completion=get(1),cached_ordinary_completion=get(1,True),warm_interval=8460,
        carry_done=12558,first_digit=8459,cold_first=102,cached_first=3,cold_root_extra=99,
        canonical_normal_cycles=9*n,canonical_special_cycles=10*n,copy_cycles=n+3,
        canonical_and_copy_occurrences=1,special_extra_cycles=n,
        equation='102 + (1911814-1)*8460 + 12558 + 2 + 9*65536 + 65536 + 4',
        finite_source_cycles=dict(short1=get(1),continuous100=get(100),continuous1000=get(1000)),
        seconds_per_ns=str(Decimal(cold)/Decimal(10**9)),selected_period_ns=None,
        selected_frequency_mhz=None,projected_seconds=None,
        sources=[ref(COMMON,root)]+[ref(path,root) for path in c.LEDGERS],
        scope='Own source-ledger compute-only input. Cold setup and final ordinary canonical/copy once included; initial host load/final host readback/board I/O/gaps excluded. No baseline8459/P8 clock or result inheritance.')


def fitted_source(root=ROOT):
    need(ref(FIT+'/receipt.json',root)['sha256']==FIT_RECEIPT,'FIT_RECEIPT')
    archive=root/FIT/'native-reports.tar.gz';need(sha(archive.read_bytes())==FIT_ARCHIVE,'FIT_ARCHIVE')
    with tarfile.open(archive) as t:raw=t.extractfile('project/manifest.json').read()
    need(sha(raw)==FIT_MANIFEST,'FIT_MANIFEST')
    m=json.loads(raw);pins=m['source_sha256']
    need(len(pins)==64 and pins[TOP]==TOP_PIN and m['core_parameters']==PARAMETERS,'EXACT_FITTED64')
    need({k:m['geometry'][k] for k in ('warm_interval','carry_done','first_digit','correction_cache_latency')}==
         dict(warm_interval=8460,carry_done=12558,first_digit=8459,correction_cache_latency=78),'FITTED_CALENDAR')
    return m,dict(receipt=ref(FIT+'/receipt.json',root),archive=ref(FIT+'/native-reports.tar.gz',root),
        archived_manifest_member='project/manifest.json',archived_manifest_sha256=FIT_MANIFEST,
        standalone64=pins,standalone64_map_sha256=digest(pins),parameters=PARAMETERS,
        scope='Exact completed whole-fit source identity, not an inherited clock or selected final passing audit.')


def trace(role,manifest,report,job,root=ROOT):
    count=manifest['continuous']['operations'];row=report['steps'][-1]
    path='queue/evidence/'+job+'/attempt-0/collected/output/native/'+row['log']
    raw=(root/path).read_bytes();need(sha(raw)==row['sha256'],'TRACE_LOG')
    lines=raw.decode().splitlines();need(len(lines)==count+1,'TRACE_LENGTH')
    pops=[]
    for line in lines[:count-1]:
        name,body=line.split(' ',1);need(name=='S4_CONTINUOUS_POP','TRACE_PREFIX');pops.append(json.loads(body))
    plan=manifest['continuous']['plan'];bits=plan['double_bits']
    for index,value in enumerate(pops,1):
        need(value==dict(index=index,age=102+index*8460,bit=int(bits[index])),'OWN_TRACE_AGE')
    footer=json.loads(lines[-1].split(' ',1)[1]);wanted=manifest['continuous']['counts_ordinary_source_projection']
    need(lines[-1].startswith('S4_CONTINUOUS_PASS ') and {k:footer[k] for k in wanted}==wanted,'TRACE_FOOTER')
    need(footer['candidate_cycles']==668026+(count-1)*8460,'OWN_DIRECT_COLD')
    return dict(role=role,log=ref(path,root),accepted_pop_rows=len(pops),
        cold_completion_from_trace=footer['candidate_cycles']-(count-1)*8460,
        directly_observed_interval=(pops[1]['age']-pops[0]['age']) if len(pops)>1 else None,
        counts=wanted,phase_wall_ms={k:footer[k] for k in ('candidate_ms','reference_ms','read_ms')})


def completed_subset(root=ROOT):
    c=common(root);fit,binding=fitted_source(root);entries=[];full={};small={};traces=[]
    for role,job in JOBS.items():
        entry,m,r,rtl=c.native(job,root);entry['role']=role
        need(all(m['build']['parameters'].get(k)==v for k,v in FLAGS.items()),'OWN_ROLE_FLAGS')
        if role in ('full9_two_stopped_jobs','cold_short','serial_continuous100','thread8_continuous100'):
            need(len(rtl)==75 and all(rtl.get(k)==v for k,v in fit['source_sha256'].items()),'EXACT64_SUBSET75')
            full[role]=(m,r,rtl)
            if role!='full9_two_stopped_jobs':
                need(m['continuous']['plan']['candidate_root_sha256']==TOP_PIN and m['continuous']['p16_timing']==1,'OWN_SOURCE_PLAN')
                traces.append(trace(role,m,r,job,root))
        else:
            need(m['build']['parameters']['P']==16 and m['p16_timing_qualification']['flags']==FLAGS,'OWN_SMALL_ROLE')
            keys=['p16_diet_prp_qualification','p16_diet_aw8_qualification','p16_diet_whole_host_faults']
            key=next(k for k in keys if k in m);meta=m[key]
            small[role]=dict(geometry={k:meta['geometry'][k] for k in ('n','p','first_digit','warm_interval','carry_done','feedback_fifo_rows')},
                declared_summary={k:meta[k] for k in ('base_floor','operations','host_cycles','reads','candidate_cycles','descriptor_codes','reset_ages','special_cycles') if k in meta},
                expected_stdout_sha256=[sha(step.get('expected_stdout','').encode()) for step in m['steps']])
        entries.append(entry)
    full9=full['full9_two_stopped_jobs'][0];base='queue/evidence/'+JOBS['full9_two_stopped_jobs']+'/attempt-0/collected/output/native'
    cpp=full9['build']['cpp_source'];header='rtl/tb/s4_host_chain_full_config_v1.h'
    with tarfile.open(root/base/'sources.tar.gz') as t:
        raw=t.extractfile(cpp).read();h=t.extractfile(header).read()
    need(sha(raw)==full9['sources'][cpp] and b'(hit?3u:102u)+uint64_t(count-1)*INTERVAL+CARRY_DONE+2+(special?10u:9u)*N+N+4' in raw,'OWN_FULL9_FINISH')
    need(sha(h)==full9['sources'][header] and b'FIRST_DIGIT=8459,INTERVAL=8460,CARRY_DONE=12558,EXPECTED_CYCLES=1395173' in h,'OWN_FULL9_HEADER')
    binding.update(paired75_map_sha256=digest(full['thread8_continuous100'][2]),exact_fitted64_subset_of_paired75=True,
        own_full9_cpp_sha256=full9['sources'][cpp],own_full9_header_sha256=full9['sources'][header])
    return dict(schema='stream27-p16-timing7-author-completed-subset-v1',status='COMPLETED_OWN_SUBSET_LONG_AND_FINAL_CLOCK_PENDING',
        promotion_allowed=False,producer=ref('reference/stream27_p16_timing7_consolidation.py',root),
        author_tests=ref('tests/test_stream27_p16_timing7_consolidation.py',root),
        candidate='Timing7 P16 diet/canonical1/context1, distinct from original baseline P16',root_sha256=TOP_PIN,
        source_binding=binding,receipt_index=entries,small_geometry_coverage=small,direct_traces=traces,sample_ledger=scalar_ledger(root),
        pending1000=dict(id=LONG,scope='One own eight-thread dependent1000 FIFO job, final-only65536 signed96; live result must not be inferred from short/100.',
            input=ref('results/throughput-20260929/s4-p16-timing7-continuous1000-thread8-native-v1/global-ticket-v1.json',root),
            gate=None,numerical_pass=None),
        final_clock=dict(fit_id='s4-p16-timing-whole-9000-high-effort-v1',final_audit=None,selected_period_ns=None,projected_seconds=None),
        remaining=['Own actual1000 typed terminal and final source join','Same saved-layout final clock/audit review','Independent consolidation and advisor acceptance before adoption'],
        scope_limits=['Own N32 PRPs and N256 dense18-row calendar are scaled source qualification, not full-size sample PRP.',
            'Full9 is two stopped jobs, not one continuous9/1000 chain.',
            'Minimal whole-host controls cover four descriptor faults/occupied reset/quarantine/recovery/sentinel and typed comparator, not exhaustive fault coverage.',
            'No original baseline P16/P8 numerical or clock inheritance. Simulation times do not establish achievable FPGA MHz.'],
        method='Source/receipt metadata joins, retained ordinal/calendar traces and pinned scalar ledger ASTs only; no full-N numerical/reference/native/fit rerun.')


def final_delta(snapshot,root=ROOT):
    snapshot=Path(snapshot).resolve();need(snapshot.is_file(),'PRIOR_PARTIAL_SNAPSHOT')
    prior=json.loads(snapshot.read_text());need(prior['schema']=='stream27-p16-timing7-author-completed-subset-v1' and prior['root_sha256']==TOP_PIN,'PRIOR_SOURCE')
    c=common(root);entry,m,r,rtl=c.native(LONG,root)
    pins=prior['source_binding']['standalone64']
    need(len(rtl)==75 and all(rtl.get(k)==v for k,v in pins.items()) and digest(rtl)==prior['source_binding']['paired75_map_sha256'],'FINAL_SOURCE_JOIN')
    v=entry['typed_results'][0]['validation'];counts=v['counts']
    need(r['probe']==dict(context_threads=8,model_threads=8,expected_threads=8) and
         v['p16_timing']==1 and v['candidate_root_sha256']==TOP_PIN and v['uninterrupted_1000_native'] and
         v['independent_reference_equal'] and v['final_actual_sha256']==v['final_expected_sha256'],'FINAL_NATIVE_EQUALITY')
    need(counts['candidate_cycles']==9119566 and counts['operations']==1000 and counts['doubles']==500 and
         counts['signed96_words']==65536 and all(counts[k]==1 for k in ('resets','loads','starts','readbacks')),'FINAL_CONTINUITY')
    return dict(schema='stream27-p16-timing7-author-long-delta-v1',status='OWN1000_TYPED_PASS_SOURCE_MATCHES_PARTIAL_CLOCK_SEPARATE',
        previous_snapshot=dict(path=str(snapshot.relative_to(root)),sha256=sha(snapshot.read_bytes())),
        producer=ref('reference/stream27_p16_timing7_consolidation.py',root),long=entry,
        direct_trace=trace('thread8_continuous1000',m,r,LONG,root),
        selected_period_ns=None,projected_seconds=None,promotion_allowed=False,
        scope='Only final1000 delta appended to frozen completed subset. Independent terminal/clock consolidation and advisor acceptance remain separate.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--delta-for',type=Path)
    args=parser.parse_args();result=final_delta(args.delta_for,args.root) if args.delta_for else completed_subset(args.root)
    print(json.dumps(result,sort_keys=True,indent=2))
