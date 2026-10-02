"""Closed A10 AW16 whole-core packet; reuse verified vector bytes, no local NTT.

The frozen G4 driver checks every requested digit, host/cache/profile contract
and phase counter natively. Predicted stdout changes only cold-root/NTT fields
of the matched parent logs. Unchanged post-CRT integer doubling is retained.
No dispatch, RTL change, executable reuse or numeric full-N calculation.
"""
import argparse
import json
from pathlib import Path

from fpga.reference import a10_native_batch_prepare_v1 as batch
from fpga.reference import a10_whole_geometry_gates_v1 as whole

ROOT = batch.ROOT
SELF = 'reference/a10_whole_native_prepare_v1.py'
TEST = 'tests/test_a10_whole_native_prepare_v1.py'
WHOLE_MANIFEST = '13f66b0d106973556fe4f2a05ec4a8eeabd2692d2d75cd8d0cd7f15f92ac29d2'
ENGINE_MANIFEST = '8ae22eab8a141018abffde047f36827f2f28cb691d9872a5cea9463ccf64bc5f'
BENCH_SHA = '8c991f216ab86537826c18be79fe92539740871b7f5742b13a15d695d09ac283'
LOG_PINS = ('bf4bb63ae7d016d2c7ece361f227e02ba4356854f4e71812401df1c5d1fa333c',
            '30844f8d70c72d134ac35d380ecdfdb407dbd80c0b28ca3fcd52b86a42040902')


def prediction(parent_log, metadata):
    """Exact counter prediction, not a measured A10 result or vector oracle."""
    lines = parent_log.splitlines()
    batch.need(len(lines) == metadata['operations'] + 1, 'A10_WHOLE_PARENT_LOG_EXTENT')
    output = []
    for line, run in zip(lines[:-1], metadata['runs']):
        label, *words = line.split()
        values = {k: int(v) for k, v in (w.split('=') for w in words)}
        cold = not run['profile_before']
        batch.need(label == run['label'] and values['base'] == run['base'] and
            values['profile_before'] == run['profile_before'] and values['readback'] == run['readback'],
            'A10_WHOLE_PARENT_CASE_ORDER')
        batch.need(values['conversion'] == 4102 and values['ntt'] == 20558 and
            values['crt'] == 4113 and values['carry'] == 4147 and values['passes'] == 2 and
            values['roots'] == (8743 if cold else 0) and values['profile_words'] == (8738 if cold else 0)
            and values['seed_setup'] == 815 and values['profile_loads'] == int(cold) and
            values['profile_hits'] == int(not cold) and
            values['cycles'] == sum(values[k] for k in ('conversion','roots','ntt','crt','carry')),
            'A10_WHOLE_MATCHED_PARENT_COUNTERS')
        values.update(roots=9 if cold else 0, ntt=17709, profile_words=4 if cold else 0, seed_setup=0)
        values['cycles'] = sum(values[k] for k in ('conversion','roots','ntt','crt','carry'))
        output.append(label + ' ' + ' '.join(k + '=' + str(v) for k, v in values.items()))
    batch.need(lines[-1] == f"PASS n=65536 squares={metadata['operations']} readbacks={metadata['readbacks']} aborts=0",
               'A10_WHOLE_PARENT_FOOTER')
    return '\n'.join(output + [lines[-1]]) + '\n'


