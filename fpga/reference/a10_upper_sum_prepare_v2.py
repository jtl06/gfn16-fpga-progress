"""Prepare three immutable component roles; dispatcher alone launches native."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from fpga.reference import a10_upper_sum_native_v2 as native
from fpga.tools import native_class_package_v2 as package
from fpga.tools import native_class_v1 as executor

ROOT = native.ROOT
SELF = 'reference/a10_upper_sum_prepare_v2.py'
NATIVE = 'reference/a10_upper_sum_native_v2.py'
REPLAY = 'reference/a10_upper_sum_replay_v2.py'
TESTS = ('tests/test_a10_upper_sum_prepare_v2.py', 'tests/test_a10_upper_sum_replay_v2.py')
PACKAGE_SHA = '03b6a81aa7d465487da97f854a79e9e43a19c9c637db6178587cfac02476f604'
STAGER = 'tools/native_package_v3.py'
STAGER_SHA = '5ce285d2a880d4b739c02d0daec5a4e15b6ab23b4b570fafed46ebbe5d8239b9'
COMPANION = 'tools/native_package_v2.py'
COMPANION_SHA = '3f2186fa5aac8129ac1ad5a161de39cf221925ee95d5de6364a941b199e7279a'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def identifier(field):
    native.field_basis(field)
    return f'a10-upper-sum-f{field}-q1-v2'


def role(field):
    native.verify(); p, q = native.field_basis(field)
    names = (*native.PINS, NATIVE, SELF, REPLAY, *TESTS)
    files = {name: (ROOT/name).read_bytes() for name in names}
    value = dict(schema='native-source-gate-v1', status='prepared_not_executed',
                 source_root='/not-a-dispatch-path/a10-upper-sum/fpga',
                 output_parent='/not-a-dispatch-path/a10-upper-sum/output',
                 sources={name: native.sha(raw) for name, raw in files.items()},
                 build=dict(top=native.TOP, sv_sources=list(native.SV_SOURCES), cpp_source=native.CPP,
                            parameters=dict(P=p, Q=q),
                            cflags=['-std=c++17', '-Werror=return-type',
                                    f'-DA10_UPPER_P={p}', f'-DA10_UPPER_FIELD={field}']),
                 probe=dict(argv=['{exe}', '--runtime-probe'],
                            expected_json=dict(context_threads=1, model_threads=1, expected_threads=1)),
                 steps=[],
                 scope='Actual old/new canonical BF component pair. Canonical field inputs only, k+5/II1 unchanged; no engine/full-N/physical/clock/promotion claim.',
                 upper_sum=dict(field=field, modulus=p, montgomery_q=q, counts=native.native_counts(),
                                source_pins=native.PINS,
                                oracle='Independent ordinary64-bit modular multiplication with R^-1; no sparse reduction implementation.',
                                latency=5, ii=1, reset_ages=list(range(7)),
                                native_executed=False, full_N_numeric_locally_performed=False))
    for negative in (False, True):
        value['steps'].append(dict(name='upper-sum-negative-oracle' if negative else 'upper-sum-normal',
                                  argv=['{exe}'] + (['--negative-oracle'] if negative else []),
                                  expected_returncode=int(negative),
                                  validator=dict(source=NATIVE, function='validate',
                                                 config=dict(field=field, negative=negative), assets={})))
    return value, files


def dump(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2); stream.write('\n')


def prepare(output, field, budget):
    native.need(not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE', 'queue/PAUSE')),
                'A10_UPPER_SUM_PAUSE')
    for name, pin in (('tools/native_class_package_v2.py', PACKAGE_SHA),
                      (STAGER, STAGER_SHA), (COMPANION, COMPANION_SHA)):
        native.need(native.sha((ROOT/name).read_bytes()) == pin, 'A10_UPPER_SUM_SHARED_TOOL_DRIFT ' + name)
    output = Path(output).resolve()
    native.need(not output.exists(), 'A10_UPPER_SUM_FRESH_OUTPUT')
    manifest, files = role(field)
    source = output/'input/source/fpga'; source.mkdir(parents=True)
    for name, raw in files.items():
        path = source/name; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream: stream.write(raw)
    path = output/'input/manifest.json'; dump(path, manifest)
    variants = []
    for pair in ('01', '23'):
        profile = f'gcp-c4d-static{pair}-v1'; worker = f'a10-upper-sum-f{field}-{pair}-v2'
        packet = output/('packet-' + pair)
        prepared = package.prepare(path, source, profile, worker, 'run', packet, Path(budget).resolve())
        variants.append(dict(profile=profile, worker_id=worker, packet=str(packet),
                             archive=str(packet/'package.tar.gz'), sha256=prepared['archive_sha256'],
                             ticket_sha256=prepared['ticket_sha256'],
                             manifest_sha256=native.sha((packet/'manifest.json').read_bytes()),
                             native_root=prepared['native_root'], build_key=prepared['build_key'],
                             archive_bytes=prepared['archive_bytes'],
                             resource_profile_sha256=native.sha(canonical(executor.profile(profile))),
                             runner='tools/native_class_package_v2.py', runner_sha256=PACKAGE_SHA,
                             stager=str(ROOT/STAGER), stager_sha256=STAGER_SHA,
                             stager_dependencies=[dict(path=str(ROOT/COMPANION), sha256=COMPANION_SHA)],
                             max_seconds=3700))
    first, second = [json.loads((Path(item['packet'])/'manifest.json').read_text()) for item in variants]
    native.need(all(first[key] == second[key] for key in ('sources', 'build', 'probe', 'steps')),
                'A10_UPPER_SUM_DUAL_IDENTITY')
    result = dict(schema='a10-upper-sum-dual-v2', status='source_ready_not_dispatched', field=field,
                  variants=variants, source_files=len(first['sources']), source_pins=native.PINS,
                  source_map_sha256=native.sha(canonical(first['sources'])), select_exactly_one=True,
                  promotion_allowed=False, HDL_or_native_executed=False,
                  full_N_numeric_locally_performed=False)
    dump(output/'preparation.json', result)
    ticket = dict(schema='gfn16-global-ticket-v1', id=identifier(field), owner='canonical-native-bench',
                  created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                  priority='P1', kind='sim', needs='verilator',
                  tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
                  resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4), minimum_ram_gib=4,
                  minimum_ram_rationale='Explicit bounded exploratory4GiB allowance for tiny standalone actual old/new BF pair; not measured requirement. Desired8GiB remains. Preserve failures; no automatic numeric retry.',
                  est_minutes=2, promotion_bound=False, packages=variants)
    dump(output/'global-ticket-v1.json', ticket); native.verify()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--field', type=int, choices=range(3), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--budget', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.field, args.budget), indent=2))
