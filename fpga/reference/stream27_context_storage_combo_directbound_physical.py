"""Optional R8 physical snapshot; no deadline override or numerical claim."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path

from . import stream27_context_storage_combo_directbound_bind as candidate
from .stream27_context_storage_combo_physical import ROOT, sha, need, read, encoded

PARENT = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-faultlocal-physical-v1/physical-16000-v1'
GENERATOR = ROOT / 'reference/stream27_context_storage_combo_directbound_bind.py'
PIN = 'd7b179631988fd9269f9e3ff955f9e28f58270051380d0149bfbb4a66077be56'


def build(role, gate):
    need(sha(GENERATOR.read_bytes()) == PIN, 'frozen R8 generator')
    full = candidate.prepare(65536, p=16, contexts=2, enabled=1)
    small = candidate.prepare(256, p=16, contexts=2, enabled=1)
    role = Path(role).resolve()
    native = read(role / 'manifest.json')
    need(read(role / 'production-bundle.json')['files'] == small['files'], 'own R8 AW8 production source')
    params = dict(native['build']['parameters'], AW=16)
    need(params == dict(full['parameters'], EPOCH_SEED0=65534, EPOCH_SEED1=42), 'actual own compiled parameters')
    parent = read(PARENT / 'project/manifest.json')
    need(len(full['files']) == len(small['files']) == 55 and full['geometry'] == parent['geometry'], 'source55/calendar exact')
    controls = {}
    for name, pin in parent['control_sha256'].items():
        raw = (PARENT / 'project' / name).read_bytes()
        need(sha(raw) == pin, 'immutable parent control ' + name)
        controls[name] = raw
    qsf = '\n'.join(line for line in controls['probe.qsf'].decode().splitlines()
                    if not line.startswith('set_global_assignment -name SYSTEMVERILOG_FILE ')) + '\n'
    qsf = qsf.replace(parent['top'], full['top'])
    qsf += 'set_parameter -name CANONICAL_C0_DIRECT 1\n'
    qsf += ''.join('set_global_assignment -name SYSTEMVERILOG_FILE rtl/' + name + '\n' for name in full['files'])
    controls['probe.qsf'] = qsf.encode()
    manifest = copy.deepcopy(parent)
    manifest.update(status='prepared_R8_signed33_direct_c0_provisional', top=full['top'], core_parameters=params,
        source_sha256=full['generated_sha256'], generator_source_sha256=full['source_sha256'],
        control_sha256={name: sha(raw) for name, raw in controls.items()},
        native_normal_id=gate, native_role_manifest_sha256=sha((role / 'manifest.json').read_bytes()),
        context_storage_combo_directbound=full['context_storage_combo_directbound'],
        notes=['R8 only signed33 c0 direct interval on live base; no c1, FF/cache, priority, reset, owner, one-shot, publication or calendar change.',
               'Own quicknormal required. R6 wrap prerequisite is unchanged-host component only, not R8 wrap/long qualification.',
               'ONE16ns Balanced/seed1/AWS12/40GiB full4h only if actual admission before16UTC after R7 audits. No preemption/deadline extension.',
               'Prepared-only if truthful launch unavailable. Integer proof is not measured timing/area benefit.'])
    spec = read(PARENT / 'structural-inventory.json')
    renames = {'rtl/' + parent['top'] + '.sv': 'rtl/' + full['top'] + '.sv',
               'rtl/' + candidate.OLD + '.sv': 'rtl/' + candidate.NEW + '.sv'}
    def remap(value):
        if isinstance(value, dict):
            return {k: remap(v) for k, v in value.items()}
        if isinstance(value, list):
            return [remap(v) for v in value]
        return renames.get(value, value) if isinstance(value, str) else value
    spec = remap(spec)
    spec['identity'].update(top=manifest['top'], parameters=params)
    spec['sources'] = {'rtl/' + name: pin for name, pin in manifest['source_sha256'].items()}
    spec['settings'] = dict(manifest['control_sha256'], **{'manifest.json': sha(encoded(manifest))})
    transfer = next(t for t in spec['transfers'] if t['id'] == 'shadows_to_canonical_scratch')
    transfer['exception']['reason'] += ' R8 BEGIN c0 bounds use exact signed33 direct interval including base0; c1 and fault priority/accepted edge unchanged. No cached1056FF bank or added cycle.'
    for _, text in candidate.CHANGES:
        transfer['exception']['contract_anchors'].append(dict(source='rtl/' + candidate.NEW + '.sv', text=text))
    proof = dict(schema='fit-provisional-aw8-geometry-v1', generator=dict(path=str(GENERATOR), sha256=PIN),
                 kwargs=dict(p=16, contexts=2, enabled=1), native_n=256, fit_n=65536)
    requires = read(PARENT / 'requires.json')
    for requirement in requires:
        path = Path(requirement['path'])
        need(sha(path.read_bytes()) == requirement['sha256'] and read(path)['status'] == 'PASS_expected_contracts', 'unchanged host component wrap evidence')
    files = {'rtl/' + name: text.encode() for name, text in full['files'].items()}
    files.update(controls)
    return manifest, files, spec, proof, requires


def prepare(output, role, gate):
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists(), 'fresh R8 physical output')
    manifest, files, spec, proof, requires = build(role, gate)
    for name, raw in files.items():
        path = out / 'project' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    (out / 'project/manifest.json').write_bytes(encoded(manifest))
    loader = importlib.util.spec_from_file_location('r8_structure', ROOT / 'tools/prefit_structural_guard_v1.py')
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
