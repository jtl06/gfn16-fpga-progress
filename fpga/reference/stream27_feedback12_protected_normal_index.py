"""Two fresh protected R12 normal receipts; never import lean execution credit."""
from datetime import datetime,timezone
import json
from pathlib import Path
from .stream27_context_storage_combo_oneshot_numerical_index import job,load,pin,sha

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/throughput-20260929/trackS-c2-feedback12-protected-native-v1'
SELF='reference/stream27_feedback12_protected_normal_index.py'


def need(ok,why):
    if not ok:raise ValueError('R12_PROTECTED_NORMAL_INDEX_'+why)


def prepare():
    out=BASE/'normal-evidence-index-v1.json';need(not out.exists(),'FRESH_OUTPUT')
    captures=[];rows=[]
    for stage,interval in (('aw8',218),('full',8464)):
        directory=BASE/(stage+'-normal');bp=directory/'production-bundle.json';mp=directory/'manifest.json'
        b,m=load(bp),load(mp);identifier='s4-p16-c2-r12-protected-'+stage+'-normal-q1-v1'
        row=job(identifier);actual={Path(name).name:value for name,value in row['compiled_sources'].items()}
        need(len(b['files'])==58 and len(m['build']['sv_sources'])==58+(stage=='full') and
             all(actual.get(name)==digest for name,digest in b['generated_sha256'].items()),'OWN_PROTECTED58_COMPILED')
        need(row['compiled_parameters']==m['build']['parameters']==dict(b['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42) and
             'LEAN_PRODUCTION' not in b['parameters'] and b['parameters']['LEAN_PROGRESS_WATCHDOG']==0 and
             not b['context_feedback12']['lean_production'],'PROTECTED_MODE_NO_LEAN_FLAGS')
        need(b['geometry']['warm_interval']==interval and
             all(b['parameters'][flag]==1 for flag in ('CRT_TRANSPORT_REG','INVERSE_INGRESS_REG','TERM_JOIN_TRANSPORT_REG',
                 'FEEDBACK_INGRESS_REG','AUTO_CORRECTION_INGRESS_REG','C0_ADMISSION_DIRECT')),'OWN_TRANSPORT_BASELINE_NOT_FIELD100')
        need(m['rtl_readiness']['rtl_ready_at_utc']=='2026-10-02T22:11:01Z','OWN_PROTECTED_FREEZE')
        captures.append(dict(stage=stage,bundle=pin(bp),manifest=pin(mp),parameters=m['build']['parameters'],
            generated_sha256=b['generated_sha256'],source_dependency_pins=b['source_sha256'],geometry=b['geometry']))
        rows.append(row)
    measurements=rows[1]['steps'][0]['measurements']
    need(measurements['squares']==8 and measurements['reads']==393216 and measurements['interval']==8464 and
         measurements['joint_cycles']==1405695 and measurements['context_alone_bit_identical'] and
         measurements['independent_reference'] and measurements['done_edges']==[680695,1340159],
         'OWN_FULL_NUMERICAL_CALENDAR')
    value=dict(schema='r12-protected-baseline-two-normal-index-v1',status='OWN_PROTECTED_MODE_TWO_NORMAL_GATES_PASS_ONLY',
        created_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),producer=pin(ROOT/SELF),
        numerical_helper=pin(ROOT/'reference/stream27_feedback12_protected_native.py'),
        source_tests=pin(ROOT/'tests/test_stream27_feedback12_protected_native.py'),captures=captures,jobs=rows,
        scope=dict(three_transports_retained=True,protected_field100_transport_OFF_batch=False,
            lean_runtime_normal_fault_or_clock_inherited=False,own1000_or_PRP_or_fault_qualification_in_this_index=False,
            source_restores_protected_checks=True,GL_or_rollback_implementation_added=False,
            accepted_helper_scope_precision='Healthy protected-mode evidence only. Copied scope text mentioning host GL '
                'does not implement GL or establish protection/rollback qualification; actual compiled watch0/no LEAN flag '
                'and metadata lean_production=false identify the protected source.',
            same_C2_context_alone_joint_not_C1_source_equivalence=True,arbitrary_fault_protection_claim=False),
        promotion_allowed=False,selected_period_ns=None,projected_pair_seconds=None,projected_amortized_seconds=None)
    with out.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    return dict(index=str(out),sha256=sha(out),status=value['status'],own_jobs=len(rows))


if __name__=='__main__':print(json.dumps(prepare(),indent=2))
