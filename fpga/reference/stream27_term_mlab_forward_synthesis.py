"""Small source-matched synthesis-only inference probe, not a field/whole fit."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from . import stream27_context_term_mlab_forward_native as native

ROOT = native.ROOT
PARENT = ROOT / 'results/throughput-20260929/trackS-c2-timing-probes-v1/whole-source-v1/project'
NORMAL = ROOT / 'results/throughput-20260929/trackS-c2-term-mlab-forward-v1/unit-normal-v3'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def prepare(output):
    out = Path(output).resolve()
    native.binding.captured.need(out.is_relative_to(ROOT) and not out.exists(), 'FORWARD_SYN_FRESH')
    parent = json.loads((PARENT / 'manifest.json').read_text())
    normal = json.loads((NORMAL / 'manifest.json').read_text())
    filename = native.NEW + '.sv'
    raw = (NORMAL / 'source/fpga/rtl' / filename).read_bytes()
    native.binding.captured.need(normal['sources']['rtl/' + filename] == sha(raw), 'FORWARD_SYN_NATIVE_SOURCE')
    controls = {}
    for name, pin in parent['control_sha256'].items():
        data = (PARENT / name).read_bytes()
        native.binding.captured.need(sha(data) == pin, 'FORWARD_SYN_PARENT_CONTROL')
        controls[name] = data
    qsf = controls['probe.qsf'].decode()
    qsf = native.binding.captured.binder.parent.once(qsf, 'TOP_LEVEL_ENTITY ' + parent['top'], 'TOP_LEVEL_ENTITY ' + native.NEW)
    qsf = re.sub(r'^set_global_assignment -name SYSTEMVERILOG_FILE .*\n', '', qsf, flags=re.M)
    qsf = re.sub(r'^set_parameter .*\n', '', qsf, flags=re.M)
    qsf = re.sub(r'^set_instance_assignment .*\n', '', qsf, flags=re.M)
    qsf += 'set_global_assignment -name SYSTEMVERILOG_FILE rtl/' + filename + '\n'
    controls['probe.qsf'] = qsf.encode()
    native.binding.captured.need(parent['allowed_stages'] == ['syn'] and 'execute_module -tool fit' not in controls['run.tcl'].decode(), 'FORWARD_SYN_ONLY')
    manifest = dict(parent, scope='component_probe', top=native.NEW, core_parameters={}, field_parameters={},
        raw_multiplier_parameters={}, address_width=None,
        geometry=dict(depth=8, word_width=27, read_latency=0), source_sha256={filename: sha(raw)},
        control_sha256={name: sha(data) for name, data in controls.items()},
        native_normal_id=native.NORMAL_ID, native_role_manifest_sha256=sha((NORMAL/'manifest.json').read_bytes()),
        source_experiment='Exact zero-read-latency explicit post-write forwarding; no no_rw_check',
        promotion_allowed=False, notes=['Small one-leaf synthesis inference only; no whole-area/clock claim.'])
    out.mkdir(parents=True)
    for name, data in dict(controls, **{'rtl/' + filename: raw}).items():
        path = out/name; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
    native.binding.captured.dump(out/'manifest.json', manifest)
    return dict(project=str(out), native_normal_id=native.NORMAL_ID, scope='small_SYN_only')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))
