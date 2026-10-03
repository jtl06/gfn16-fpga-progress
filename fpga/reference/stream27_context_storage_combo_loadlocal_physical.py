"""R5 exact physical preparation: R4 plus exclusive LOAD eligibility only."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path

from . import stream27_context_storage_combo_loadlocal_bind as candidate
from .stream27_context_storage_combo_physical import ROOT, sha, need, read, encoded

PARENT = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-readlocal-physical-v1/physical-16000-v1'
GENERATOR = ROOT / 'reference/stream27_context_storage_combo_loadlocal_bind.py'
PIN = 'c9173c97266126ebd8fb19ea6736b310bcc785427ff73da3505a9442e6bbdf2f'


def build(role, gate):
    need(sha(GENERATOR.read_bytes()) == PIN, 'frozen R5 generator')
    full = candidate.prepare(65536, p=16, contexts=2, enabled=1)
    small = candidate.prepare(256, p=16, contexts=2, enabled=1)
    role = Path(role).resolve()
    native = read(role / 'manifest.json')
    need(read(role / 'production-bundle.json')['files'] == small['files'], 'own AW8 production source')
    params = dict(native['build']['parameters'], AW=16)
    need(params == dict(full['parameters'], EPOCH_SEED0=65534, EPOCH_SEED1=42), 'actual native epoch parameters')
    parent = read(PARENT / 'project/manifest.json')
    need(len(full['files']) == len(small['files']) == 55, 'exact production55')
    need(full['geometry'] == parent['geometry'], 'R4 geometry unchanged')
    controls = {}
    for name, pin in parent['control_sha256'].items():
        raw = (PARENT / 'project' / name).read_bytes()
        need(sha(raw) == pin, 'immutable R4 control ' + name)
        controls[name] = raw
    qsf = '\n'.join(line for line in controls['probe.qsf'].decode().splitlines()
                    if not line.startswith('set_global_assignment -name SYSTEMVERILOG_FILE ')) + '\n'
    qsf = qsf.replace(parent['top'], full['top'])
    qsf += 'set_parameter -name CANONICAL_LOAD_LOCAL 1\n'
    qsf += ''.join('set_global_assignment -name SYSTEMVERILOG_FILE rtl/' + name + '\n' for name in full['files'])
    controls['probe.qsf'] = qsf.encode()
    manifest = copy.deepcopy(parent)
    manifest.update(status='prepared_R5_loadlocal_provisional_AW8_full_route', top=full['top'], core_parameters=params,
        source_sha256=full['generated_sha256'], generator_source_sha256=full['source_sha256'],
        control_sha256={name: sha(raw) for name, raw in controls.items()},
        native_normal_id=gate, native_role_manifest_sha256=sha((role / 'manifest.json').read_bytes()),
        context_storage_combo_loadlocal=full['context_storage_combo_loadlocal'],
        notes=['R5 immutable R4 plus ONLY exclusive legal_LOAD factoring; original load range/order and authoritative fault/FSM retained.',
               'No FF/latency/calendar/read/owner/publication changes. Own AW8 source/generator proof, full/fault/long independent.',
               '16ns Balanced/seed1; actual AWS12/40GiB by dispatch, full4h. No clock or area gain inferred.'])
    spec = read(PARENT / 'structural-inventory.json')
    rename = {'rtl/' + parent['top'] + '.sv': 'rtl/' + full['top'] + '.sv',
              'rtl/' + candidate.OLD + '.sv': 'rtl/' + candidate.NEW + '.sv'}
    def remap(value):
        if isinstance(value, dict):
            return {k: remap(v) for k, v in value.items()}
        if isinstance(value, list):
            return [remap(v) for v in value]
        return rename.get(value, value) if isinstance(value, str) else value
    spec = remap(spec)
    spec['identity'].update(top=manifest['top'], parameters=params)
    spec['sources'] = {'rtl/' + name: pin for name, pin in manifest['source_sha256'].items()}
    spec['settings'] = dict(manifest['control_sha256'], **{'manifest.json': sha(encoded(manifest))})
    transfer = next(t for t in spec['transfers'] if t['id'] == 'shadows_to_canonical_scratch')
    transfer['exception']['reason'] += ' R5 exclusive legal_LOAD excludes BEGIN-only correction bounds while preserving pending/exclusivity/base/load/order checks. Original authoritative fault priority/FSM/RAM write edge remain literal; no timing exception or added stage.'
    transfer['exception']['contract_anchors'].append(dict(source='rtl/' + candidate.NEW + '.sv', text=candidate.LOAD_AFTER))
    proof = dict(schema='fit-provisional-aw8-geometry-v1', generator=dict(path=str(GENERATOR), sha256=PIN),
                 kwargs=dict(p=16, contexts=2, enabled=1), native_n=256, fit_n=65536)
    files = {'rtl/' + name: text.encode() for name, text in full['files'].items()}
    files.update(controls)
    return manifest, files, spec, proof


def prepare(output, role, gate):
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists(), 'fresh R5 physical output')
    manifest, files, spec, proof = build(role, gate)
    for name, raw in files.items():
        path = out / 'project' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    (out / 'project/manifest.json').write_bytes(encoded(manifest))
    loader = importlib.util.spec_from_file_location('r5_structure', ROOT / 'tools/prefit_structural_guard_v1.py')
    checker = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(checker)
    result = checker.source_inventory(out / 'project', spec)
    need(not result['findings'], 'source structural findings: ' + repr(result['findings']))
    (out / 'structural-inventory.json').write_bytes(encoded(spec))
    (out / 'provisional-geometry.json').write_bytes(encoded(proof))
    return dict(project=str(out / 'project'), source_count=55, crossings=len(spec['transfers']),
        structural_sha256=sha(encoded(spec)), provisional_sha256=sha(encoded(proof)), source_findings=result['findings'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--native-role', type=Path, required=True)
    parser.add_argument('--native-gate', required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.native_role, args.native_gate), indent=2))
