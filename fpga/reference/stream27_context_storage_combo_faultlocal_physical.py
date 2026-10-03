"""Bounded R7 physical preparation, secondary to fixed-source R6."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path

from . import stream27_context_storage_combo_faultlocal_bind as candidate
from .stream27_context_storage_combo_physical import ROOT, sha, need, read, encoded

PARENT = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-oneshot-physical-v1/physical-16000-v1'
GENERATOR = ROOT / 'reference/stream27_context_storage_combo_faultlocal_bind.py'
PIN = '847dc928e3c84e565d8971fbd05e65ff2e3d50627e0d8b8347ff2ae025918d06'


def build(role, gate):
    need(sha(GENERATOR.read_bytes()) == PIN, 'frozen R7 generator')
    full = candidate.prepare(65536, p=16, contexts=2, enabled=1)
    small = candidate.prepare(256, p=16, contexts=2, enabled=1)
    role = Path(role).resolve()
    native = read(role / 'manifest.json')
    need(read(role / 'production-bundle.json')['files'] == small['files'], 'own R7 AW8 exact production source')
    params = dict(native['build']['parameters'], AW=16)
    need(params == dict(full['parameters'], EPOCH_SEED0=65534, EPOCH_SEED1=42), 'own R7 compiled parameters')
    parent = read(PARENT / 'project/manifest.json')
    need(len(full['files']) == len(small['files']) == 55 and full['geometry'] == parent['geometry'], 'source55/calendar unchanged')
    controls = {}
    for name, pin in parent['control_sha256'].items():
        raw = (PARENT / 'project' / name).read_bytes()
        need(sha(raw) == pin, 'immutable R6 controls ' + name)
        controls[name] = raw
    qsf = '\n'.join(line for line in controls['probe.qsf'].decode().splitlines()
                    if not line.startswith('set_global_assignment -name SYSTEMVERILOG_FILE ')) + '\n'
    qsf = qsf.replace(parent['top'], full['top'])
    qsf += 'set_parameter -name COMM_OWNER_COMPARE_LOCAL 1\n'
    qsf += ''.join('set_global_assignment -name SYSTEMVERILOG_FILE rtl/' + name + '\n' for name in full['files'])
    controls['probe.qsf'] = qsf.encode()
    manifest = copy.deepcopy(parent)
    manifest.update(status='prepared_R7_compare_before_phase_provisional', top=full['top'], core_parameters=params,
        source_sha256=full['generated_sha256'], generator_source_sha256=full['source_sha256'],
        control_sha256={name: sha(raw) for name, raw in controls.items()},
        native_normal_id=gate, native_role_manifest_sha256=sha((role / 'manifest.json').read_bytes()),
        context_storage_combo_faultlocal=full['context_storage_combo_faultlocal'],
        notes=['R7 full valid/context/GEN comparisons before phase, selects one bad bit; no secondary protocol absorption.',
               'Exact R6 host one-shot/reverse; all FF/reset/owner/data/tag/publication edges and geometry unchanged.',
               'Own quicknormal required. R6 wrap prerequisite covers unchanged host component only, not R7 full qualification.',
               '16ns Balanced/seed1/actual AWS12/40GiB full4h; launch before16UTC only within actual guards. No area/clock benefit promised.'])
    spec = read(PARENT / 'structural-inventory.json')
    old, new = 'rtl/' + parent['top'] + '.sv', 'rtl/' + full['top'] + '.sv'
    def remap(value):
        if isinstance(value, dict):
            return {k: remap(v) for k, v in value.items()}
        if isinstance(value, list):
            return [remap(v) for v in value]
        return new if value == old else value
    spec = remap(spec)
    spec['identity'].update(top=manifest['top'], parameters=params)
    spec['sources'] = {'rtl/' + name: pin for name, pin in manifest['source_sha256'].items()}
    spec['settings'] = dict(manifest['control_sha256'], **{'manifest.json': sha(encoded(manifest))})
    spec['exclusions'].append(dict(kind='inside_single_macroblock',
        reason='R7 packed-stage full tag mismatch comparisons move before phase selection. Existing continuity check and all registers/edges/data/tag routing remain exact; no protocol absorption, no timing exception.',
        endpoints=['field0/1/2 CT/GS packed commutator owner_bad']))
    proof = dict(schema='fit-provisional-aw8-geometry-v1', generator=dict(path=str(GENERATOR), sha256=PIN),
                 kwargs=dict(p=16, contexts=2, enabled=1), native_n=256, fit_n=65536)
    requires = read(PARENT / 'requires.json')
    for requirement in requires:
        path = Path(requirement['path'])
        need(sha(path.read_bytes()) == requirement['sha256'] and read(path)['status'] == 'PASS_expected_contracts', 'unchanged R6 host component wrap evidence')
    files = {'rtl/' + name: text.encode() for name, text in full['files'].items()}
    files.update(controls)
    return manifest, files, spec, proof, requires


def prepare(output, role, gate):
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists(), 'fresh R7 physical output')
    manifest, files, spec, proof, requires = build(role, gate)
    for name, raw in files.items():
        path = out / 'project' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    (out / 'project/manifest.json').write_bytes(encoded(manifest))
    loader = importlib.util.spec_from_file_location('r7_structure', ROOT / 'tools/prefit_structural_guard_v1.py')
    checker = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(checker)
    result = checker.source_inventory(out / 'project', spec)
    need(not result['findings'], 'source structural findings: ' + repr(result['findings']))
    for name, value in [('structural-inventory.json', spec), ('provisional-geometry.json', proof), ('requires.json', requires)]:
        (out / name).write_bytes(encoded(value))
    return dict(project=str(out / 'project'), source_count=55, crossings=len(spec['transfers']),
        structural_sha256=sha(encoded(spec)), provisional_sha256=sha(encoded(proof)),
        requires_sha256=sha(encoded(requires)), source_findings=result['findings'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--native-role', type=Path, required=True)
    parser.add_argument('--native-gate', required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.native_role, args.native_gate), indent=2))
