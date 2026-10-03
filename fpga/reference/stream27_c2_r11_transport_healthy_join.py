"""Own R11 captured-source/native2 healthy calendar join; clock stays NULL.

No RTL execution or full-N arithmetic locally. Sample-count arithmetic uses
own source geometry and declared FIRST anchors, not a previous pair ledger.
"""
import argparse
import hashlib
import json
from pathlib import Path
from . import stream27_context_transport11_model as model

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_c2_r11_transport_healthy_join.py'
CAPTURE='results/throughput-20260929/trackS-c2-storage-combo-transport11-native-v1/full-normal-v2/production-bundle.json'
CAPTURE_PIN='5c795a3efe314d7b77b3508de56b5f0870708ed3ef145a23198ee9a477f5382e'
SOURCE_PINS={
 'reference/stream27_context_storage_combo_transport11_bind.py':'5375b3fd76f78b342b2ee1a6a931629ae4e3883dcc2b8091e9157f9bc3ab9d3b',
 'reference/stream27_context_storage_combo_transport11_source_v2.py':'792851152b0a637a83885a72fb33a972601547470ae377723228411a188c2262',
 'reference/stream27_context_transport11_model.py':'2b047ff32c9e162ae437a37df871b99cf4bdd473a37e12bf7519772a82e963df',
 'reference/stream27_context_lean_watchdog_bind.py':'90857abb24ed29925e5b3709ba2b274882848ba76a3b3f2d2272034e6c2203c3'}
ID='s4-p16-c2-combo-r11-full-normal-q1-v1'
STEP='normal-full-c2-r11-lean-alone-and-joint'
LOG=STEP+'.log'
SAMPLE_K=1911814


def need(ok,why):
    if not ok:raise ValueError('R11_HEALTHY_JOIN_'+why)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def source():
    raw=(ROOT/CAPTURE).read_bytes();need(sha(raw)==CAPTURE_PIN,'OWN_CAPTURE')
    b=json.loads(raw);g=b['geometry'];c=b['context_transport11']
    need(len(b['files'])==58 and {name:sha(text.encode()) for name,text in b['files'].items()}==
         b['generated_sha256'],'ALL58_CAPTURE_BYTES')
    for name,pin in SOURCE_PINS.items():
        need(b['source_sha256'][name]==pin and sha((ROOT/name).read_bytes())==pin,'FROZEN_SOURCE:'+name)
    for flag in ('CRT_TRANSPORT_REG','INVERSE_INGRESS_REG','TERM_JOIN_TRANSPORT_REG',
                 'LEAN_PROGRESS_WATCHDOG','LEAN_PRODUCTION'):
        need(b['parameters'][flag]==1,'OWN_FLAG:'+flag)
    need(c['source_ready'] and c['source_declared_cold_first_edges']==[204,4435] and
         c['source_declared_solo_first_edge']==104 and c['term_recurrence_edges']==4 and
         c['publication_fence_edges_per_job']==1 and c['ntt_compare_reg']==0,'OWN_SOURCE_CONTRACT')
    need(model.geometry(c['calendar_before'],crt_transport_reg=1,inverse_ingress_reg=1,
         term_join_transport_reg=1)==g and
         tuple(g[k] for k in ('n','p','rows','warm_interval','first_digit','carry_done',
                 'sink_accept','crt_accept','correction_cache_latency','term_seed_first','term_seed_last'))==
         (65536,16,4096,8463,8462,12561,8419,8420,78,71,74),'OWN_GEOMETRY')
    host=b['files'][b['top']+'.sv']
    for anchor in ('wire lean_square_progress=child_completed!=lean_completed_seen;',
                   'if(child_correction_accept)begin second_correction_sent<=1;',
                   'if(publish_pending)begin','publish_owner<=live_owner[canonical_owner*56+:56];',
                   'assign canonical_ready=published & {2{!safety_error}};'):
        need(host.count(anchor)==1,'OWN_HOST_ANCHOR:'+anchor)
    need(any('logic crt_transport_slot,crt_transport_start,crt_transport_double;' in text for text in b['files'].values())
         and sum('logic pair_slot_q,pair_start_q;' in text for text in b['files'].values())==3 and
         sum('logic inverse_slot_q,inverse_start_q;' in text for text in b['files'].values())==3,
         'OWN_THREE_TRANSPORT_SEAMS')
    return b


def calendar(g,count,special=(False,False)):
    # FIRSTs are traced in the own captured contract and verified natively for2.
    return model.publication_calendar(g,count,[204,4435],special=special)


