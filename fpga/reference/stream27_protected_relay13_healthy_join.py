"""Own protected R13 source/native calendar join; no local RTL or NTT execution.

Pure model arithmetic is joined to captured own production bytes, compiled
parameters and automatic typed native receipts. Clock and promotion remain
separate; equal scalars never supply another candidate's qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
from . import stream27_protected_relay13_model as model

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_protected_relay13_healthy_join.py'
CAPTURE='results/throughput-20260929/trackS-c2-protected-relay13-native-v1/full-normal/production-bundle.json'
CAPTURE_PIN='229e07390fbed434131bba7e101c2492bde27f5a45ebceb7fa40e1d94fec5c53'
SOURCE_PINS={
 'reference/stream27_protected_relay13_bind.py':'cbb914bbf82f28a008bd7097910e0719d9d4d51d77b258a7e7a60ebae457e21a',
 'reference/stream27_protected_relay13_model.py':'fdd5a171af84d3e62c334727ada44f33c69f69c4bb2ef416fcc2e456de3934d4'}
JOBS={2:('s4-p16-c2-protected-relay13-full-normal-q1-v1','normal-full-c2-protected-relay13-alone-and-joint','R84_C2_FULL_PASS '),
 100:('s4-p16-c2-protected-relay13-own100-serial-q1-v1','normal-full-c2-protected-relay13-own100-percontext','R84_C2_THREAD100_PASS '),
 1000:('s4-p16-c2-protected-relay13-continuous1000-q1-v1','normal-full-c2-protected-relay13-continuous1000-percontext','R84_C2_THREAD100_PASS ')}
SAMPLE_K=1911814

def need(ok,why):
    if not ok:raise ValueError('R13_HEALTHY_JOIN_'+why)

def sha(raw):return hashlib.sha256(raw).hexdigest()

def source():
    raw=(ROOT/CAPTURE).read_bytes();need(sha(raw)==CAPTURE_PIN,'OWN_CAPTURE')
    b=json.loads(raw);g=b['geometry'];c=b['context_protected_relay13'];p=b['parameters']
    need(len(b['files'])==58 and {n:sha(t.encode()) for n,t in b['files'].items()}==b['generated_sha256'],'OWN_ALL58_BYTES')
    for name,pin in SOURCE_PINS.items():
        need(b['source_sha256'][name]==pin and sha((ROOT/name).read_bytes())==pin,'OWN_FROZEN_SOURCE:'+name)
    need(c['source_ready'] and not c['lean_production'] and c['CRT_TRANSPORT_REG']==0 and
        c['source_declared_cold_first_edges']==[204,4436] and c['source_declared_solo_first_edge']==104 and
        c['publication_fence_edges_per_job']==1 and c['cold_one_shot_acceptance_retirement_literal'] and
        c['host_full56_COPY_DRAIN_literal'] and c['protocol_FAST_and_raw_tuple_retirement_literal'],'OWN_SOURCE_CONTRACT')
    need('LEAN_PRODUCTION' not in p and 'LEAN_PROGRESS_WATCHDOG' not in p and p['CRT_TRANSPORT_REG']==0 and
        all(p.get(k)==1 for k in ('INVERSE_INGRESS_REG','TERM_JOIN_TRANSPORT_REG','FORWARD_INGRESS_REG',
         'FIELD_PROTOCOL_ORIGIN_FAST','FIELD_ERROR_REPORT_REG','DATAPATH_QUARANTINE_REG',
         'FEEDBACK_INGRESS_REG','AUTO_CORRECTION_INGRESS_REG','C0_ADMISSION_DIRECT',
         'CANONICAL_FOLD_PAYLOAD_REG','CARRY_QUARANTINE_LOCAL')),'OWN_PROTECTED_FLAGS')
    need(model.geometry(c['calendar_before'],inverse_ingress_reg=1,term_join_transport_reg=1,forward_ingress_reg=1)==g and
        tuple(g[k] for k in ('n','p','rows','warm_interval','pointwise_accept','sink_accept','crt_accept','first_digit',
            'carry_done','correction_cache_latency','term_seed_first','term_seed_last','carry_busy_edges','cache_margin'))==
        (65536,16,4096,8464,4208,8420,8420,8462,12561,78,71,74,4142,31),'OWN_GEOMETRY_NOT_EQUAL_I_PARENT')
    host=b['files'][b['top']+'.sv']
    for anchor in ('if(child_correction_accept)begin second_correction_sent<=1;',
        'if(publish_pending)begin','publish_owner<=live_owner[canonical_owner*56+:56];',
        'assign canonical_ready=published & {2{!safety_error}};'):
        need(host.count(anchor)==1,'OWN_HOST_AUTHORITY:'+anchor)
    need('logic crt_transport_slot,crt_transport_start,crt_transport_double;' not in ''.join(b['files'].values()),'CRT_RELAY_OFF')
    for label in ('forward','pair','inverse'):
        need(sum('logic '+label+'_slot_q,'+label+'_start_q;' in t for t in b['files'].values())==3,'THREE_FIELDS_'+label)
    return b

def calendar(g,count,special=(False,False)):
    return model.event_calendar(g,count,special=special)

def validate_footer(v,g,count):
    e=calendar(g,count)
    need(v['interval']==g['warm_interval'] and v['warm_edges']==e['warm_edges'] and
        v['done_edges']==e['publication_edges'] and v['joint_cycles']==e['full_read_completion_cycles'] and
        v['setup_edges']==[99,199] and
        v['launches']==[[first+k*g['warm_interval'] for k in range(count)] for first in e['first_edges']],
        'OWN_EVERY_LAUNCH_AND_PUBLICATION')
    need(v['signed96'] is True and v['independent_reference'] is True and
        v['bases']==[604832956,999999937] and v['model_threads']==1,'OWN_REFERENCE_PROFILES')
    if count==2:
        need(v['context_alone_bit_identical'] is True and v['squares']==8 and v['reads']==393216 and
            v['peer_live_reads']==65536 and v['single_cycles']==[746131,746131],'OWN_SAME_C2_ALONE_JOINT')
    else:
        need(v['count_per_context']==count and v['squares']==2*count and v['descriptors']==2*(count-1) and
            v['reads']==262144 and v['initial_resets']==1 and v['initial_load_words']==131072 and
            v['peer_live_reads']==65536,'OWN_UNINTERRUPTED_COUNT')
    return e

def native(b,count):
    job,step,prefix=JOBS[count];e=ROOT/'queue/evidence'/job;n=e/'attempt-0/collected/output/native'
    gp=e/'gate-receipt.json';rp=n/'report.json';mp=n/'approved-manifest.json';lp=n/(step+'.log')
    gate,report,m=[json.loads(p.read_bytes()) for p in (gp,rp,mp)]
    need(gate['status']=='PASS_expected_contracts' and gate['manifest_sha256']==sha(mp.read_bytes())==
        report['manifest_sha256'] and gate['report_sha256']==sha(rp.read_bytes()),'OWN_AUTOMATIC_RECEIPT')
    need(len(m['build']['sv_sources'])==59 and m['build']['parameters']==dict(b['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),
        'OWN_ACTUAL_COMPILED_PARAMETERS')
    for name,pin in b['generated_sha256'].items():
        need(m['sources']['rtl/'+name]==pin==report['sources']['rtl/'+name] and 'rtl/'+name in m['build']['sv_sources'],
            'OWN_ALL58_COMPILED_PRODUCTION')
    build=[r for r in report['steps'] if r['name']=='build']
    need(len(build)==1 and build[0]['returncode']==0 and
        all('-G'+k+'='+str(v) in build[0]['command'] for k,v in m['build']['parameters'].items()),'ACTUAL_PARAMETER_ARGV')
    need(report['artifacts'][step+'.log']==sha(lp.read_bytes()),'OWN_BOUND_RAW_LOG')
    text=lp.read_text();need(text.startswith(prefix) and len(text.splitlines())==1,'OWN_LOG_FOOTER')
    footer=json.loads(text.removeprefix(prefix));derived=validate_footer(footer,b['geometry'],count)
    return dict(id=job,gate_sha256=sha(gp.read_bytes()),report_sha256=sha(rp.read_bytes()),
        manifest_sha256=sha(mp.read_bytes()),log_name=step+'.log',log_sha256=sha(lp.read_bytes()),
        compiled_parameters=m['build']['parameters'],measurements=footer,calendar=derived)

def close(include1000=False):
    b=source();g=b['geometry'];calendars={str(k):calendar(g,k) for k in (2,100,1000,SAMPLE_K)}
    sample=calendars[str(SAMPLE_K)]
    need(sample['pair_completion_cycles']==16182916927,'OWN_SOURCE_DERIVED_SAMPLE')
    jobs={str(k):native(b,k) for k in ((2,100,1000) if include1000 else (2,100))}
    return dict(schema='r13-own-source-native-healthy-ledger-v1',
        status='OWN_SOURCE_NATIVE2_100_1000_JOIN_PASS' if include1000 else 'OWN_SOURCE_NATIVE2_100_JOIN_PASS_LONG_PENDING',
        producer=dict(path=SELF,sha256=sha((ROOT/SELF).read_bytes())),
        production=dict(top=b['top'],sv_count=58,bundle=dict(path=CAPTURE,sha256=CAPTURE_PIN),
            all58_generated_sha256=b['generated_sha256'],source_pins=SOURCE_PINS),
        jobs=jobs,calendars=calendars,sample=sample,native1000_pending=not include1000,
        selected_period_ns=None,projected_pair_seconds=None,projected_amortized_seconds=None,promotion_allowed=False,
        scopes=['Own protected R13 healthy timely-feed ordinary equal K1911814 pair only.',
          'Setup/canonical/copyN+4/PUB1 included; external cold input/readback and host transport excluded.',
          'Source-equivalent scalar functions reused as arithmetic only, never R12 execution/clock qualification.',
          'Special minus-one adds65536 edges per affected job, not per square.',
          'Fault/cache/context/wrap/PRP and physical/clock/review/advisor gates remain separate.',
          'No GL/rollback implementation, measured full-sample PRP, board or individual-latency claim.'])

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--include1000',action='store_true');a=p.parse_args();out=a.output.resolve()
    need(out.is_relative_to(ROOT) and not out.exists(),'FRESH_OUTPUT');value=close(a.include1000)
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(status=value['status'],path=str(out),sha256=sha(out.read_bytes()),
        pair_cycles=value['sample']['pair_completion_cycles'],period_ns=None)))
