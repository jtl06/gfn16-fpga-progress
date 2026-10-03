"""Source-bound private R7 lean whole fit; host GL assumed (unimplemented).

Copies the existing protected R7 controls and declared-source inventory, then
rebinds exact frozen lean normal RTL. No inherited clock or fault sign-off.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT/'results/throughput-20260929/trackS-c2-storage-combo-faultlocal-physical-v1/physical-16000-v1'
NATIVE = ROOT/'results/throughput-20260929/trackS-c2-lean-r7-native-v2/full-normal'
LABEL = 'lean build; host GL assumed (unimplemented)'
GATE = 's4-p16-c2-lean-r7-full-normal-q1-v2'


def need(ok, why):
    if not ok:
        raise ValueError('C2_LEAN_PHYSICAL_'+why)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2)+'\n').encode()


def read(path):
    return json.loads(Path(path).read_bytes())


def build():
    native = read(NATIVE/'manifest.json')
    full = read(NATIVE/'production-bundle.json')
    need(len(full['files']) == 55 and full['lean_production']['label'] == LABEL,
         'EXACT_OWN_LEAN55')
    parent = read(PARENT/'project/manifest.json')
    need(full['geometry'] == parent['geometry'] and
         full['lean_production']['parent_generated_sha256'] == parent['source_sha256'],
         'EXACT_R7_CONTROL_ANCESTRY')
    params = native['build']['parameters']
    need(params == dict(parent['core_parameters'], LEAN_PRODUCTION=1), 'ONLY_LEAN_PARAMETER')
    need(all(native['sources']['rtl/'+name] == pin == sha(text.encode())
             for name, text in full['files'].items()
             for pin in [full['generated_sha256'][name]]), 'OWN_NORMAL_SOURCE_JOIN')
    controls = {}
    for name, pin in parent['control_sha256'].items():
        raw = (PARENT/'project'/name).read_bytes()
        need(sha(raw) == pin, 'CAPTURED_CONTROL:'+name)
        controls[name] = raw
    qsf = '\n'.join(line for line in controls['probe.qsf'].decode().splitlines()
                    if not line.startswith('set_global_assignment -name SYSTEMVERILOG_FILE '))+'\n'
    qsf = qsf.replace(parent['top'], full['top'])
    qsf += 'set_parameter -name LEAN_PRODUCTION 1\n'
    qsf += ''.join('set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+name+'\n'
                   for name in full['files'])
    controls['probe.qsf'] = qsf.encode()
    sdc = controls['probe.sdc'].decode()
    need(sdc.count('-period 16.000') == 1, 'ONE_DECLARED_CLOCK')
    controls['probe.sdc'] = sdc.replace('-period 16.000', '-period 13.000', 1).encode()
    manifest = {key: copy.deepcopy(parent[key]) for key in (
        'scope', 'edition', 'device', 'compile_processors', 'seed', 'address_width',
        'bitstream_generation', 'allowed_stages', 'raw_multiplier_parameters',
        'field_parameters', 'intermediate_snapshots', 'geometry')}
    manifest.update(status='prepared_lean_healthy_exploration_not_clock', label=LABEL,
        top=full['top'], clock_period_ns=13.0, core_parameters=params,
        source_sha256=full['generated_sha256'], generator_source_sha256=full['source_sha256'],
        control_sha256={name: sha(raw) for name, raw in controls.items()},
        native_normal_id=GATE, native_role_manifest_sha256=sha((NATIVE/'manifest.json').read_bytes()),
        lean_production=full['lean_production'],
        notes=[LABEL, 'Healthy-input numerical equivalence is own-source and not twin fault inheritance.',
               'Functional canonical owner/routing/leases/recurrence/framing/copy and R6 one-shot retained.',
               'Only checking cones specified by private lean contract removed; global watchdog retained.',
               '13ns raw target, seed1, frozen Balanced controls; no promised fit or audited clock.',
               'GL and rollback unimplemented; no protected fault immunity or deployment claim.'])
    spec = read(PARENT/'structural-inventory.json')
    names = {delta['parent'][:-3]: name[:-3]
             for name, delta in full['lean_production']['modified'].items()
             if delta['parent'] != name}

    def remap(value):
        if isinstance(value, dict):
            return {key: remap(item) for key, item in value.items()}
        if isinstance(value, list):
            return [remap(item) for item in value]
        if isinstance(value, str):
            for old, new in names.items():
                value = value.replace(old, new)
            replacements = {
                'wire response_bad=shadow_row_valid && (shadow_response_context!=row_context_d ||':
                    "wire response_bad=1'b0; // Lean: no full56 response verification.",
                'wire capture_bad=final_valid && (phase[final_context]!=RUN ||':
                    "wire capture_bad=1'b0; // Lean: no full56/row capture verification.",
                'assign error=local_error || child_error || canon_error;':
                    'assign error=local_error || lean_watchdog_error;',
                '(capture_req_d && !shadow_capture_ack) || (|child_cancelled))local_error<=1;':
                    'if(ingress_bad || copy_bad || (capture_req_d && !shadow_capture_ack))local_error<=1;',
            }
            return replacements.get(value, value)
        return value

    spec = remap(spec)
    spec['identity'].update(top=full['top'], parameters=params, clock_period_ns=13.0)
    spec['sources'] = {'rtl/'+name: pin for name, pin in full['generated_sha256'].items()}
    spec['settings'] = dict(manifest['control_sha256'], **{'manifest.json': sha(encoded(manifest))})
    for transfer in spec['transfers']:
        if transfer['id'] == 'prospective_fault_to_sticky_origin':
            transfer['exception']['reason'] = ('Lean retains internal origin-edge field sticky authority, '
                'but host only aggregates its retained descriptor/copy framing and global watchdog. '
                'No child/canonical typed protection is claimed; host GL assumed (unimplemented).')
        if transfer['id'] == 'cold_registered_row_to_source':
            transfer['exception']['reason'] = ('Registered RAM/source payload and context route unchanged; '
                'full56 response verification is disabled on trusted inputs. No corruption detection claim.')
    # Replace the old protected comparison explanation, not any timing constraint.
    for item in spec['exclusions']:
        if 'R7 packed-stage full tag mismatch comparisons' in item['reason']:
            item['reason'] = ('Lean removes packed owner mismatch verification; live-generation eligibility, '
                'framing, registers and payload/tag routing retained. No owner fault immunity claimed.')
    spec['exclusions'].append(dict(kind='inside_single_macroblock',
        reason=LABEL+'; canonical range/owner and host typed aggregation checking disabled explicitly. '
               'Arithmetic/canonical folding and functional owner selectors retained. '
               'Declared-source inventory only, not exhaustive netlist/timing or fault proof.',
        endpoints=['host capture/response/boundary compares', 'canonical range checks',
                   'packed owner_bad', 'shadow owner authorization']))
    files = {'rtl/'+name: text.encode() for name, text in full['files'].items()}
    files.update(controls)
    return manifest, files, spec


def prepare(output):
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists(), 'FRESH_OUTPUT')
    manifest, files, spec = build()
    for name, raw in files.items():
        path = out/'project'/name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    with (out/'project/manifest.json').open('xb') as stream:
        stream.write(encoded(manifest))
    loader = importlib.util.spec_from_file_location('lean_structure', ROOT/'tools/prefit_structural_guard_v1.py')
    checker = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(checker)
    result = checker.source_inventory(out/'project', spec)
    need(not result['findings'], 'SOURCE_STRUCTURAL_FINDINGS')
    with (out/'structural-inventory.json').open('xb') as stream:
        stream.write(encoded(spec))
    return dict(project=str(out/'project'), source_count=55, crossings=len(spec['transfers']),
        structural_sha256=sha(encoded(spec)), native_source_gate=GATE, label=LABEL,
        status='PREPARED_NOT_NATIVE_OR_TIMED', source_findings=result['findings'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))
