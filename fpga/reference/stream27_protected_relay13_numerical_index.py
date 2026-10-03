"""Own R13 automatic evidence index; no numerical or native replay."""
from datetime import datetime,timezone
from pathlib import Path
from .stream27_context_storage_combo_oneshot_numerical_index import job,load,pin,sha

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_protected_relay13_numerical_index.py'
BASE=ROOT/'results/throughput-20260929/trackS-c2-protected-relay13-ownlong-v1'
NORMAL=ROOT/'results/throughput-20260929/trackS-c2-protected-relay13-native-v1'
IDS=[
 's4-p16-c2-protected-relay13-aw8-normal-q1-v1',
 's4-p16-c2-protected-relay13-full-normal-q1-v1',
 's4-p16-c2-protected-relay13-own100-serial-q1-v1',
 's4-p16-c2-protected-relay13-full-wrap-normal-q1-v1',
 's4-p16-c2-protected-relay13-continuous1000-q1-v1',
 's4-p16-c2-protected-relay13-full-contracts-q1-v1',
 's4-p16-c2-protected-relay13-full-early-cache-q1-v1',
 's4-p16-c2-protected-relay13-crosstalk-q1-v1',
 's4-p16-c2-protected-relay13-prp-normal-q1-v1',
 's4-p16-c2-protected-relay13-prp-controls-q1-v1']

def need(ok,why):
    if not ok:raise ValueError('R13_INDEX_'+why)

