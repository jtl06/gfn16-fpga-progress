"""Own R14-F raw-completion calendar join; no native/oracle replay or clock."""
from datetime import datetime, timezone
import json

from .stream27_context_storage_combo_oneshot_numerical_index import ROOT, job, load, pin, sha
from fpga.tools import native_long_class_v2 as runtime

SELF = ROOT / 'reference/stream27_r14f_host_offload_healthy_ledger_v1.py'
BASE = ROOT / 'results/throughput-20260929/trackS-r14f-host-offload-ownlong-v1'
FULL = BASE / 'continuous1000-source-v1'
SHORT_ID = 's4-r14f-host-offload-own100-q1-v1'
LONG_ID = 's4-r14f-host-offload-continuous1000-q1-v1'
NORMAL_ID = 's4-r14f-b-equivalence-full-normal-q1-v1'
SAMPLE_K = 1911814


def need(ok, why):
    if not ok:
        raise ValueError('R14F_HEALTHY_LEDGER_' + why)


def calendar(count):
    need(type(count) is int and 1 <= count <= 0xffffffff, 'COUNT32')
    first = [204, 4434]
    last = [edge + (count - 1) * 8461 for edge in first]
    warm = [edge + 12558 + 1 for edge in last]
    done = [edge + 2 for edge in warm]
    return dict(count_per_context=count, interval=8461, carry_done=12558,
                first_edges=first, last_launch_edges=last, warm_edges=warm,
                raw_done_edges=done, pair_raw_completion_cycles=max(done),
                raw_done_after_warm_edges=2, canonical_copy_or_publication_cost_used=False)


