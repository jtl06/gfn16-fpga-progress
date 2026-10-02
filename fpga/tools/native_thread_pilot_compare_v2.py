"""Matched P3 evidence with accounting-only freshness updates kept separate.

Frozen v1 raw-artifact/runtime/measurement replay remains exact. The original
59-member role and every shared runtime/tool/profile file stay identical; only
the closed read-only provider snapshot can differ between admitted starts.
This grants neither spending admission nor higher-thread production admission.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import types

HERE = Path(__file__).resolve().parent
BASE_SHA = 'e9b2f1eb8f1d8c52f17f4356f3c0112597bf373c5740aede9c2f80a66b5f6905'
ROLE = 'results/throughput-20260929/core27-t5b-thread-pilot-source-v1/t5b-cold-warm-threads1-manifest.json'
ROLE_SHA = '42fb4fde0a6ca2cd7b8c2069c353974656b1bb726f841ce19723597ca6c5b1e6'
PROVIDER = re.compile(r'results/throughput-20260929/core27-t5b-thread-pilot-source-v1/execution-inputs-v[1-9][0-9]*/provider\.json')


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def parent():
    path = HERE/'native_thread_pilot_compare_v1.py'
    need(sha(path) == BASE_SHA, 'frozen comparison replay')
    spec = importlib.util.spec_from_file_location('_p3_frozen_compare', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def role_equal(a, b):
    path = HERE.parent/ROLE
    need(sha(path) == ROLE_SHA, 'exact source-only P3 role manifest')
    role = json.loads(path.read_text())['sources']
    need(a.get('budget_source_members') == b.get('budget_source_members') == role,
         'identical exact reviewed 59-member role, not financial data')
    runtime = parent().load('native_threaded_class_v1.py')
    expected = dict(role, **runtime.PINS, **{runtime.SELF: parent().PINS['native_threaded_class_v1.py']})
    for name, pin in expected.items():
        need(a['sources'].get(name) == b['sources'].get(name) == pin, 'unchanged role/runtime/tool/profile source: '+name)
    for manifest in (a, b):
        need(all(name in role for name in manifest['build']['sv_sources']+[manifest['build']['cpp_source']]),
             'all compiled sources in reviewed role')
        need(len([name for name in manifest['sources'] if PROVIDER.fullmatch(name)]) == 1, 'one closed provider snapshot per sample')
    differences = {name for name in set(a['sources'])|set(b['sources']) if a['sources'].get(name) != b['sources'].get(name)}
    need(all(PROVIDER.fullmatch(name) for name in differences), 'source variation only authenticated accounting snapshots')
    return True


def compare(*args):
    base = parent()
    raw = (HERE/'native_thread_pilot_compare_v1.py').read_text()
    old = "a['sources'] == b['sources'] and a['host'] == b['host']"
    need(raw.count(old) == 1, 'unique exact source comparison anchor')
    raw = raw.replace(old, "role_equal(a, b) and a['host'] == b['host']", 1)
    # Execute the exact predecessor text, then restore its pinned sample
    # function so tests and the actual raw-artifact replay use the same API.
    module = types.ModuleType('_p3_accounting_compare')
    module.__file__ = str(HERE/'native_thread_pilot_compare_v1.py')
    exec(compile(raw, str(HERE/'native_thread_pilot_compare_v1.py')+'[accounting-only]', 'exec'), module.__dict__)
    module.role_equal = role_equal
    module.sample = base.sample
    result = module.compare(*args)
    result.update(schema='promoted-t5b-thread-pilot-comparison-v2',
        matched_source_scope='exact59 role members plus all runtime/tool/profile code; only closed accounting snapshot may differ',
        spending_admission_conferred=False)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--one-manifest', type=Path, required=True)
    parser.add_argument('--one-report', type=Path, required=True)
    parser.add_argument('--two-manifest', type=Path, required=True)
    parser.add_argument('--two-report', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.one_manifest, args.one_report, args.two_manifest, args.two_report), indent=2))
