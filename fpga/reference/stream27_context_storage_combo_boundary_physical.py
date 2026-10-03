"""R95 boundary-only R2 physical snapshot; no shared RTL transformation."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path

from . import stream27_context_storage_combo_boundary_bind as candidate
from .stream27_context_storage_combo_physical import ROOT, sha, need, read, encoded

PARENT = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-v1/physical-v1'
GENERATOR = ROOT / 'reference/stream27_context_storage_combo_boundary_bind.py'
PIN = '0540d53c0bfce872f6aec87d71e16daa368984a5f3b2df5bd288441754d31bab'


def build(native_role, gate, period):
    need(sha(GENERATOR.read_bytes()) == PIN, 'frozen R2 generator')
    full = candidate.prepare(65536, p=16, contexts=2, enabled=1)
    small = candidate.prepare(256, p=16, contexts=2, enabled=1)
    role = Path(native_role).resolve()
    native = read(role / 'manifest.json')
    need(read(role / 'production-bundle.json')['files'] == small['files'], 'own AW8 production source')
    params = dict(native['build']['parameters'], AW=16)
    need(params == dict(full['parameters'], EPOCH_SEED0=65534, EPOCH_SEED1=42), 'actual AW8 epoch overrides')
    need(len(full['files']) == len(small['files']) == 54, 'R2 production54')
    parent = read(PARENT / 'project/manifest.json')
    controls = {}
    for name, pin in parent['control_sha256'].items():
        raw = (PARENT / 'project' / name).read_bytes()
        need(sha(raw) == pin, 'immutable parent control ' + name)
        controls[name] = raw
    qsf = '\n'.join(line for line in controls['probe.qsf'].decode().splitlines()
                    if not line.startswith('set_global_assignment -name SYSTEMVERILOG_FILE ')) + '\n'
    qsf = qsf.replace(parent['top'], full['top'])
    qsf += 'set_parameter -name BOUNDARY_INPUTREG 1\n'
    qsf += ''.join('set_global_assignment -name SYSTEMVERILOG_FILE rtl/' + name + '\n' for name in full['files'])
    controls['probe.qsf'] = qsf.encode()
    sdc = controls['probe.sdc'].decode()
    need(sdc.count('-period 14.000') == 1, 'original explicit clock')
    controls['probe.sdc'] = sdc.replace('-period 14.000', '-period ' + format(float(period), '.3f')).encode()
    manifest = copy.deepcopy(parent)
    manifest.update(status='prepared_R95_boundary_only_provisional_AW8_full_route',
        top=full['top'], clock_period_ns=float(period), core_parameters=params,
        source_sha256=full['generated_sha256'], generator_source_sha256=full['source_sha256'],
        control_sha256={name: sha(raw) for name, raw in controls.items()},
        native_normal_id=gate, native_role_manifest_sha256=sha((role / 'manifest.json').read_bytes()),
        geometry=full['geometry'], context_storage_combo_boundary=full['context_storage_combo_boundary'],
        notes=['R95 exact combo9d34 plus ONLY coherent full27 boundary input register; no fault-edge delay or seven-flag mixing.',
               'Small counted frontend+1/I213/cache78; full I8459/first8458/carry12557 unchanged/cache78.',
               'Provisional own AW8 numerical source gate; full/fault/long ladder independent, no inherited qualification.',
               'Balanced/seed1; actual AWS12 physical cores/40GiB by dispatch; genuine full4h, no timing exception.'])
    spec = read(PARENT / 'structural-inventory.json')
    rename = {'rtl/' + parent['top'] + '.sv': 'rtl/' + full['top'] + '.sv'}
    for f in range(3):
        rename[f'rtl/genefer_stream27_shared_warm_aw16_p16_f{f}_storage_combo_v1.sv'] = f'rtl/genefer_stream27_shared_warm_aw16_p16_f{f}_storage_combo_boundary_v1.sv'
    def remap(value):
        if isinstance(value, dict):
            return {k: remap(v) for k, v in value.items()}
        if isinstance(value, list):
            return [remap(v) for v in value]
        return rename.get(value, value) if isinstance(value, str) else value
    spec = remap(spec)
    spec['identity'].update(top=manifest['top'], parameters=params, clock_period_ns=float(period))
    spec['sources'] = {'rtl/' + name: pin for name, pin in manifest['source_sha256'].items()}
    spec['settings'] = dict(manifest['control_sha256'], **{'manifest.json': sha(encoded(manifest))})
    boundary = next(t for t in spec['transfers'] if t['id'] == 'carry_boundary_to_fields')
    boundary['exception']['reason'] = ('Original signed carry boundary acceptance remains. Inside each field, coherent signed32/base32/high/full27 owner/valid is registered before the reducer: D4 becomes D5, cache77 becomes78; accepted origin tails survive later quarantine. Full public PW/SINK/carry cadence unchanged; AW8 frontend has explicit+1/I213. No false timing path or delayed sticky-fault authority.')
    for text in ('else slot_q<=in_valid && !quarantine;',
                 'correction_q<=correction; base_q<=base;',
                 'high_q<=boundary_high; owner_q<=payload_in;',
                 '.clk,.rst_n,.in_valid(slot_q),.boundary_high(high_q),'):
        boundary['exception']['contract_anchors'].append(dict(
            source='rtl/genefer_stream27_signed_boundary_inputreg_v1.sv', text=text))
    proof = dict(schema='fit-provisional-aw8-geometry-v1',
        generator=dict(path=str(GENERATOR), sha256=PIN),
        kwargs=dict(p=16, contexts=2, enabled=1), native_n=256, fit_n=65536)
    files = {'rtl/' + name: text.encode() for name, text in full['files'].items()}
    files.update(controls)
    return manifest, files, spec, proof


def prepare(output, native_role, gate, period):
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists(), 'fresh R2 physical namespace')
    manifest, files, spec, proof = build(native_role, gate, period)
    for name, raw in files.items():
        path = out / 'project' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    (out / 'project/manifest.json').write_bytes(encoded(manifest))
    loader = importlib.util.spec_from_file_location('r95_structure', ROOT / 'tools/prefit_structural_guard_v1.py')
    checker = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(checker)
    result = checker.source_inventory(out / 'project', spec)
    need(not result['findings'], 'source structural findings: ' + repr(result['findings']))
    (out / 'structural-inventory.json').write_bytes(encoded(spec))
    (out / 'provisional-geometry.json').write_bytes(encoded(proof))
    return dict(project=str(out / 'project'), source_count=54, crossings=len(spec['transfers']),
        structural_sha256=sha(encoded(spec)), provisional_sha256=sha(encoded(proof)), source_findings=result['findings'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--native-role', type=Path, required=True)
    parser.add_argument('--native-gate', required=True)
    parser.add_argument('--period-ns', type=float, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.native_role, args.native_gate, args.period_ns), indent=2))