def prepare(*, join_long=False):
    out = BASE / ('healthy-source-native2-100-1000-ledger-v1.json' if join_long
                  else 'healthy-source-native2-100-ledger-v1.json')
    need(not out.exists(), 'FRESH_OUTPUT')
    manifest_path = FULL / 'manifest.json'
    manifest = load(manifest_path)
    build = manifest['build']
    need(build['top'] == 'genefer_stream27_host_contexts_aw16_p16_protected_field100_v1_r14f_v1'
         and len(build['sv_sources']) == 66 and build['runtime_threads'] == 1
         and build['parameters'] == dict(runtime.C2_FIELD100_SOURCE_TEMPLATE['parameters'], HOST_OFFLOAD=1),
         'OWN_FIELD100_RELAY_OFF_ON66')
    required = set(build['sv_sources']) | {
        runtime.R14F_CPP, 'rtl/tb/native_runtime_context_v1.h',
        'rtl/tb/stream27_host_offload_host_v2.h', 'rtl/tb/stream27_host_chain_full_reference_v1.h',
        'rtl/tb/stream27_shared_reference_ntt_v1.h'}
    model_map = {name: manifest['sources'][name] for name in sorted(required)}
    need(runtime.duration.digest(model_map) == runtime.R14F_MODEL_PINS_DIGEST,
         'EXACT_OWN66_CPP_C_REFERENCE_RUNTIME')
    source = FULL / 'source/fpga'
    need(all(sha(source / name) == digest for name, digest in model_map.items()), 'CAPTURED_MODEL_BYTES')
    need(manifest['sources']['reference/stream27_host_offload_field100_v1.py'] ==
         '6a9920ca2b704145553ed9f5fc13d0e6f97de78b0f89a960801bf7919b184633', 'OWN_F_COMPILER')
    paths = dict(forecast=FULL / 'own-pilot-forecast.json',
                 pilot_manifest=ROOT / 'queue/evidence' / SHORT_ID / 'attempt-0/collected/output/native/approved-manifest.json',
                 pilot_report=ROOT / 'queue/evidence' / SHORT_ID / 'attempt-0/collected/output/native/report.json',
                 pilot_gate=ROOT / 'queue/evidence' / SHORT_ID / 'gate-receipt.json')
    admission = runtime.duration_for(1).assess(manifest, {k: load(p) for k, p in paths.items()},
                                             {k: sha(p) for k, p in paths.items()}, 'gfn16-pilot-c4d')
    need(admission['status'] == 'PASS_R14F_own_measured_finite_duration_only', 'OWN_PILOT_ASSESSMENT')
    normal, short = job(NORMAL_ID), job(SHORT_ID)
    normal_map = {name.rsplit('/', 1)[-1]: digest for name, digest in normal['compiled_sources'].items()}
    need(normal['compiled_parameters'] == build['parameters']
         and all(normal_map.get(name.rsplit('/', 1)[-1]) == manifest['sources'][name]
                 for name in build['sv_sources']), 'ACTUAL_TWIN_ALL66_SOURCE_PARAMETERS')
    rows = {'100': short}
    if join_long:
        rows['1000'] = job(LONG_ID)
    native = {}
    for key, row in rows.items():
        count = int(key)
        expect = calendar(count)
        measured = row['steps'][0]['measurements']
        need(row['compiled_top'] == build['top'] and row['compiled_parameters'] == build['parameters']
             and row['compiled_sv_count'] == 66
             and all(row['compiled_sources'].get(name) == manifest['sources'][name]
                     for name in build['sv_sources']), 'ACTUAL_OWN_LONG_SOURCE')
        need(measured['count'] == count and measured['squares'] == 2 * count
             and measured['descriptors'] == 2 * (count - 1)
             and measured['doubles'] == sum(map(sum, runtime.r14f_bits(count)))
             and measured['initial_resets'] == measured['model_threads'] == 1
             and measured['checked_words'] == 131072
             and measured['warm_edges'] == expect['warm_edges']
             and measured['done_edges'] == expect['raw_done_edges']
             and measured['cycles'] == expect['pair_raw_completion_cycles'], 'ACTUAL_RAW_WARM_DONE_CALENDAR')
        native[key] = dict(receipts=row, calendar=expect)
    g = manifest['context_protected_field100']['geometry']
    frame_models = {}
    for count in (100, 1000):
        model = runtime.c2_frame_calendar(g, count, 8461, boundary_inputreg=1,
                                         inverse_only=1, protected_field100=1)
        frame_models[str(count)] = dict(status=model['status'], frames=model['frames'],
            launch_gaps=model['launch_gaps'], lease_peak=model['lease_peak'],
            minimum_cache_margin=min(row['margin'] for row in model['correction']),
            feedback_old_fifo_rows=model['feedback_old_fifo_rows'],
            explicit_feedback_register_rows=model['explicit_feedback_register_rows'],
            source_geometry_only_not_parent_native_credit=True)
    value = dict(schema='r14f-own-source-raw-completion-ledger-v1',
        status='OWN_FROZEN_SOURCE_NATIVE2_NUMERICAL_AND_NATIVE100_CALENDAR_JOIN_PASS'
               if not join_long else 'OWN_FROZEN_SOURCE_NATIVE2_NUMERICAL_AND_NATIVE100_1000_CALENDAR_JOIN_PASS',
        created_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        owner='/root/merged_ntt_model', producer=pin(SELF), own_source_manifest=pin(manifest_path),
        own_model_pins=model_map, own_compiled_parameters=build['parameters'],
        native2_twin=normal, native2_calendar=calendar(2),
        native2_absolute_edges_logged=False,
        native2_scope='Actual twin checks every launched/completed count and W+2 raw completion; '
                      'typed packet bodies/full56 owners are recorded, absolute warm/done edges are not logged.',
        native_calendars=native, source_frame_models=frame_models,
        sample=dict(**calendar(SAMPLE_K), conditional_source_model_only=True,
                    measured_full_sample=False, no_parent_sample_ledger_inherited=True,
                    equal_count_ordinary_timely_feed_only=True),
        selected_period_ns=None, projected_pair_seconds=None, projected_amortized_seconds=None,
        host_time_excluded_from_chip_cycles=True, transport_or_host_GL_implemented=False,
        canonical_FIELD100_R13_copy_publication_ledger_not_used=True,
        old_R14_or_R13_numeric_runtime_clock_not_inherited=True,
        host_C_sample_time_not_rebenchmarked=True,
        selected_clock_independent_review_and_advisor_pending=True, promotion_allowed=False,
        limits=['No measured full-sample PRP, board or individual test latency.',
                'Pilot command includes reference, host staging, DUT and finalization; not pure DUT seconds.',
                'Raw completion uses always-ready host stream; transport/backpressure/GL/rollback are not implemented.',
                'No new native or full-N numerical oracle replay during this metadata join.',
                'New F1000 joins only after its own actual typed terminal; historical R14 results never count.'])
    with out.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    return dict(ledger=str(out), sha256=sha(out), sample=value['sample'], status=value['status'])


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--join-long', action='store_true')
    args = parser.parse_args()
    print(json.dumps(prepare(join_long=args.join_long), indent=2))
