"""Own R12 automatic receipt index only; no native/oracle/source rerun."""
from datetime import datetime,timezone
import json
from pathlib import Path
from .stream27_context_storage_combo_oneshot_numerical_index import job,load,pin,sha

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/throughput-20260929/trackS-c2-feedback12-ownlong-v1'
NORMAL=ROOT/'results/throughput-20260929/trackS-c2-feedback12-native-v1'
IDS=[
 's4-p16-c2-combo-r12-aw8-normal-q1-v1',
 's4-p16-c2-combo-r12-full-normal-q1-v1',
 's4-p16-c2-combo-r12-own100-serial-q1-v1',
 's4-p16-c2-combo-r12-full-wrap-normal-q1-v1',
 's4-p16-c2-combo-r12-continuous1000-q1-v1',
 's4-p16-c2-combo-r12-full-control-q1-v2',
 's4-p16-c2-r12-prp-normal-q1-v1',
 's4-p16-c2-r12-prp-controls-q1-v1']
SELF='reference/stream27_context_feedback12_numerical_index.py'


def need(ok,why):
    if not ok:raise ValueError('R12_INDEX_'+why)


def prepare():
    out=BASE/'numerical-index-v1.json';need(not out.exists(),'FRESH_INDEX')
    bp=NORMAL/'full-normal/production-bundle.json';mp=NORMAL/'full-normal/manifest.json'
    bundle,manifest=load(bp),load(mp)
    need(sha(bp)=='c67f2b435f6fee7248818fe79e86795066df94952ea43ba63cd2756b38942695' and
         len(bundle['files'])==58 and len(manifest['build']['sv_sources'])==59 and
         manifest['build']['parameters']==dict(bundle['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),
         'EXACT_OWN_FULL_CAPTURE')
    rows=[job(identifier) for identifier in IDS]
    for i in (1,2,3,4,5):
        actual={Path(name).name:value for name,value in rows[i]['compiled_sources'].items()}
        need(all(actual.get(name)==digest for name,digest in bundle['generated_sha256'].items()),
             'OWN58_FULL_COMPILED:'+rows[i]['id'])
    small=load(NORMAL/'aw8-normal/production-bundle.json')
    for i in (0,6,7):
        actual={Path(name).name:value for name,value in rows[i]['compiled_sources'].items()}
        need(all(actual.get(name)==digest for name,digest in small['generated_sha256'].items()),
             'OWN58_SMALL_COMPILED:'+rows[i]['id'])
    ledger=ROOT/'results/throughput-20260929/trackS-c2-feedback12-ledger-v1/publication-ledger-native2-100-1000-joined-v1.json'
    need(sha(ledger)=='e583efe2630130aa65d8c3f6624049dc6845cde1dab80c5ca5ef2215660256fc' and
         load(ledger)['sample']['pair_completion_cycles']==16182916927,'OWN_LEDGER_JOIN')
    failed=ROOT/'queue/done/s4-p16-c2-combo-r12-full-control-q1-v1.json'
    fr=ROOT/'queue/evidence/s4-p16-c2-combo-r12-full-control-q1-v1/attempt-0/collected/output/native/report.json'
    need(load(failed)['result']['status']=='terminal_failure' and load(fr)['status']=='failed_native_commands',
         'PRESERVED_V2_FAILURE')
    queue_failed=ROOT/'queue/done/s4-p16-c2-r12-queue-normal-q1-v1.json'
    queue_report=ROOT/'queue/evidence/s4-p16-c2-r12-queue-normal-q1-v1/attempt-0/collected/output/native/report.json'
    queue_canceled=ROOT/'queue/done/s4-p16-c2-r12-queue-faults-q1-v1.json'
    need(load(queue_failed)['result']['status']=='terminal_failure' and
         load(queue_report)['status']=='failed_native_commands' and
         load(queue_canceled)['result']['status']=='cancelled_unstarted_dependency_failure','RETAINED_QUEUE_FAILURE_NO_FAULT_EXECUTION')
    value=dict(schema='stream27-c2-r12-numerical-evidence-index-v1',
        status='OWN_EIGHT_FUNCTIONAL_SCOPED_CONTROL_GATES_PASS_REVIEW_CLOCK_PENDING',
        created_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),owner='merged-ntt-model',
        producer=pin(ROOT/SELF),receipt_mechanics_only=pin(ROOT/'reference/stream27_context_storage_combo_oneshot_numerical_index.py'),
        production=dict(bundle=pin(bp),manifest=pin(mp),aw8_bundle=pin(NORMAL/'aw8-normal/production-bundle.json'),
            production_sv_count=58,full_compiled_sv_count=59,parameters=manifest['build']['parameters'],
            generated_sha256=bundle['generated_sha256'],source_dependency_pins=bundle['source_sha256'],
            top=bundle['top'],geometry=bundle['geometry'],rtl_ready_at_utc='2026-10-02T20:32:36Z',
            lean_production=True,host_GL_assumed_unimplemented=True,protected_fault_rollback_claim=False),
        jobs=rows,own_healthy_source_native_ledger=pin(ledger),
        own_ledger_producer=pin(ROOT/'reference/stream27_c2_r12_feedback_healthy_join_v3.py'),
        retained_failure=dict(id='s4-p16-c2-combo-r12-full-control-q1-v1',done=pin(failed),report=pin(fr),
            reason='CXX_MISSING_GENERATED_INCLUDE_r12_transport_control_config.h',
            actual_failure_not_reclassified=True,
            successor_scope='v2 changes ONLY generated include filename to match existing CPP; all production58, '
                'observer59, CPP, header content, reference and expectations unchanged. RESET5 and '
                'strict external HOSTwatch masks retain occupied raw/internal descriptor tails.',
            source_scope_test=pin(ROOT/'tests/test_stream27_context_feedback12_control_v2.py')),
        source_scopes=dict(transport='Coherent feedback and auto-correction queues plus C0 admission direct, '
                'on fixed three transports. Own I8464/F8462/C12561/cache78/seeds71..74 and '
                'scratch serialization independently recalendar. OldFIFO0 plus explicit queue1/full, '
                'AW8 oldFIFO18 plus queue1, not a resized array. Added latency is not free.',
            watchdog='Private90857 observes actual completed warm-square progress; native healthy1000/PRP '
                'and simulated real-age expiry, not a real stalled native job.',
            fullwrap='Three HOST timestamp aliases only; protocol/arithmetic/owner/watchdog ticks real. '
                'Actual table context/epoch/gen, not independent bank oracle or billions of protocol edges.',
            context='Same-C2 context-alone versus joint bit identity plus independent reference/all words; '
                'no C1-source equivalence or production RAM/config fault injection.',
            PRP='Own N256 full b^256 outputs and same-DUT impulse special-minus-one; no primality/fullN sample claim.',
            private_PRP_author='Own new R12 graph/geometry helper; unchanged driver/corpus provenance only from independent_review R11 recipe, no R11 execution inheritance.',
            protected_cache_fault_gate_inherited=False,protected_crosstalk_fault_gate_inherited=False,
            removed_lean_checks_not_asserted=True,full_count2_reset_epoch_wrap_claim=False,
            actual1000_epoch16_wrap=True,no_reload_or_checkpoint_in1000=True,
            no_ancestor_execution_forecast_clock_inheritance=True,full_N_numeric_locally_performed=False),
        queued_descriptor_fixture=dict(predecessor_normal=pin(queue_failed),predecessor_report=pin(queue_report),
            predecessor_faults=pin(queue_canceled),normal_failure='Duplicate unguarded config include caused C++ redefinitions/build rc2 before model.',
            native_fault_execution_in_this_index=False,protection_pass_claim=False,
            additive_include_only_v2_normal_submitted_separately=True),
        protected_mode=dict(execution_in_this_lean_index=False,healthy_normal_is_separate_source_mode=True,
            no_protected_result_clock_or_fault_inheritance=True),
        final_promotion=dict(source_numerical_review_pending=True,own_physical_clock_pending=True,
            advisor_acceptance_pending=True,selected_period_ns=None,projected_pair_seconds=None,
            projected_amortized_seconds=None,promotion_allowed=False))
    with out.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    return dict(index=str(out),sha256=sha(out),own_jobs=len(rows),status=value['status'])


if __name__=='__main__':print(json.dumps(prepare(),indent=2))