def prepare():
    import json
    out=BASE/'numerical-index-v1.json';need(not out.exists(),'FRESH_INDEX')
    bp=NORMAL/'full-normal/production-bundle.json';mp=NORMAL/'full-normal/manifest.json'
    bundle,manifest=load(bp),load(mp)
    need(sha(bp)=='229e07390fbed434131bba7e101c2492bde27f5a45ebceb7fa40e1d94fec5c53' and
        sha(mp)=='d39a6e7a7054aa59f1b2cd66cdb25013e69a1af56c562ecb575b2c3829bda51d' and
        len(bundle['files'])==58 and manifest['build']['parameters']==dict(bundle['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),
        'OWN_FULL_CAPTURE')
    rows=[job(identifier) for identifier in IDS]
    for i in (1,2,3,4,5,7):
        actual={Path(n).name:p for n,p in rows[i]['compiled_sources'].items()}
        need(all(actual.get(n)==p for n,p in bundle['generated_sha256'].items()),'OWN_ALL58_FULL:'+rows[i]['id'])
        need(rows[i]['compiled_parameters']==manifest['build']['parameters'],'OWN_PARAMETERS:'+rows[i]['id'])
    small=load(NORMAL/'aw8-normal/production-bundle.json')
    for i in (0,8,9):
        actual={Path(n).name:p for n,p in rows[i]['compiled_sources'].items()}
        need(all(actual.get(n)==p for n,p in small['generated_sha256'].items()),'OWN_ALL58_SMALL:'+rows[i]['id'])
    # The cache diagnostic changes only F0's term caller and adds a clone.
    cache_manifest=load(BASE/'full-early-cache-v1/manifest.json')
    scope=cache_manifest['protected_relay13_full_fault'];delta=scope['diagnostic_rtl_delta']
    need(len(delta)==2 and scope['eventual_duplicate_abort_only'] and
        scope['origin_age_validation_not_proved'] and
        scope['extra_early_token_and_genuine_later_row3_token_both_retained'],'CACHE_EXPLICIT_SCOPE')
    actual={Path(n).name:p for n,p in rows[6]['compiled_sources'].items()}
    need(rows[6]['compiled_sv_count']==60 and
        all(actual.get(n)==p for n,p in bundle['generated_sha256'].items() if 'rtl/'+n not in delta),
        'CACHE_ONLY_F0_AND_CLONE')
    long=rows[4]['steps'][0]['measurements']
    need((long['squares'],long['descriptors'],long['doubles'],long['reads'],long['interval'],long['joint_cycles'])==
        (2000,1998,1022,262144,8464,9852767) and long['initial_resets']==1 and long['initial_load_words']==131072,
        'OWN_UNINTERRUPTED1000')
    ledger=ROOT/'results/throughput-20260929/trackS-protected-relay13-ledger-v1/publication-ledger-native2-100-1000-v1.json'
    need(load(ledger)['sample']['pair_completion_cycles']==16182916927 and
        set(load(ledger)['jobs'])=={'2','100','1000'} and load(ledger)['selected_period_ns'] is None,'OWN_LEDGER')
    value=dict(schema='stream27-protected-r13-numerical-evidence-index-v1',
        status='OWN_TEN_NUMERICAL_SCOPED_FAULT_GATES_PASS_TARGETED_REVIEW_CLOCK_PENDING',
        created_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),owner='merged-ntt-model',
        producer=pin(ROOT/SELF),receipt_mechanics_only=pin(ROOT/'reference/stream27_context_storage_combo_oneshot_numerical_index.py'),
        production=dict(bundle=pin(bp),manifest=pin(mp),aw8_bundle=pin(NORMAL/'aw8-normal/production-bundle.json'),
            production_sv_count=58,full_compiled_sv_count=59,parameters=manifest['build']['parameters'],
            all58_generated_sha256=bundle['generated_sha256'],source_dependency_pins=bundle['source_sha256'],
            top=bundle['top'],geometry=bundle['geometry'],rtl_ready_at_utc='2026-10-02T23:47:23Z',
            lean_production=False,host_GL_implemented=False,protected_fault_rollback_claim=False),
        jobs=rows,own_healthy_source_native_ledger=pin(ledger),
        own_ledger_producer=pin(ROOT/'reference/stream27_protected_relay13_healthy_join.py'),
        scopes=dict(transport='Exactly forward/inverse/term matched full25 tuple relays; CRT OFF. '
            'Own PW4208/SINK8420/carry4142/I8464/cache78/seeds71..74; physical oldFIFO0/full plus explicit feedbackq1. '
            'No inner BF or term E4 recurrence change; added latency recomputed, not free.',
            healthy='Single-active runs of SAME C2 source versus joint plus independent reference; not C1 equivalence.',
            wrap='Three HOST timestamp aliases only; actual external cold accepts2 and table events4/field. '
                'Protocol/datapath/watchdog time not forced; context/epoch/gen checks, not independent bank oracle.',
            cache='Extra early matching seed token observed; genuine row3 token retained. Eventual duplicate-abort/no publication only, NOT origin-age validation.',
            crosstalk='One native output-word bit0 mismatch, all65536 peer words unchanged; NOT production RAM/configuration fault.',
            reset='COUNT2 seed65534 ends65535: no epoch wrap from reset footer. Actual own1000 crosses epoch16 wrap.',
            PRP='Own N256 full b^256 outputs plus same-DUT impulse special-minus-one; no primality/fullN sample claim.',
            protected_RAW_FAST_relay_fixture='Separate core AUTHOR cohort; own source/gates and nonauthor review required, never FIELD100 inheritance.',
            representative_owner_corruptions_only=True,no_arbitrary_FF_XZ_immunity_claim=True,
            raw_tails_after_HOST_watch_not_universal_flush=True,no_reload_or_checkpoint_in1000=True,
            no_ancestor_source_execution_forecast_clock_inheritance=True,full_N_numeric_locally_performed=False),
        final_promotion=dict(targeted_fixture_and_partitioned_review_pending=True,own_physical_clock_pending=True,
            advisor_acceptance_pending=True,selected_period_ns=None,projected_pair_seconds=None,
            projected_amortized_seconds=None,promotion_allowed=False))
    with out.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    return dict(index=str(out),sha256=sha(out),own_jobs=len(rows),status=value['status'])

if __name__=='__main__':
    import json
    print(json.dumps(prepare(),indent=2))