def validate_footer(value,g,count=2):
    e=calendar(g,count)
    need(value['interval']==g['warm_interval'] and value['warm_edges']==e['warm_edges'] and
         value['done_edges']==e['publication_edges'] and
         value['joint_cycles']==e['full_read_completion_cycles'] and value['setup_edges']==[99,199],
         'OWN_ACTUAL_EVENT_EDGES')
    need(value['launches']==[[first+k*g['warm_interval'] for k in range(count)] for first in e['first_edges']],
         'EVERY_OWN_ACTUAL_LAUNCH')
    need(value['signed96'] is True and value['independent_reference'] is True and
         value['bases']==[604832956,999999937] and value['model_threads']==1,'OWN_REFERENCE_PROFILES')
    if count==2:
        need(value['context_alone_bit_identical'] is True and value['squares']==8 and
             value['reads']==393216 and value['peer_live_reads']==65536 and value['single_cycles']==[746130,746130],
             'OWN_SAME_C2_ALONE_JOINT')
    else:
        need(value['count_per_context']==count and value['squares']==2*count and
             value['descriptors']==2*(count-1) and value['reads']==262144 and
             value['initial_resets']==1 and value['initial_load_words']==131072 and
             value['peer_live_reads']==65536,'OWN_CONTINUOUS_NO_RELOAD')
    return e


def close_native2():
    b=source();g=b['geometry'];evidence=ROOT/'queue/evidence'/ID
    native=evidence/'attempt-0/collected/output/native'
    gp=evidence/'gate-receipt.json';rp=native/'report.json';mp=native/'approved-manifest.json';lp=native/LOG
    gate,report,manifest=[json.loads(p.read_bytes()) for p in (gp,rp,mp)]
    need(gate['status']=='PASS_expected_contracts' and gate['manifest_sha256']==sha(mp.read_bytes())==
         report['manifest_sha256'] and gate['report_sha256']==sha(rp.read_bytes()),'OWN_AUTOMATIC_BINDING')
    need(len(manifest['build']['sv_sources'])==59 and
         manifest['build']['parameters']==dict(b['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),
         'OWN_ACTUAL_COMPILED_PARAMETERS')
    for name,pin in b['generated_sha256'].items():
        need(manifest['sources']['rtl/'+name]==pin==report['sources']['rtl/'+name] and
             'rtl/'+name in manifest['build']['sv_sources'],'ALL58_ACTUAL_COMPILED_PRODUCTION')
    build=[row for row in report['steps'] if row['name']=='build']
    need(len(build)==1 and build[0]['returncode']==0 and
         all('-G'+key+'='+str(value) in build[0]['command'] for key,value in manifest['build']['parameters'].items()),
         'ACTUAL_PARAMETER_ARGV')
    need(report['artifacts'][LOG]==sha(lp.read_bytes()),'REPORT_BOUND_RAW_LOG')
    text=lp.read_text();need(text.startswith('R84_C2_FULL_PASS ') and len(text.splitlines())==1,'OWN_LOG_FOOTER')
    footer=json.loads(text.removeprefix('R84_C2_FULL_PASS '));actual=validate_footer(footer,g)
    calendars={str(k):calendar(g,k) for k in (2,100,1000,SAMPLE_K)}
    sample=calendars[str(SAMPLE_K)]
    need(sample['pair_completion_cycles']==16181005114,'OWN_REDERIVED_SAMPLE_NOT_ANCESTOR_LEDGER')
    return dict(schema='r11-own-source-native2-healthy-ledger-v1',status='OWN_SOURCE_NATIVE2_JOIN_PASS_LONG_AND_CLOCK_PENDING',
        producer=dict(path=SELF,sha256=sha((ROOT/SELF).read_bytes())),production=dict(top=b['top'],sv_count=58,
            bundle=dict(path=CAPTURE,sha256=CAPTURE_PIN),all58_generated_sha256=b['generated_sha256'],source_pins=SOURCE_PINS,
            compiled_parameters=manifest['build']['parameters']),native2=dict(id=ID,gate_sha256=sha(gp.read_bytes()),
            report_sha256=sha(rp.read_bytes()),manifest_sha256=sha(mp.read_bytes()),log_name=LOG,
            log_sha256=sha(lp.read_bytes()),measurements=footer,calendar=actual),calendars=calendars,sample=sample,
        native100_join_pending=True,native1000_join_pending=True,own_wrap_control_PRP_qualification_separate=True,
        selected_period_ns=None,projected_pair_seconds=None,projected_amortized_seconds=None,promotion_allowed=False,
        scope=['Own LEAN build; host GL assumed/unimplemented; no protected fault/rollback credit.',
               'Healthy timely-feed equal ordinary K1911814 pair only; both setup/canonical/copy/PUB1 included.',
               'External cold load, external readback and host transport excluded from pair_completion_cycles.',
               'One special minus-one adds65536 edges per affected job, not each square.',
               'Source-watchdog repair and transports do not inherit old R10 PRP/native1000 qualification.',
               'No measured full-sample PRP, board clock, individual latency or no-cost-added-latency claim.'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();need(out.is_relative_to(ROOT) and not out.exists(),'FRESH_OUTPUT')
    value=close_native2();out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(status=value['status'],path=str(out),sha256=sha(out.read_bytes()),
        pair_cycles=value['sample']['pair_completion_cycles'],selected_period_ns=None)))
