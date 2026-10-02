"""Source-matched private whole SYN-only screen, never whole fit/STA.

Copies the corrected C2 synthesis control snapshot and substitutes only the
already prepared storage2 production53. It does not dispatch a vendor job.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from . import stream27_context_storage_banks_native as native

ROOT = native.ROOT
SELF = 'reference/stream27_context_storage_banks_physical.py'
PARENT = ROOT / 'results/throughput-20260929/trackS-p16-two-context-synthesis-v1/source-explicit-v2/project'
NORMAL = ROOT / 'results/throughput-20260929/trackS-c2-storage2-native-v1/full-normal'
FIELD_PARENT = ROOT / 'results/throughput-20260929/trackS-p16-stage-tagcompact-v1/field-parent-v1/project'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def build():
    parent = json.loads((PARENT / 'manifest.json').read_text())
    source = json.loads((NORMAL / 'production-bundle.json').read_text())
    role = json.loads((NORMAL / 'manifest.json').read_text())
    for name, pin in parent['control_sha256'].items():
        native.need(sha((PARENT / name).read_bytes()) == pin, 'SYN_PARENT_CONTROL:' + name)
    for name, pin in parent['source_sha256'].items():
        native.need(sha((PARENT / 'rtl' / name).read_bytes()) == pin, 'SYN_PARENT_RTL:' + name)
    native.need(source['storage_contract']['clean_parent'] and len(source['files']) == 53, 'SYN_PRIVATE53')
    for name, pin in source['generated_sha256'].items():
        native.need(sha(source['files'][name].encode()) == pin and role['sources']['rtl/' + name] == pin, 'SYN_NATIVE_SOURCE_MATCH:' + name)
    qsf = (PARENT / 'probe.qsf').read_text()
    qsf = native.binder.parent.once(qsf, 'TOP_LEVEL_ENTITY ' + parent['top'], 'TOP_LEVEL_ENTITY ' + source['top'])
    qsf = re.sub(r'^set_global_assignment -name SYSTEMVERILOG_FILE rtl/\S+\n', '', qsf, flags=re.M)
    qsf += ''.join('set_global_assignment -name SYSTEMVERILOG_FILE rtl/' + name + '\n' for name in source['rtl_sources'])
    files = {'rtl/' + name: text.encode() for name, text in source['files'].items()}
    files.update({name: (PARENT / name).read_bytes() for name in ('probe.qpf', 'probe.sdc', 'run.tcl')})
    files['probe.qsf'] = qsf.encode()
    manifest = dict(parent)
    manifest.update(status='prepared_SYN_only', top=source['top'], source_sha256=source['generated_sha256'],
        control_sha256={name: sha(files[name]) for name in ('probe.qsf', 'probe.qpf', 'probe.sdc', 'run.tcl')},
        native_normal_id=native.IDS['full'], native_role_manifest_sha256=sha((NORMAL / 'manifest.json').read_bytes()),
        source_parent_manifest_sha256=sha((PARENT / 'manifest.json').read_bytes()),
        storage2=dict(contract=source['storage_contract'], benchmark_parent='corrected C2 compact OFF',
                      wholefit_released=False, memory_tile_proxy_is_not_placed_count=True))
    native.need(manifest['allowed_stages'] == ['syn'] and files['run.tcl'] == (PARENT / 'run.tcl').read_bytes(), 'SYN_ONLY_NO_FIT_STA')
    return manifest, files


def prepare(output):
    out = Path(output).resolve()
    native.need(out.is_relative_to(ROOT) and not out.exists(), 'SYN_FRESH_OUTPUT')
    manifest, files = build()
    out.mkdir(parents=True)
    for name, data in files.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)
    native.dump(out / 'manifest.json', manifest)
    return dict(project=str(out), source_files=53, status='source_ready_SYN_only_not_submitted',
                waits_for_actual_native_gate=native.IDS['full'], wholefit_released=False)


def build_field():
    """Same corrected-C2 field/QSF controls; no compact-tag ancestry."""
    parent = json.loads((FIELD_PARENT / 'manifest.json').read_text())
    source = json.loads((NORMAL / 'production-bundle.json').read_text())
    _, _, captured = native.capture('full')
    native.need(parent['source_sha256'] == captured['generated_sha256'], 'FIELD_EXACT_CORRECTED_PARENT53')
    for name, pin in parent['control_sha256'].items():
        native.need(sha((FIELD_PARENT / name).read_bytes()) == pin, 'FIELD_PARENT_CONTROL:' + name)
    for name, pin in parent['source_sha256'].items():
        native.need(sha((FIELD_PARENT / 'rtl' / name).read_bytes()) == pin, 'FIELD_PARENT_SOURCE:' + name)
    native.need(parent['scope'] == 'component_probe' and parent['clock_period_ns'] == 10 and
                parent['seed'] == 1 and parent['compile_processors'] == 4, 'FIELD_MATCHED_SETTINGS')
    oldtop = parent['top']
    top = oldtop + '_storage2_v1'
    native.need(top + '.sv' in source['files'], 'FIELD_F0_PRIVATE_TOP')
    qsf = (FIELD_PARENT / 'probe.qsf').read_text()
    qsf = native.binder.parent.once(qsf, 'TOP_LEVEL_ENTITY ' + oldtop, 'TOP_LEVEL_ENTITY ' + top)
    qsf = re.sub(r'^set_global_assignment -name SYSTEMVERILOG_FILE rtl/\S+\n', '', qsf, flags=re.M)
    qsf += ''.join('set_global_assignment -name SYSTEMVERILOG_FILE rtl/' + name + '\n' for name in source['rtl_sources'])
    files = {'rtl/' + name: text.encode() for name, text in source['files'].items()}
    files.update({name: (FIELD_PARENT / name).read_bytes() for name in ('probe.qpf','probe.sdc','run.tcl')})
    files['probe.qsf'] = qsf.encode()
    manifest = dict(parent)
    manifest.update(status='prepared_component_probe', top=top, source_sha256=source['generated_sha256'],
        control_sha256={name: sha(files[name]) for name in ('probe.qsf','probe.qpf','probe.sdc','run.tcl')},
        native_normal_id=native.IDS['full'], native_role_manifest_sha256=sha((NORMAL / 'manifest.json').read_bytes()),
        storage2=dict(matched_parent_id='s4-p16-tagcompact-field-parent-v1', clean_parent=True,
            compact_tags=False, logical_leases=4, physical_banks=2, normal_source_exact=True,
            wholefit_released=False, measured_area_saving=None))
    return manifest, files


def prepare_field(output):
    out = Path(output).resolve()
    native.need(out.is_relative_to(ROOT) and not out.exists(), 'FIELD_FRESH_OUTPUT')
    manifest, files = build_field()
    out.mkdir(parents=True)
    for name, data in files.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:stream.write(data)
    native.dump(out / 'manifest.json', manifest)
    return dict(project=str(out), status='prepared_matched_F0_not_native', wholefit_released=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--field', action='store_true')
    args = parser.parse_args()
    print(json.dumps((prepare_field if args.field else prepare)(args.output), indent=2))
