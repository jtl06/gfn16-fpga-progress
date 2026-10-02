"""Immutable F3 soak role with explicit actual-host reference selection.

GCP uses its unchanged native adapter. Azure uses the already source-reviewed
two-runtime bridge, preserving original generation bytes and every boundary.
No package profile rewrites runtime assets. Source/data staging only; no native
launch or reference arithmetic occurs in prepare().
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
from fpga.reference import anext_writeback_soak_output_v1 as prior

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = 'donor/fpga/reference/core27_t5b_soak_cross_runtime_v1.py'
BRIDGE_SHA = '3be94f597e09455a2b9f3f363dfc6a4ac36a240eb26b22a1717e91a072ea1e83'
GENERATION_SHA = '84fb40c8e6452d4b660d9302e83584dd3c4761aa6219495e57f2df582401cf0b'
TARGETS = {
    'gfn16-azure-f16': ('target-f16', '1ed8253a93078657227941ea9e1f08d2420dc1a27d992f0e767b2136ebf5f8dc'),
    'gfn16-azure-sim-f32': ('target-burst', '1a5125fa55711298b5412df91105e47aa4c13b6b42ab32191fd8b23696f081f2'),
}
COMMON = {'oracle', 'runtime', 'generation-runtime', 'generation', 'generation-admission',
          'reference-config', 'reference-report', 'reference-execution'}
ASSETS = COMMON | {item[0] for item in TARGETS.values()}
ROLES = {
    'short': ('anext-writeback-qualification-short-role-v1', '89dcc87409ae717564c2880504c0c2760c8fc4b89bf81886dd9903f59dc67037',
              'soak-t5b-aw16-short-cross-burst16-manifest-v2', 'continuous'),
    'pilot': ('anext-writeback-qualification-pilot-role-v1', '3b074e2a39b6260679e4b369e5c6727f0f9d36182b2429bb509fa5843aaea738',
              'soak-t5b-aw16-chunk00-cross-burst16-manifest-v2', 'chunk-00'),
    'continuous': ('anext-writeback-qualification-continuous-role-v1', 'f8c142ff564d11f620b1c124651f5d9d2492b1c21ba6e349dffb49f0036bdc48',
              'soak-t5b-aw16-continuous-cross-burst16-manifest-v2', 'continuous'),
}
SELF = 'reference/anext_writeback_soak_portable_v1.py'


def need(ok, why):
    if not ok:
        raise ValueError('F3 portable: '+why)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def selected_assets(assets, host):
    need(set(assets) == ASSETS, 'exact original plus both target assets')
    need(text_sha(assets['runtime']) == text_sha(assets['generation-runtime']) == GENERATION_SHA,
         'byte-preserved original generation runtime')
    for target_host, (label, pin) in TARGETS.items():
        need(text_sha(assets[label]) == pin and json.loads(assets[label])['host'] == target_host,
             'exact declared target descriptor')
    need(host == 'gfn16-pilot-c4d' or host in TARGETS, 'actual admitted host')
    if host == 'gfn16-pilot-c4d':
        return {'oracle': assets['oracle'], 'runtime': assets['runtime']}
    result = {key: assets[key] for key in COMMON}
    result['runtime'] = assets[TARGETS[host][0]]
    return result


def bridge():
    path = ROOT/BRIDGE
    need(not path.is_symlink() and sha(path) == BRIDGE_SHA, 'unchanged closed cross-runtime bridge')
    spec = importlib.util.spec_from_file_location('_f3_portable_bridge', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate(stdout, stderr, returncode, config, assets):
    need(set(config) == {'negative'} and config['negative'] in ('none', 'boundary', 'loaded-state'),
         'exact normal/fault contract')
    need(sha(ROOT/'rtl/kernel/genefer_anext_writeback_core_v1.sv') == prior.CORE_SHA,
         'actual F3 candidate before arithmetic')
    host = socket.gethostname()
    chosen = selected_assets(assets, host)
    if host == 'gfn16-pilot-c4d':
        result = prior.validate(stdout, stderr, returncode, config, chosen)
    else:
        b = bridge()
        b.binding(chosen)  # Source/receipt metadata only, no GMP.
        d = prior.donor()
        admitted = d.admit_runtime(chosen['runtime'])  # Actual target BEFORE integer work/import.
        oracle = json.loads(chosen['oracle'])
        converted, metrics = prior.normalise(stdout, oracle, d.reference())
        value = b.validate(converted, stderr, returncode, config, chosen)
        result = dict(status='PASS_expected_contracts', candidate='A-next-writeback-v1',
                      candidate_core_sha256=prior.CORE_SHA, donor_reference_validation=value,
                      donor_runtime_admission=admitted, native_anext_metrics=metrics,
                      donor_provenance_unchanged=True, promotion_allowed=False)
    result.update(actual_reference_host=host, generation_reference_host='gfn16-pilot-c4d',
                  original_generation_not_rehosted=True,
                  actual_runtime_manifest_sha256=text_sha(chosen['runtime']),
                  declared_reference_hosts=['gfn16-pilot-c4d', *TARGETS])
    return result


def prepare(kind, output):
    from fpga.reference.anext_point_qualification_v1 import closed
    need(kind in ROLES, 'finite prepared recipe')
    role, pin, donor_name, segment = ROLES[kind]
    m, files = closed(role, pin)
    output = Path(output).resolve()
    need(not output.exists() and not (ROOT/'docs/briefs/PAUSE').exists(), 'fresh output/no PAUSE')
    donor_root = ROOT/'results/throughput-20260929'/donor_name
    dm = json.loads((donor_root/'cross-runtime-manifest.json').read_text())
    for name, expected in dm['sources'].items():
        path = donor_root/'source/fpga'/name
        need(not path.is_symlink() and sha(path) == expected, 'immutable donor closure '+name)
        key = 'donor/fpga/'+name
        data = path.read_bytes()
        need(key not in files or files[key] == data, 'no original donor overwrite '+name)
        files[key] = data
    for host, (label, pin) in TARGETS.items():
        name = 'soak-azure-f16-runtime-v1' if label == 'target-f16' else 'soak-azure-f32-runtime-v1'
        path = ROOT/'results/throughput-20260929'/name/'runtime.json'
        need(sha(path) == pin, 'existing actual target closure')
        files['portable/'+label+'.json'] = path.read_bytes()
    for name in (SELF, 'tests/test_anext_writeback_soak_portable_v1.py'):
        files[name] = (ROOT/name).read_bytes()
    normal = [step for step in m['steps'] if step['validator']['config'] == {'negative': 'none'}]
    need(len(normal) == 1, 'normal-first role')
    m['steps'] = normal
    step = normal[0]
    need(files[step['validator']['assets']['oracle']] == files['donor/fpga/soak/'+segment+'.json'],
         'unchanged exact arithmetic donor')
    paths = {key: 'donor/fpga/soak/cross-'+key+'.json' for key in COMMON-{'oracle', 'runtime'}}
    paths.update(oracle=step['validator']['assets']['oracle'], runtime=step['validator']['assets']['runtime'],
                 **{label: 'portable/'+label+'.json' for label, _ in TARGETS.values()})
    step['validator'].update(source=SELF, assets=paths)
    m['sources'] = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    destination = output/'source/fpga'
    destination.mkdir(parents=True)
    for name, data in files.items():
        target = destination/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (output/'manifest.json').write_text(json.dumps(m, indent=2)+'\n')
    result = dict(status='prepared_source_only_not_native', kind=kind, manifest_sha256=sha(output/'manifest.json'),
                  allowed_hosts=['gfn16-pilot-c4d', *TARGETS], compiled_sv=30,
                  original_GCP_role_unchanged=True, target_runtime_selected_only_at_validation=True,
                  target_timing_required_before_continuous=True, promotion_allowed=False)
    (output/'preparation.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=ROLES, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.kind, args.output), indent=2))
