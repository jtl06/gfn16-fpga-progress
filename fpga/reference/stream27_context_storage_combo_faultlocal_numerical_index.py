"""Own R7 index of existing automatic receipts; no arithmetic/native replay."""
from datetime import datetime, timezone
import json
from pathlib import Path

# Reuse receipt-reading mechanics only, never R6 outcomes or source attribution.
from stream27_context_storage_combo_oneshot_numerical_index import job, load, pin, sha

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-faultlocal-ownlong-v1'
NORMAL = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-faultlocal-native-v1'
IDS = [
    's4-p16-c2-combo-r7-aw8-normal-q1-v1',
    's4-p16-c2-combo-r7-full-normal-q1-v1',
    's4-p16-c2-combo-r7-paired-normal-q1-v1',
    's4-p16-c2-combo-r7-paired-fault-q1-v1',
    's4-p16-c2-combo-r7-own100-serial-q1-v1',
    's4-p16-c2-combo-r7-full-contracts-q1-v1',
    's4-p16-c2-combo-r7-full-early-cache-q1-v1',
    's4-p16-c2-combo-r7-full-wrap-normal-q1-v1',
    's4-p16-c2-combo-r7-crosstalk-q1-v1',
    's4-p16-c2-combo-r7-continuous1000-q1-v1',
]


def need(ok, why):
    if not ok:
        raise ValueError('R7_NUMERICAL_INDEX_' + why)


def production_join(receipt, generated):
    actual = {Path(name).name: digest for name, digest in receipt['compiled_sources'].items()}
    return dict(
        exact_generated_files=[name for name, digest in generated.items() if actual.get(name) == digest],
        absent_or_diagnostic_changed_files={name: dict(expected=digest, actual=actual.get(name))
                                           for name, digest in generated.items() if actual.get(name) != digest},
    )


