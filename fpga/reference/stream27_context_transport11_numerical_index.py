"""Own R11 automatic receipt index only; no native/oracle/source rerun."""
from datetime import datetime,timezone
import json
from pathlib import Path
from .stream27_context_storage_combo_oneshot_numerical_index import job,load,pin,sha

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-transport11-ownlong-v1'
NORMAL=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-transport11-native-v1'
IDS=[
 's4-p16-c2-combo-r11-aw8-normal-q1-v1',
 's4-p16-c2-combo-r11-full-normal-q1-v1',
 's4-p16-c2-combo-r11-own100-serial-q1-v1',
 's4-p16-c2-combo-r11-full-wrap-normal-q1-v1',
 's4-p16-c2-combo-r11-continuous1000-q1-v1',
 's4-p16-c2-combo-r11-full-control-q1-v3',
 's4-p16-c2-r11-prp-normal-q1-v1',
 's4-p16-c2-r11-prp-controls-q1-v1']
SELF='reference/stream27_context_transport11_numerical_index.py'


def need(ok,why):
    if not ok:raise ValueError('R11_INDEX_'+why)


def prepare():
    out=BASE/'numerical-index-v1.json';need(not out.exists(),'FRESH_INDEX')
    bp=NORMAL/'full-normal-v2/production-bundle.json';mp=NORMAL/'full-normal-v2/manifest.json'
    bundle,manifest=load(bp),load(mp)
    need(sha(bp)=='5c795a3efe314d7b77b3508de56b5f0870708ed3ef145a23198ee9a477f5382e' and
         len(bundle['files'])==58 and len(manifest['build']['sv_sources'])==59 and
         manifest['build']['parameters']==dict(bundle['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),
         'EXACT_OWN_FULL_CAPTURE')
    rows=[job(identifier) for identifier in IDS]
    for i in (1,2,3,4,5):
        actual={Path(name).name:value for name,value in rows[i]['compiled_sources'].items()}
        need(all(actual.get(name)==digest for name,digest in bundle['generated_sha256'].items()),
             'OWN58_FULL_COMPILED:'+rows[i]['id'])
    small=load(NORMAL/'aw8-normal-v2/production-bundle.json')
    for i in (0,6,7):
        actual={Path(name).name:value for name,value in rows[i]['compiled_sources'].items()}
        need(all(actual.get(name)==digest for name,digest in small['generated_sha256'].items()),
             'OWN58_SMALL_COMPILED:'+rows[i]['id'])
    ledger=ROOT/'results/throughput-20260929/trackS-c2-transport11-ledger-v1/publication-ledger-native2-100-1000-joined-v1.json'
    need(sha(ledger)=='fa9b372ed349714d3c1003df9214f682df814a8213711608a5750122ce00cb1b' and
         load(ledger)['sample']['pair_completion_cycles']==16181005114,'OWN_LEDGER_JOIN')
    failed=ROOT/'queue/done/s4-p16-c2-combo-r11-full-control-q1-v2.json'
    fr=ROOT/'queue/evidence/s4-p16-c2-combo-r11-full-control-q1-v2/attempt-0/collected/output/native/report.json'
    need(load(failed)['result']['status']=='terminal_failure' and load(fr)['status']=='failed_native_commands',
         'PRESERVED_V2_FAILURE')
    value=dict(schema='stream27-c2-r11-numerical-evidence-index-v1',
        status='OWN_EIGHT_FUNCTIONAL_SCOPED_CONTROL_GATES_PASS_REVIEW_CLOCK_PENDING',
        created_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),owner='merged-ntt-model',
        producer=pin(ROOT/SELF),receipt_mechanics_only=pin(ROOT/'reference/stream27_context_storage_combo_oneshot_numerical_index.py'),
        production=dict(bundle=pin(bp),manifest=pin(mp),aw8_bundle=pin(NORMAL/'aw8-normal-v2/production-bundle.json'),
            production_sv_count=58,full_compiled_sv_count=59,parameters=manifest['build']['parameters'],
            generated_sha256=bundle['generated_sha256'],source_dependency_pins=bundle['source_sha256'],
            top=bundle['top'],geometry=bundle['geometry'],rtl_ready_at_utc='2026-10-02T19:30:30Z',
            lean_production=True,host_GL_assumed_unimplemented=True,protected_fault_rollback_claim=False),
        jobs=rows,own_healthy_source_native_ledger=pin(ledger),
        own_ledger_producer=pin(ROOT/'reference/stream27_c2_r11_transport_healthy_join_v3.py'),
        retained_failure=dict(id='s4-p16-c2-combo-r11-full-control-q1-v2',done=pin(failed),report=pin(fr),
            reason='R11_CONTROL_QUARANTINE_NO_PUBLICATION_OR_STALE_TUPLE',
            actual_failure_not_reclassified=True,
            successor_scope='v3 retains RESET3 slot/start flush and strict external HOSTwatch masks, '
                'permits original occupied raw/internal descriptor tails. No production or reference change.',
            source_scope_test=pin(ROOT/'tests/test_stream27_context_transport11_control_v3.py')),
        source_scopes=dict(transport='Coherent term JOIN/inverse/CRT tuples: sink+2, downstream+3; '
                'E4 term recurrence/PW/cache78/seeds71..74 unchanged. Added launch interval is not free.',
            watchdog='Private90857 observes actual completed warm-square progress; native healthy1000/PRP '
                'and simulated real-age expiry, not a real stalled native job.',
            fullwrap='Three HOST timestamp aliases only; protocol/arithmetic/owner/watchdog ticks real. '
                'Actual table context/epoch/gen, not independent bank oracle or billions of protocol edges.',
            context='Same-C2 context-alone versus joint bit identity plus independent reference/all words; '
                'no C1-source equivalence or production RAM/config fault injection.',
            PRP='Own N256 full b^256 outputs and same-DUT impulse special-minus-one; no primality/fullN sample claim.',
            private_PRP_author='independent_review authors only these new PRP source/roles; exclude author from its promotion review.',
            protected_cache_fault_gate_inherited=False,protected_crosstalk_fault_gate_inherited=False,
            removed_lean_checks_not_asserted=True,full_count2_reset_epoch_wrap_claim=False,
            actual1000_epoch16_wrap=True,no_reload_or_checkpoint_in1000=True,
            no_ancestor_execution_forecast_clock_inheritance=True,full_N_numeric_locally_performed=False),
        final_promotion=dict(source_numerical_review_pending=True,own_physical_clock_pending=True,
            advisor_acceptance_pending=True,selected_period_ns=None,projected_pair_seconds=None,
            projected_amortized_seconds=None,promotion_allowed=False))
    with out.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    return dict(index=str(out),sha256=sha(out),own_jobs=len(rows),status=value['status'])


if __name__=='__main__':print(json.dumps(prepare(),indent=2))
