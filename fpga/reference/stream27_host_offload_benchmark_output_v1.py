"""Pure typed validator for retained B host-only timing JSON, no arithmetic."""
import json
import math
import re
import statistics

PHASES = ('profile_wall', 'cold_conversion_wall', 'finalization_wall',
          'profile_cpu', 'cold_conversion_cpu', 'finalization_cpu')


def need(ok, why):
    if not ok:
        raise ValueError('HOST_OFFLOAD_TIMING_' + why)


def validate(stdout, stderr, returncode, config, assets):
    need(type(stdout) is str and type(stderr) is str and type(returncode) is int and
         returncode == 0 and stderr == '' and len(stdout) < 65536,
         'ACTUAL_COMMAND_OUTPUT')
    need(type(config) is dict and set(config) == {'repetitions', 'source_sha256'} and
         type(config['repetitions']) is int and 1 <= config['repetitions'] <= 5 and
         type(config['source_sha256']) is dict and assets == {}, 'EXACT_CONFIG')
    report = json.loads(stdout)
    need(report['status'] == 'PASS_host_conversion_measurement_only' and
         report['host'].split('.')[0] == 'aethia' and report['platform'].startswith('linux'),
         'HOST_SCOPE')
    need(report['sources'] == config['source_sha256'] and len(report['sources']) == 7 and
         all(type(v) is str and re.fullmatch('[0-9a-f]{64}', v) for v in report['sources'].values()),
         'SOURCE_PINS')
    expected = dict(n=65536, p=16, base=604832956, repetitions=config['repetitions'],
                    input_residue_words=196608, final_digit_words=65536, final_boundary_words=32)
    need(all(type(report.get(k)) is int and report[k] == value for k, value in expected.items()),
         'EXACT_SIZED_MEASUREMENT')
    need(report['native_core_equivalence'] is False and report['promotion_allowed'] is False and
         all(report[k] is None for k in ('measured_backend_seconds', 'transport_seconds', 'prp_wall_seconds')),
         'NO_BACKEND_PRP_OR_EQUIVALENCE_INFERENCE')
    need(type(report['max_self_rss_kib']) is int and 0 < report['max_self_rss_kib'] <= 4 * 1024 * 1024 and
         type(report['output_sha256']) is str and re.fullmatch('[0-9a-f]{64}', report['output_sha256']),
         'BOUNDED_RSS_OUTPUT_HASH')
    for phase in PHASES:
        values = report[phase]
        need(set(values) == {'samples_seconds', 'minimum_seconds', 'median_seconds', 'maximum_seconds'},
             'PHASE_FIELDS')
        samples = values['samples_seconds']
        need(type(samples) is list and len(samples) == config['repetitions'] and
             all(type(v) in (float, int) and math.isfinite(v) and 0 <= v <= 60 for v in samples),
             'FINITE_TIME_SAMPLES')
        need(all(type(values[k]) in (float, int) and math.isfinite(values[k]) and 0 <= values[k] <= 60
                 for k in ('minimum_seconds', 'median_seconds', 'maximum_seconds')), 'FINITE_SUMMARY_VALUES')
        need(values['minimum_seconds'] == min(samples) and
             values['median_seconds'] == statistics.median(samples) and
             values['maximum_seconds'] == max(samples), 'ACTUAL_SAMPLE_SPREAD')
    need(sum(sum(report[phase]['samples_seconds']) for phase in PHASES[:3]) <= 60,
         'FINITE_TOTAL_TIMING')
    return dict(status='PASS_expected_contracts', host_only=True, numerical_backend_seconds=None,
                profile_seconds=report['profile_wall']['median_seconds'],
                cold_conversion_seconds=report['cold_conversion_wall']['median_seconds'],
                finalization_seconds=report['finalization_wall']['median_seconds'],
                native_core_equivalence=False, promotion_allowed=False)
