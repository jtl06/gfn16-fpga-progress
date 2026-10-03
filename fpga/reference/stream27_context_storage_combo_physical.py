"""Source-exact combined C2 provisional AW8-to-full physical preparation.

No RTL transformation here. The native gate and dispatch independently join
the pinned generator, both captured ancestors, and actual compiled parameters.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

from . import stream27_context_storage_combo_bind as combo

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / 'results/throughput-20260929/trackS-c2-storage2-route14-v1'
NATIVE = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-native-v1/aw8-normal'
GENERATOR = ROOT / 'reference/stream27_context_storage_combo_bind.py'
GENERATOR_SHA = '9d34d0980209b48f90a8c2fa96a72fe537bef9094f3a56d71e4e80a4beef5243'
GATE = 's4-p16-c2-combo-aw8-normal-q1-v1'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def read(path):
    return json.loads(path.read_text())


def encoded(value):
    return (json.dumps(value, indent=2) + '\n').encode()


def build():
    need(sha(GENERATOR.read_bytes()) == GENERATOR_SHA, 'frozen combined generator')
    bundle = combo.prepare(65536, p=16, contexts=2, enabled=1)
    small = combo.prepare(256, p=16, contexts=2, enabled=1)
    captured = read(NATIVE / 'production-bundle.json')
    need(small['files'] == captured['files'], 'accepted AW8 exact production closure')
    need(len(bundle['files']) == len(small['files']) == 53, 'exact production53')
    parent = read(PARENT / 'project/manifest.json')
    need(bundle['geometry'] == parent['geometry'], 'original public calendar unchanged')
    params = dict(bundle['parameters'], EPOCH_SEED0=65534, EPOCH_SEED1=42)
    native = read(NATIVE / 'manifest.json')
    need(dict(native['build']['parameters'], AW=16) == params, 'actual native epoch parameters')
    files = {'rtl/' + name: text.encode() for name, text in bundle['files'].items()}
    for name, pin in parent['control_sha256'].items():
        raw = (PARENT / 'project' / name).read_bytes()
        need(sha(raw) == pin, 'original pre-vendor controls: ' + name)
        files[name] = raw
    qsf = files['probe.qsf'].decode()
    lines = [line for line in qsf.splitlines() if not line.startswith('set_global_assignment -name SYSTEMVERILOG_FILE ')]
    qsf = '\n'.join(lines).replace(parent['top'], bundle['top']) + '\n'
    qsf += ''.join('set_global_assignment -name SYSTEMVERILOG_FILE rtl/' + name + '\n' for name in bundle['files'])
    need('LAST_QUARTUS_VERSION' not in qsf and 'NUM_PARALLEL_PROCESSORS 4' in qsf, 'clean four-worker snapshot')
    files['probe.qsf'] = qsf.encode()
    manifest = {key: copy.deepcopy(parent[key]) for key in (
        'scope', 'edition', 'device', 'compile_processors', 'seed', 'clock_period_ns',
        'address_width', 'bitstream_generation', 'allowed_stages', 'raw_multiplier_parameters',
        'field_parameters', 'intermediate_snapshots')}
    manifest.update(status='prepared_combined_C2_provisional_AW8_full_route', top=bundle['top'],
        core_parameters=params, source_sha256={name: sha(text.encode()) for name, text in bundle['files'].items()},
        control_sha256={name: sha(files[name]) for name in parent['control_sha256']},
        geometry=bundle['geometry'], native_normal_id=GATE,
        native_role_manifest_sha256=sha((NATIVE / 'manifest.json').read_bytes()),
        generator_source_sha256=bundle['source_sha256'], context_storage_combo=bundle['context_storage_combo'],
        fit_allowed=False, promotion_allowed=False,
        notes=['Provisional full size: actual own AW8 normal required; full native/fault qualification remains parallel, not inherited.',
               'Combined original storage2 + packed delays + root weight retime + term payload lookahead; no lean/timing7/tagcompact/GEN.',
               '14ns Balanced/seed1/Azure4/32GiB; genuine full four-hour flow, no timing claim.',
               'Declared source crossing inventory is not synthesized connectivity completeness.'])
    spec = read(PARENT / 'structural-inventory.json')
    need(len(spec['transfers']) == 20, 'original twenty source crossings')
    rename = {'rtl/' + parent['top'] + '.sv': 'rtl/' + bundle['top'] + '.sv'}
    for f in range(3):
        old = [name for name in spec['sources'] if name.startswith('rtl/genefer_stream27_shared_warm_aw16_p16_f' + str(f))]
        need(len(old) == 1, 'unique original field root')
        rename[old[0]] = 'rtl/genefer_stream27_shared_warm_aw16_p16_f' + str(f) + '_storage_combo_v1.sv'
    def remap(value):
        if isinstance(value, dict):
            return {key: remap(item) for key, item in value.items()}
        if isinstance(value, list):
            return [remap(item) for item in value]
        return rename.get(value, value) if isinstance(value, str) else value
    spec = remap(spec)
    spec['identity'].update(top=manifest['top'], parameters=params)
    spec['sources'] = {'rtl/' + name: pin for name, pin in manifest['source_sha256'].items()}
    spec['settings'] = dict(manifest['control_sha256'], **{'manifest.json': sha(encoded(manifest))})
    spec['exclusions'].append(dict(kind='inside_single_macroblock',
        reason='New field-internal payload owner/row/B-coefficient lookahead FFs select data one edge ahead; original full-owner admission, cache/fault authority and public E4 calendar remain. Not a new inter-macroblock cycle or timing exception.',
        endpoints=['field0/1/2 protocol payload lookahead to term/B coefficient selection']))
    proof = dict(schema='fit-provisional-aw8-geometry-v1',
        generator=dict(path=str(GENERATOR), sha256=GENERATOR_SHA),
        kwargs=dict(p=16, contexts=2, enabled=1), native_n=256, fit_n=65536)
    return manifest, files, spec, proof


def prepare(output):
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists(), 'fresh owned combined output')
    manifest, files, spec, proof = build()
    for name, raw in files.items():
        path = out / 'project' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    (out / 'project/manifest.json').write_bytes(encoded(manifest))
    checker_spec = importlib.util.spec_from_file_location('combo_structural_guard', ROOT / 'tools/prefit_structural_guard_v1.py')
    checker = importlib.util.module_from_spec(checker_spec)
    checker_spec.loader.exec_module(checker)
    result = checker.source_inventory(out / 'project', spec)
    need(not result['findings'], 'exact source structural findings: ' + repr(result['findings']))
    (out / 'structural-inventory.json').write_bytes(encoded(spec))
    (out / 'provisional-geometry.json').write_bytes(encoded(proof))
    return dict(project=str(out / 'project'), source_count=53, declared_crossings=20,
        source_findings=result['findings'], native_source_gate=GATE,
        structural_sha256=sha(encoded(spec)), provisional_sha256=sha(encoded(proof)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))
