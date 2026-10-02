"""Owner replay of collected small-N soak evidence; not independent promotion.

No model executes and no GMP import occurs here. AW<=8 scalar integer boundary
checks complement the recorded Linux GMP validations. Full-N use is refused.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
ORACLE_SHA = '8075e2033a01b09b9bbc344b72f23df4ebbc90b8489caadfbd0546e6f3bcfe3a'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def archive(archive_path, expected):
    actual = {}
    with tarfile.open(archive_path, 'r:gz') as bundled:
        for entry in bundled:
            need(entry.isfile() and entry.name not in actual and entry.size <= 8 << 20,
                 'SOAK_REPLAY_ARCHIVE_TYPE')
            with bundled.extractfile(entry) as stream:
                actual[entry.name] = hashlib.file_digest(stream, 'sha256').hexdigest()
    need(actual == expected, 'SOAK_REPLAY_EXACT_ARCHIVE')


def replay(evidence):
    evidence = Path(evidence).resolve()
    native = evidence/'output/native'
    manifest = json.loads((evidence/'manifest.json').read_text())
    report = json.loads((native/'report.json').read_text())
    need(report['status'] == 'completed_native_commands_unreviewed'
         and report['manifest_sha256'] == sha(evidence/'manifest.json')
         and report['sources'] == manifest['sources'], 'SOAK_REPLAY_NATIVE_SOURCE_BINDING')
    need(manifest['build']['parameters']['AW'] <= 8, 'SOAK_REPLAY_SMALL_ONLY')
    need(manifest['sources']['reference/core27_crtmont_soak_v1.py'] == ORACLE_SHA
         == sha(ROOT/'reference/core27_crtmont_soak_v1.py'), 'SOAK_REPLAY_FROZEN_ORACLE')
    spec = importlib.util.spec_from_file_location('_soak_scalar_replay', ROOT/'reference/core27_crtmont_soak_v1.py')
    oracle_module = importlib.util.module_from_spec(spec); spec.loader.exec_module(oracle_module)
    archive(native/'sources.tar.gz', manifest['sources'])
    archive(native/'generated-sources.tar.gz', report['generated_source_sha256'])
    for name, pin in report['artifacts'].items():
        need(sha(native/name) == pin, 'SOAK_REPLAY_NATIVE_ARTIFACT_DRIFT')
    with gzip.open(native/'model.gz', 'rb') as stream:
        need(hashlib.file_digest(stream, 'sha256').hexdigest() == report['executable_sha256'],
             'SOAK_REPLAY_MODEL_IDENTITY')
    need(report['probe'] == manifest['probe']['expected_json']
         == dict(context_threads=1, model_threads=1, expected_threads=1), 'SOAK_REPLAY_PROBE')
    for phase in ('lint', 'build'):
        admission = report[phase+'_admission']
        need(admission['classification'] == 'style_only'
             and not admission['fatal_class_counts'] and not admission['unknown_class_counts']
             and not admission['error_streams'] and not admission['malformed_diagnostics'],
             'SOAK_REPLAY_CLASS_GATE')
    steps = {step['name']: step for step in report['steps']}
    results = {}
    # Read the captured sources without extracting or executing their contents.
    with tarfile.open(native/'sources.tar.gz', 'r:gz') as bundled:
        for contract in manifest['steps']:
            name, validator = contract['name'], contract['validator']
            step = steps[name]
            need(step['error'] is None and step['returncode'] == contract['expected_returncode']
                 and sha(native/step['log']) == step['sha256']
                 and sha(native/step['stderr_log']) == step['stderr_sha256'], 'SOAK_REPLAY_STEP_IDENTITY')
            oracle = json.loads(bundled.extractfile(validator['assets']['oracle']).read())
            plan, segment = oracle_module.check_oracle(oracle)
            need(plan['profile']['aw'] <= 8, 'SOAK_REPLAY_SMALL_ONLY')
            wanted = [check['step'] for check in segment['checkpoints']]
            states, _ = oracle_module.compute_states(plan, 'python-small-only', segment['end'], wanted)
            need([states[k] for k in wanted] == segment['checkpoints'], 'SOAK_REPLAY_SCALAR_BOUNDARIES')
            value = oracle_module.validate_rows((native/step['log']).read_text(),
                (native/step['stderr_log']).read_text(), step['returncode'], validator['config'], oracle)
            recorded = report['validations'][name]
            need(recorded['independent_gmpy2_boundary_replay'] is True
                 and recorded['oracle_sha256'] == hashlib.sha256(bundled.extractfile(validator['assets']['oracle']).read()).hexdigest()
                 and recorded['normal_log_sha256'] == step['sha256']
                 and recorded['auxiliary_reference_runtime']['status'] == 'passed_exact_auxiliary_reference_runtime',
                 'SOAK_REPLAY_RECORDED_GMP_BINDING')
            for key in ('status', 'case_id'):
                need(value[key] == recorded[key], 'SOAK_REPLAY_TYPED_VALIDATION')
            results[name] = dict(status=value['status'], scalar_boundary_replay=True,
                native_gmp_replay_recorded=True, returncode=step['returncode'],
                stdout_sha256=step['sha256'], stderr_sha256=step['stderr_sha256'])
    need(len(results) == 6 and sum(row['returncode'] == 1 for row in results.values()) == 4,
         'SOAK_REPLAY_COMPLETE_PILOT_SUITE')
    return dict(schema='crtmont-soak-owner-pilot-replay-v1',
        status='PASS_actual_AW5_native_pilot_owner_replay_exploration_only',
        manifest_sha256=sha(evidence/'manifest.json'), report_sha256=sha(native/'report.json'),
        replay_source_sha256=sha(__file__), executable_sha256=report['executable_sha256'],
        native_seconds=report['seconds'], validations=results,
        AW16_qualification=False, chunked_1000_coverage=False,
        uninterrupted_1000_square_rtl=False, independent_review=False, promotion_allowed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(replay(args.evidence), indent=2))
