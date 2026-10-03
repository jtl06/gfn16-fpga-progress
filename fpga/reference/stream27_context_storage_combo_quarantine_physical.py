"""R3 exact separate physical snapshot: R2 plus same-D stop replicas only."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path

from . import stream27_context_storage_combo_quarantine_bind as candidate
from .stream27_context_storage_combo_physical import ROOT, sha, need, read, encoded

PARENT = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-boundary-physical-v1/physical-16000-v1'
GENERATOR = ROOT / 'reference/stream27_context_storage_combo_quarantine_bind.py'
PIN = 'a45413816ed3cccb112a0e0ec6947c20c22e3314e30e6eaed8be260f5ac25a28'


def build(native_role, gate):
    need(sha(GENERATOR.read_bytes()) == PIN, 'frozen R3 generator')
    full = candidate.prepare(65536, p=16, contexts=2, enabled=1)
    small = candidate.prepare(256, p=16, contexts=2, enabled=1)
    role = Path(native_role).resolve()
    native = read(role / 'manifest.json')
    need(read(role / 'production-bundle.json')['files'] == small['files'], 'own AW8 production source')
    params = dict(native['build']['parameters'], AW=16)
    need(params == dict(full['parameters'], EPOCH_SEED0=65534, EPOCH_SEED1=42), 'actual AW8 epoch parameters')
    need(len(full['files']) == len(small['files']) == 55, 'R3 production55')
    parent = read(PARENT / 'project/manifest.json')
    need(full['geometry'] == parent['geometry'], 'every R2 geometry field exact')
    controls = {}
    for name, pin in parent['control_sha256'].items():
        raw = (PARENT / 'project' / name).read_bytes()
        need(sha(raw) == pin, 'immutable R2 control ' + name)
        controls[name] = raw
    qsf = '\n'.join(line for line in controls['probe.qsf'].decode().splitlines()
                    if not line.startswith('set_global_assignment -name SYSTEMVERILOG_FILE ')) + '\n'
    qsf = qsf.replace(parent['top'], full['top'])
    qsf += 'set_parameter -name QUARANTINE_REPLICAS 1\n'
    qsf += ''.join('set_global_assignment -name SYSTEMVERILOG_FILE rtl/' + name + '\n' for name in full['files'])
    controls['probe.qsf'] = qsf.encode()
    manifest = copy.deepcopy(parent)
    manifest.update(status='prepared_R3_same_D_replicas_provisional_AW8_full_route',
        top=full['top'], core_parameters=params,
        source_sha256=full['generated_sha256'], generator_source_sha256=full['source_sha256'],
        control_sha256={name: sha(raw) for name, raw in controls.items()},
        native_normal_id=gate, native_role_manifest_sha256=sha((role / 'manifest.json').read_bytes()),
        context_storage_combo_quarantine=full['context_storage_combo_quarantine'],
        notes=['R3 frozen R2 plus ONLY two same-D CT/GS sticky-stop replicas per field; exact original setter/authority and calendars.',
               'All fault-replica inputs declared before instance. Public fault/pending/full owners/commit barriers unchanged.',
               '16ns Balanced/seed1/Azure4/32GiB full4h, no locality or timing gain claimed.',
               'Own AW8 generator/geometry admission; full/fault/long ladder independent. No parent numerical inheritance.'])
    spec = read(PARENT / 'structural-inventory.json')
    rename = {'rtl/' + parent['top'] + '.sv': 'rtl/' + full['top'] + '.sv'}
    for f in range(3):
        rename[f'rtl/genefer_stream27_shared_warm_aw16_p16_f{f}_storage_combo_boundary_v1.sv'] = f'rtl/genefer_stream27_shared_warm_aw16_p16_f{f}_storage_combo_quarantine_v1.sv'
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
    spec['exclusions'].append(dict(kind='inside_single_macroblock',
        reason='R3 field-local CT/GS stop copies use exact original sticky setter/reset on same edge; public controller_error/pending and origin work unchanged. No new pipeline stage or timing exception.',
        endpoints=['field0/1/2 fault_replicas to forward_transform/inverse_transform quarantine']))
    proof = dict(schema='fit-provisional-aw8-geometry-v1',
        generator=dict(path=str(GENERATOR), sha256=PIN),
        kwargs=dict(p=16, contexts=2, enabled=1), native_n=256, fit_n=65536)
    files = {'rtl/' + name: text.encode() for name, text in full['files'].items()}
    files.update(controls)
    return manifest, files, spec, proof


def prepare(output, native_role, gate):
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists(), 'fresh R3 physical output')
    manifest, files, spec, proof = build(native_role, gate)
    for name, raw in files.items():
        path = out / 'project' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    (out / 'project/manifest.json').write_bytes(encoded(manifest))
    loader = importlib.util.spec_from_file_location('r3_structure', ROOT / 'tools/prefit_structural_guard_v1.py')
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
