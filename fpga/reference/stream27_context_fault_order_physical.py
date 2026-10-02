"""Chosen timing-storage58 SOURCE-ORDER-only same-controls SYN comparator.

No generator re-emission or native execution. The standing queue joins all
AW16 RTL hashes to this successor's own full normal before synthesizing it.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from . import stream27_context_fault_order_bind as order

ROOT = order.ROOT
SELF = 'reference/stream27_context_fault_order_physical.py'
ORDER_PIN = 'e5d4864afdb63b3bbaf96a83842dd3d357b3bd3d5e174d8b754e942c93c252e1'
PARENT = ROOT / 'results/throughput-20260929/trackS-c2-timing-storage2-v1/syn-project'
NORMAL = ROOT / 'results/throughput-20260929/trackS-c2-fault-order-v1/full-normal'
NORMAL_ID = 's4-p16-c2-fault-order-full-normal-q1-v1'
PARENT_ID = 's4-p16-c2-timing-storage2-whole-syn-v1'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def build():
    order.need(sha((ROOT/order.SELF).read_bytes()) == ORDER_PIN, 'FROZEN_BINDER')
    parent = json.loads((PARENT/'manifest.json').read_text())
    captured = order.prepare(65536)
    source = order.bind(captured, enabled=1)
    normal = json.loads((NORMAL/'manifest.json').read_text())
    native_bundle = json.loads((NORMAL/'production-bundle.json').read_text())
    order.need(parent['source_sha256'] == captured['generated_sha256'], 'EXACT_PARENT_PROJECT58')
    order.need(native_bundle['files'] == source['files'] and native_bundle['top'] == source['top'], 'EXACT_NEW_FULL_SOURCE')
    order.need(len(source['files']) == 58 and source['geometry']['warm_interval'] == 8460, 'EXACT_FULL58')
    files = {}
    for name, pin in parent['control_sha256'].items():
        raw = (PARENT/name).read_bytes()
        order.need(sha(raw) == pin, 'PARENT_CONTROL:' + name)
        files[name] = raw
    for name, pin in parent['source_sha256'].items():
        order.need(sha((PARENT/'rtl'/name).read_bytes()) == pin, 'PARENT_RTL:' + name)
    for name, text in source['files'].items():
        raw = text.encode()
        order.need(normal['sources'].get('rtl/'+name) == sha(raw), 'OWN_FULL_NORMAL_SOURCE:' + name)
        files['rtl/'+name] = raw
    order.need(parent['allowed_stages'] == ['syn'] and parent['clock_period_ns'] == 10 and
               parent['seed'] == 1 and parent['compile_processors'] == 4, 'SAME_SYN_SETTINGS')
    result = copy.deepcopy(parent)
    result.update(status='prepared_SYN_source_order_comparator', source_sha256=source['generated_sha256'],
        native_normal_id=NORMAL_ID, native_role_manifest_sha256=sha((NORMAL/'manifest.json').read_bytes()),
        fault_source_order=dict(source['fault_source_order'], matched_parent_id=PARENT_ID,
            source_helper_sha256=ORDER_PIN, original_source_preserved=True, controls_byte_identical=True,
            no_old_full_gate_inheritance=True, compare_native_16746_and_fault_elaboration=True,
            warning_removal_is_not_exhaustive_fanin_proof=True))
    order.need(result['top'] == parent['top'] and result['control_sha256'] == parent['control_sha256'], 'IDENTICAL_TOP_AND_CONTROLS')
    return result, files


def prepare(output):
    out = Path(output).resolve()
    order.need(out.is_relative_to(ROOT) and not out.exists(), 'FRESH_SOURCE_PROJECT')
    order.need(not any((ROOT/name).exists() for name in ('queue/PAUSE','docs/briefs/PAUSE')), 'PAUSE')
    manifest, files = build()
    out.mkdir(parents=True)
    for name, raw in files.items():
        path = out/name; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    with (out/'manifest.json').open('x') as stream:
        json.dump(manifest, stream, indent=2); stream.write('\n')
    return dict(project=str(out), sources=58, mode='synthesis_only', native_source_gate=NORMAL_ID,
                matched_parent=PARENT_ID, controls_unchanged=True, wholefit_released=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))