def role():
    whole.source_guard()
    base = ROOT / 'results/throughput-20260929/a10-batch-v1'
    w = base / 'aw5-e2e1/input'; e = base / 'aw16-f0/input'
    batch.need(batch.sha((w / 'manifest.json').read_bytes()) == WHOLE_MANIFEST and
               batch.sha((e / 'manifest.json').read_bytes()) == ENGINE_MANIFEST, 'A10_WHOLE_INPUT_MANIFEST')
    m = json.loads((w / 'manifest.json').read_text()); engine = json.loads((e / 'manifest.json').read_text())
    batch.geometry_prep.closed(w / 'source/fpga', m['sources'])
    batch.geometry_prep.closed(e / 'source/fpga', engine['sources'])
    files = {name: (w / 'source/fpga' / name).read_bytes() for name in m['sources']}
    lookup = 'rtl/kernel/a10_packed_lookup_aw16_lint_bound_v2.sv'
    files[lookup] = (e / 'source/fpga' / lookup).read_bytes()
    for name in (SELF, TEST, whole.BENCH, 'reference/a10_whole_geometry_gates_v1.py',
                 'tests/test_a10_whole_geometry_gates_v1.py'):
        files[name] = (ROOT / name).read_bytes()
    batch.need(batch.sha(files[whole.BENCH]) == BENCH_SHA and
               files[whole.BENCH].decode() == whole.bench_source(), 'A10_WHOLE_DRIVER_EXACT_DELTA')
    m['build']['parameters']['AW'] = 16
    m['build']['cpp_source'] = whole.BENCH
    m['build']['cflags'] = ['-std=c++17', '-Werror=return-type', '-DA10_AW=16']
    m['build']['sv_sources'] = [lookup if x == 'rtl/kernel/a10_packed_lookup_aw5_lint_bound_v2.sv' else x
                                for x in m['build']['sv_sources']]
    m['steps'] = []; segments = []
    for number in (0, 1):
        vector = f'segment{number}.txt'; log = f'test-segment{number}.log'
        files[vector] = (ROOT / whole.VECTORS / vector).read_bytes()
        raw_log = (ROOT / whole.VECTORS / log).read_bytes()
        batch.need(batch.sha(raw_log) == LOG_PINS[number], 'A10_WHOLE_PARENT_NATIVE_LOG')
        metadata = whole.corpus_metadata(files[vector].decode())
        expected = prediction(raw_log.decode(), metadata)
        m['steps'].append(dict(name=f'whole-segment{number}', argv=['{exe}', '{root}/' + vector],
            expected_returncode=0, expected_stdout=expected, expected_stderr=''))
        segments.append(dict(segment=number, vector_sha256=batch.sha(files[vector]),
            parent_native_log_sha256=LOG_PINS[number], expected_stdout_sha256=batch.sha(expected.encode()),
            metadata=metadata))
    files[whole.VECTORS + '/independent-review-v1.json'] = (ROOT / whole.VECTORS / 'independent-review-v1.json').read_bytes()
    m['sources'] = {name: batch.sha(raw) for name, raw in files.items()}
    m['source_root'] = '/not-a-dispatch-path/a10-whole-aw16/fpga'
    m['output_parent'] = '/not-a-dispatch-path/a10-whole-aw16/output'
    m['scope'] = 'A10 canonical whole AW16 twelve-square integration; matched G4 crtmont vectors, not PRP/fit/clock/production'
    m['batch_role'] = dict(id='whole-aw16', dependencies=['aw5-e2e1', 'aw16-f0', 'aw16-f1', 'aw16-f2'],
        segments=segments, source_only_prediction=dict(warm_cycles=30071, cold_cycles=30080,
        warm_delta=-2849, cold_root_delta=-8734), numeric_full_N_locally_performed=False)
    return m, files


def prepare(output, budget):
    batch.need(not (ROOT / 'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    output = Path(output).resolve(); batch.need(not output.exists(), 'A10_WHOLE_FRESH_OUTPUT')
    m, files = role(); source = output / 'input/source/fpga'; source.mkdir(parents=True)
    for name, raw in sorted(files.items()):
        path = source / name; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream: stream.write(raw)
    batch.geometry_prep.closed(source, m['sources'])
    manifest = output / 'input/manifest.json'
    with manifest.open('x') as stream: json.dump(m, stream, indent=2); stream.write('\n')
    variants = []
    for pair in ('01', '23'):
        profile = 'gcp-c4d-static' + pair + '-v1'; worker = 'a10-whole-aw16-batch-' + pair + '-v1'
        packet = output / ('packet-' + pair)
        p = batch.package.prepare(manifest, source, profile, worker, 'run', packet, Path(budget).resolve())
        variants.append(dict(profile=profile, worker_id=worker, packet=str(packet),
            archive=str(packet / 'package.tar.gz'), sha256=p['archive_sha256'],
            ticket_sha256=p['ticket_sha256'], manifest_sha256=batch.sha((packet / 'manifest.json').read_bytes()),
            native_root=p['native_root'], build_key=p['build_key'], archive_bytes=p['archive_bytes'],
            resource_profile_sha256=batch.sha(batch.canonical(batch.executor.profile(profile))),
            runner='tools/native_class_package_v2.py', runner_sha256=batch.PACKAGE_SHA))
    a, b = [json.loads((Path(v['packet']) / 'manifest.json').read_text()) for v in variants]
    batch.need(all(a[k] == b[k] for k in ('sources','build','steps')), 'A10_WHOLE_DUAL_EQUIVALENCE')
    result = dict(schema='a10-finite-role-dual-profile-v1', status='source_ready_not_dispatched',
        role='whole-aw16', dependencies=m['batch_role']['dependencies'], variants=variants,
        source_map_sha256=batch.sha(batch.canonical(a['sources'])),
        build_sha256=batch.sha(batch.canonical(a['build'])), steps_sha256=batch.sha(batch.canonical(a['steps'])),
        source_files=len(a['sources']), source_prediction=m['batch_role'], select_exactly_one=True,
        promotion_allowed=False, full_N_numeric_NTT_locally_performed=False)
    with (output / 'role.json').open('x') as stream: json.dump(result, stream, indent=2); stream.write('\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path); parser.add_argument('--budget', required=True, type=Path)
    args = parser.parse_args(); print(json.dumps(prepare(args.output, args.budget), indent=2))
