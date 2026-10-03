"""R4 exact physical snapshot: R3 plus read eligibility factoring only."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path

from . import stream27_context_storage_combo_readlocal_bind as candidate
from .stream27_context_storage_combo_physical import ROOT, sha, need, read, encoded

PARENT = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-quarantine-physical-v1/physical-16000-v1'
ROLE = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-readlocal-native-v1/aw8-normal'
GENERATOR = ROOT / 'reference/stream27_context_storage_combo_readlocal_bind.py'
PIN = '639b05599ba8294e3035ea66298ef216ec2382ca0e506fdb3df910691bd8470d'
GATE = 's4-p16-c2-combo-r4-aw8-normal-q1-v1'


def build():
    need(sha(GENERATOR.read_bytes()) == PIN, 'frozen R4 generator')
    full = candidate.prepare(65536, p=16, contexts=2, enabled=1)
    small = candidate.prepare(256, p=16, contexts=2, enabled=1)
    native = read(ROLE / 'manifest.json')
    need(read(ROLE / 'production-bundle.json')['files'] == small['files'], 'own AW8 production source')
    params = dict(native['build']['parameters'], AW=16)
    need(params == dict(full['parameters'], EPOCH_SEED0=65534, EPOCH_SEED1=42), 'own native parameters')
    parent = read(PARENT / 'project/manifest.json')
    need(len(full['files']) == len(small['files']) == 55, 'exact production55')
    need(full['geometry'] == parent['geometry'], 'R3 geometry unchanged')
    controls = {}
    for name, pin in parent['control_sha256'].items():
        raw = (PARENT / 'project' / name).read_bytes()
        need(sha(raw) == pin, 'frozen parent control ' + name)
        controls[name] = raw
    qsf = '\n'.join(line for line in controls['probe.qsf'].decode().splitlines()
                    if not line.startswith('set_global_assignment -name SYSTEMVERILOG_FILE ')) + '\n'
    qsf = qsf.replace(parent['top'], full['top'])
    qsf += 'set_parameter -name CANONICAL_READ_LOCAL 1\n'
    qsf += ''.join('set_global_assignment -name SYSTEMVERILOG_FILE rtl/' + name + '\n' for name in full['files'])
    controls['probe.qsf'] = qsf.encode()
    manifest = copy.deepcopy(parent)
    manifest.update(status='prepared_R4_readlocal_provisional_AW8_full_route', top=full['top'], core_parameters=params,
        source_sha256=full['generated_sha256'], generator_source_sha256=full['source_sha256'],
        control_sha256={name: sha(raw) for name, raw in controls.items()},
        native_normal_id=GATE, native_role_manifest_sha256=sha((ROLE / 'manifest.json').read_bytes()),
        context_storage_combo_readlocal=full['context_storage_combo_readlocal'],
        notes=['R4 frozen R3 plus ONLY legal-read and pending-response factoring; literal authoritative error/FSM/owner/publication barriers retained.',
               'No FF/latency/calendar change. Own AW8 source/generator proof, full/fault/long ladder independent.',
               '16ns Balanced/seed1/Azure4/32GiB full4h; automatic safe aggregate allocation, no timing or area claim.'])
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
    transfer = next(t for t in spec['transfers'] if t['id'] == 'canonical_read_to_copy')
    transfer['exception']['reason'] += ' R4 factors exclusive legal-read/pending-response enables only; exact read FF, ordered copy/owner checks and edge remain. No added idle-validation cycle or fault-priority change.'
    transfer['exception']['contract_anchors'].append(dict(source='rtl/' + candidate.NEW + '.sv', text=candidate.READ_AFTER))
    proof = dict(schema='fit-provisional-aw8-geometry-v1', generator=dict(path=str(GENERATOR), sha256=PIN),
                 kwargs=dict(p=16, contexts=2, enabled=1), native_n=256, fit_n=65536)
    files = {'rtl/' + name: text.encode() for name, text in full['files'].items()}
    files.update(controls)
    return manifest, files, spec, proof


def prepare(output):
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists(), 'fresh R4 physical output')
    manifest, files, spec, proof = build()
    for name, raw in files.items():
        path = out / 'project' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    (out / 'project/manifest.json').write_bytes(encoded(manifest))
    loader = importlib.util.spec_from_file_location('r4_structure', ROOT / 'tools/prefit_structural_guard_v1.py')
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
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))
