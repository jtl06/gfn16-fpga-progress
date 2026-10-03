"""R6 fixed-source preparation with mandatory actual accelerated-wrap gate."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path

from . import stream27_context_storage_combo_oneshot_bind as candidate
from .stream27_context_storage_combo_physical import ROOT, sha, need, read, encoded

PARENT = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-loadlocal-physical-v1/physical-16000-v1'
ROLE = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-oneshot-native-v1/aw8-normal'
GENERATOR = ROOT / 'reference/stream27_context_storage_combo_oneshot_bind.py'
PIN = '586117feeb61f81e6049d8bba942e843048b2d792f90ba612ebffd76da401810'
GATE = 's4-p16-c2-combo-r6-aw8-normal-q1-v1'
WRAP = ROOT / 'queue/evidence/s4-p16-c2-combo-r6-aw8-wrap-normal-q1-v3/gate-receipt.json'
WRAP_PIN = '108d162f194c6634c64a3f165717bd5e61936cc664af499286b485ef4f7f6bde'


def build():
    need(sha(GENERATOR.read_bytes()) == PIN, 'frozen R6 generator')
    full = candidate.prepare(65536, p=16, contexts=2, enabled=1)
    small = candidate.prepare(256, p=16, contexts=2, enabled=1)
    native = read(ROLE / 'manifest.json')
    need(read(ROLE / 'production-bundle.json')['files'] == small['files'], 'own AW8 production source')
    params = dict(native['build']['parameters'], AW=16)
    need(params == dict(full['parameters'], EPOCH_SEED0=65534, EPOCH_SEED1=42), 'own compiled parameters')
    need(sha(WRAP.read_bytes()) == WRAP_PIN and read(WRAP)['status'] == 'PASS_expected_contracts', 'actual accelerated-wrap PASS')
    parent = read(PARENT / 'project/manifest.json')
    need(len(full['files']) == len(small['files']) == 55 and full['geometry'] == parent['geometry'], 'source55 and accepted calendar exact')
    controls = {}
    for name, pin in parent['control_sha256'].items():
        raw = (PARENT / 'project' / name).read_bytes()
        need(sha(raw) == pin, 'frozen parent control ' + name)
        controls[name] = raw
    qsf = '\n'.join(line for line in controls['probe.qsf'].decode().splitlines()
                    if not line.startswith('set_global_assignment -name SYSTEMVERILOG_FILE ')) + '\n'
    qsf = qsf.replace(parent['top'], full['top'])
    qsf += 'set_parameter -name COLD_SECOND_ONESHOT 1\n'
    qsf += ''.join('set_global_assignment -name SYSTEMVERILOG_FILE rtl/' + name + '\n' for name in full['files'])
    controls['probe.qsf'] = qsf.encode()
    manifest = copy.deepcopy(parent)
    manifest.update(status='prepared_R6_oneshot_own_normal_and_wrap_PASS', top=full['top'], core_parameters=params,
        source_sha256=full['generated_sha256'], generator_source_sha256=full['source_sha256'],
        control_sha256={name: sha(raw) for name, raw in controls.items()},
        native_normal_id=GATE, native_role_manifest_sha256=sha((ROLE / 'manifest.json').read_bytes()),
        context_storage_combo_oneshot=full['context_storage_combo_oneshot'],
        notes=['R6 fixes repeated low32-cycle second-cold proposal using accepted sent/pending state. Exact R5 downstream54 files.',
               'Own quick normal and accelerated AW8 wrap machine PASS required. Full-wrap/long/own clock still promotion gates.',
               '16ns Balanced/seed1/Azure4/32GiB full4h. No old-source numerical, sample projection or clock inheritance.'])
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
    transfer = next(t for t in spec['transfers'] if t['id'] == 'source_to_warm')
    transfer['signals'] += ['cold_second_correction', 'child_correction_accept', 'second_correction_sent', 'second_correction_pending']
    transfer['exception']['reason'] += ' R6 cold-only transaction persists until actual child acceptance, then sent suppresses low32-cycle aliases. Reset/newjob clear sent/pending; warm recurrence and accepted legal-edge calendar unchanged. No old-source wrap correctness inherited.'
    for text in (candidate.PROPOSAL_AFTER, candidate.UPDATE_AFTER, candidate.RESET_AFTER, candidate.NEWJOB_AFTER):
        transfer['exception']['contract_anchors'].append(dict(source=new, text=text))
    proof = dict(schema='fit-provisional-aw8-geometry-v1', generator=dict(path=str(GENERATOR), sha256=PIN),
                 kwargs=dict(p=16, contexts=2, enabled=1), native_n=256, fit_n=65536)
    requires = [dict(path=str(WRAP), sha256=WRAP_PIN, fields=dict(status='PASS_expected_contracts'))]
    files = {'rtl/' + name: text.encode() for name, text in full['files'].items()}
    files.update(controls)
    return manifest, files, spec, proof, requires


def prepare(output):
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists(), 'fresh R6 physical output')
    manifest, files, spec, proof, requires = build()
    for name, raw in files.items():
        path = out / 'project' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    (out / 'project/manifest.json').write_bytes(encoded(manifest))
    loader = importlib.util.spec_from_file_location('r6_structure', ROOT / 'tools/prefit_structural_guard_v1.py')
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
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))
