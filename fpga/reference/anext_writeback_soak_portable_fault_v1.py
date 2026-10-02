"""Source-only portable F3 controls; no normal readiness or native-launch gate.

The already pinned portable normal role is copied without changing its validator,
runtime assets, build or numerical donor. Only the two existing fault step
contracts from the original F3 short role replace its one normal step.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from fpga.reference.anext_point_qualification_v1 import closed

ROOT = Path(__file__).resolve().parents[1]
PORTABLE = ('anext-writeback-short-portable-role-v1',
            '37c285b16f276178c8ef27c3bc914e891cc9b36aeaaa3f0b45e7d03d48674e8a')
ORIGINAL = ('anext-writeback-qualification-short-role-v1',
            '89dcc87409ae717564c2880504c0c2760c8fc4b89bf81886dd9903f59dc67037')


def need(ok, why):
    if not ok:
        raise ValueError('portable F3 controls: '+why)


def fault_steps(original, portable):
    need(len(portable['steps']) == 1 and portable['steps'][0]['validator']['config'] == {'negative': 'none'},
         'one unchanged portable normal donor')
    shared = portable['steps'][0]['validator']
    steps = [copy.deepcopy(s) for s in original['steps'] if s['validator']['config']['negative'] != 'none']
    need(len(steps) == 2 and {s['validator']['config']['negative'] for s in steps} == {'boundary', 'loaded-state'},
         'only two original expected failures')
    for step in steps:
        need(step['expected_returncode'] == 1 and step['expected_stderr'].startswith('SOAK_BOUNDARY_MISMATCH'),
             'unchanged typed rc1 failure')
        step['validator']['source'] = shared['source']
        step['validator']['assets'] = copy.deepcopy(shared['assets'])
    return steps


def prepare(output):
    m, files = closed(*PORTABLE)
    original, original_files = closed(*ORIGINAL)
    need(m['build'] == original['build'] and m['probe'] == original['probe'] and
         all(files.get(name) == data for name, data in original_files.items()),
         'unchanged build/probe/original complete closure')
    m['steps'] = fault_steps(original, m)
    output = Path(output).resolve()
    need(not output.exists() and not (ROOT/'docs/briefs/PAUSE').exists(), 'fresh output/no PAUSE')
    for name in ('reference/anext_writeback_soak_portable_fault_v1.py',
                 'tests/test_anext_writeback_soak_portable_fault_v1.py'):
        files[name] = (ROOT/name).read_bytes()
    m['sources'] = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    source = output/'source/fpga'
    source.mkdir(parents=True)
    for name, data in files.items():
        target = source/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (output/'manifest.json').write_text(json.dumps(m, indent=2)+'\n')
    return dict(status='prepared_source_only_not_native',
                manifest_sha256=hashlib.sha256((output/'manifest.json').read_bytes()).hexdigest(),
                unchanged_portable_validator=True, compiled_sv=30,
                inherited_native_outcome=False, promotion_allowed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))