def prepare():
    out = BASE / 'numerical-index-v1.json'
    need(not out.exists(), 'FRESH_INDEX')
    bundle_path = NORMAL / 'full-normal/production-bundle.json'
    bundle = load(bundle_path)
    normal = load(NORMAL / 'full-normal/manifest.json')
    need(len(bundle['files']) == 55 and normal['build']['parameters'] ==
         dict(bundle['parameters'], EPOCH_SEED0=65534, EPOCH_SEED1=42), 'OWN55_PARAMETERS')
    need(bundle['parameters']['COMM_OWNER_COMPARE_LOCAL'] == 1 and
         bundle['parameters']['COLD_SECOND_ONESHOT'] == 1, 'OWN_FLAGS')
    binder = ROOT / 'reference/stream27_context_storage_combo_faultlocal_bind.py'
    need(sha(binder) == '847dc928e3c84e565d8971fbd05e65ff2e3d50627e0d8b8347ff2ae025918d06', 'FROZEN_BINDER')
    jobs = [job(identifier) for identifier in IDS]
    for receipt in jobs:
        # Keep non-measurement typed scopes (wrap/fault coverage) verbatim as well.
        raw = load(receipt['gate']['path'])
        receipt['typed_validation_scopes'] = [
            {key: value for key, value in (step.get('validation') or {}).items()
             if key != 'measurements'} for step in raw['steps']
        ]
        if receipt['id'] != IDS[0] and '-paired-' not in receipt['id']:
            receipt['own_full_production_join'] = production_join(receipt, bundle['generated_sha256'])
    for position in (1, 4, 7, 8, 9):
        need(len(jobs[position]['own_full_production_join']['exact_generated_files']) == 55,
             'EXACT_OWN55_' + jobs[position]['id'])
    long = jobs[-1]['steps'][0]['measurements']
    need(long['squares'] == 2000 and long['descriptors'] == 1998 and long['doubles'] == 1022 and
         long['reads'] == 262144 and long['initial_resets'] == 1 and long['initial_load_words'] == 131072 and
         long['interval'] == 8459 and long['joint_cycles'] == 9847766 and long['peer_live_reads'] == 65536 and
         long['signed96'] and long['independent_reference'], 'OWN_UNINTERRUPTED1000')
    need(jobs[1]['steps'][0]['measurements']['joint_cycles'] == 1405684 and
         jobs[4]['steps'][0]['measurements']['joint_cycles'] == 2234666, 'OWN_NORMAL_PILOT_CALENDAR')
    root = bundle['top'] + '.sv'
    value = dict(
        schema='stream27-c2-r7-numerical-evidence-index-v1',
        status='OWN_TEN_NUMERICAL_AND_SCOPED_FAULT_GATES_PASS_OWN_LEDGER_CLOCK_PENDING',
        created_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        owner='merged-ntt-model',
        receipt_mechanics_only=pin(ROOT / 'reference/stream27_context_storage_combo_oneshot_numerical_index.py'),
        production=dict(
            binder=pin(binder), captured_bundle=pin(bundle_path),
            captured_manifest=pin(NORMAL / 'full-normal/manifest.json'),
            aw8_bundle=pin(NORMAL / 'aw8-normal/production-bundle.json'),
            production_sv_count=55, native_full_observer_sv_count=1, top=bundle['top'],
            root_sha256=bundle['generated_sha256'][root], all55_generated_sha256=bundle['generated_sha256'],
            source_dependency_pins=bundle['source_sha256'], compiled_parameters=normal['build']['parameters'],
            geometry=bundle['geometry'], rtl_ready_at_utc='2026-10-02T14:08:53Z',
            source_delta='Compare upper/current and upper/delayed owners before phase; one-bit select. '
                         'Registers/data/tags/fault edges and accepted-one-shot host are literal R6.',
            single_context_scope='Single-active context0/context1 runs of SAME C2 RTL, not C1-source pairing.',
        ),
        jobs=jobs,
        source_delta_review=pin(ROOT / 'results/throughput-20260929/'
                               's4-p16-c2-combo-r7-faultlocal-source-independent-v1.json'),
        own_source_sample_join=dict(status='PENDING_CORE_OWN_SOURCE_JOIN', own_native1000_pair_cycles=9847766,
                                    no_R6_numerical_or_clock_inheritance=True),
        scopes=dict(
            paired_faults='Actual identical native-only old/new head-upper-tag XOR: valid/context/all25GEN '
                          'bits, both occupied phases, 16 geometries; 864 cases. PRE owner_bad/fault_pending '
                          'and POST sticky error/admitted raw tail/reset/quarantine paired.',
            binary_source_equivalence_not_arbitrary_X=True,
            fullwrap='OWN R7 full geometry, three HOST-timestamp aliases only; real arithmetic/protocol/watchdog '
                     'clocks not forced. Actual context/epoch/generation sequence, not independent bank oracle.',
            billions_of_protocol_edges_claim=False,
            unchanged_host_component_reference='R6 AW8 wrap and old-proposal mutant are ancestor component '
                                               'evidence only, not any of these ten OWN R7 results.',
            fullcache='Early matching token with genuine later token retained: eventual duplicate-abort/no '
                      'publication only, NOT immediate origin-age rejection.',
            crosstalk='One native-only output-word bit mutation; all65536 peer words and metadata unchanged. '
                      'NOT production RAM/configuration fault.',
            reset='Own fullCOUNT2/seed65534 ends65535; no wrap credit there. Own1000 crosses epoch16 wrap.',
            healthy_retirement='Noncolliding legal traces; forced cold/auto collision retains literal sticky-abort '
                               'authority, no native collision case claimed.',
            representative_full_owner_bits_not_exhaustive=True, no_unknown_arbitrary_fault_protection_claim=True,
            no_reload_or_checkpoint_in_own1000=True, full_N_numeric_locally_performed=False,
            old_C2_complete_sample_projections_promotion='HOLD; finite/native/layout evidence preserved.',
        ),
        final_promotion=dict(own_numerical_independent_review_pending=True, own_source_ledger_pending=True,
                             own_physical_clock_pending=True, advisor_acceptance_pending=True,
                             selected_period_ns=None, projected_pair_seconds=None,
                             projected_amortized_seconds=None, promotion_allowed=False,
                             no_board_or_measured_full_sample_PRP_claim=True),
    )
    with out.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    return dict(index=str(out), sha256=sha(out), own_jobs=len(jobs), status=value['status'])


if __name__ == '__main__':
    print(json.dumps(prepare(), indent=2))
