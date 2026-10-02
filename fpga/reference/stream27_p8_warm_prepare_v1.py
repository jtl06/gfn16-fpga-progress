"""Source-ready AW8 three-field gates -> exact measured AW16 field0 gate."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from fpga.reference import stream27_p8_warm_native_v1 as native
from fpga.tools import native_class_package_v2 as package
from fpga.tools import native_class_v1 as executor

ROOT = native.ROOT
SELF = 'reference/stream27_p8_warm_prepare_v1.py'
NATIVE = 'reference/stream27_p8_warm_native_v1.py'
REPLAY = 'reference/stream27_p8_warm_replay_v1.py'
TESTS = ('tests/test_stream27_p8_warm_prepare_v1.py', 'tests/test_stream27_p8_warm_replay_v1.py')
PACKAGE_SHA = '03b6a81aa7d465487da97f854a79e9e43a19c9c637db6178587cfac02476f604'
STAGER = 'tools/native_package_v3.py'
STAGER_SHA = '5ce285d2a880d4b739c02d0daec5a4e15b6ab23b4b570fafed46ebbe5d8239b9'
COMPANION = 'tools/native_package_v2.py'
COMPANION_SHA = '3f2186fa5aac8129ac1ad5a161de39cf221925ee95d5de6364a941b199e7279a'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def identifier(aw, field):
    native.role_arguments(aw, field)
    return f's4-p8-aw{aw}-f{field}-warm-q1-v1'


def role(aw, field):
    bundle, measured = native.emitted_bundle(aw, field)
    files = {'rtl/'+name: text.encode() for name, text in bundle['files'].items()}
    cpp, header = native.compile_bench(bundle, field)
    files[native.CPP] = cpp.encode(); files[native.HEADER] = header.encode()
    files[native.REFERENCE] = (ROOT/native.REFERENCE).read_bytes()
    deps = (*bundle['source_dependencies'], native.BENCH, native.BENCH_PARENT)
    for name in dict.fromkeys(deps): files['lineage/'+name] = (ROOT/name).read_bytes()
    for name in (NATIVE, SELF, REPLAY, *TESTS): files[name] = (ROOT/name).read_bytes()
    files['evidence/p8-measured-fit-manifest.json'] = (ROOT/native.FIT_MANIFEST).read_bytes()
    files['evidence/p8-measured-fit-receipt.json'] = (ROOT/native.FIT_RECEIPT).read_bytes()
    value = dict(schema='native-source-gate-v1', status='prepared_not_executed',
                 source_root='/not-a-dispatch-path/p8-warm/fpga',
                 output_parent='/not-a-dispatch-path/p8-warm/output',
                 sources={name: native.sha(raw) for name, raw in files.items()},
                 build=dict(top=bundle['top'], sv_sources=['rtl/'+name for name in bundle['rtl_sources']],
                            cpp_source=native.CPP, parameters=dict(AW=aw, P=8, CONTEXTS=1),
                            cflags=['-std=c++17', '-O2', '-Werror=return-type']),
                 probe=dict(argv=['{exe}', '--runtime-probe'],
                            expected_json=dict(context_threads=1, model_threads=1, expected_threads=1)),
                 steps=[],
                 scope='P8 canonical one-field arithmetic and warm schedule. No three-field CRT/carry, host/PRP, board, clock or promotion claim.',
                 p8_warm=dict(aw=aw, p=8, field=field, counts=native.counts(aw, field),
                              geometry=bundle['geometry'], generated_sha256=bundle['generated_sha256'],
                              source_sha256=bundle['source_sha256'], measured_manifest_sha256=native.PINS[native.FIT_MANIFEST],
                              measured_receipt_sha256=native.PINS[native.FIT_RECEIPT],
                              exact_23_measured_RTL=aw == 16, RTL_wrapper_delta='NONE; actual field top directly instantiated.',
                              harness_delta='Frozen full-native compile_bench; P8/geometry header, role footer and local expected-word negative control only.',
                              oracle='Frozen independent iterative natural-order twist/cyclic-square/untwist; native signed N256 schoolbook self-check.',
                              native_executed=False, full_N_numeric_locally_performed=False))
    for negative in (False, True):
        value['steps'].append(dict(name='p8-warm-negative-oracle' if negative else 'p8-warm-normal',
                                  argv=['{exe}'] + (['--negative-oracle'] if negative else []),
                                  expected_returncode=int(negative),
                                  validator=dict(source=NATIVE, function='validate',
                                                 config=dict(aw=aw, field=field, negative=negative), assets={})))
    return value, files


def dump(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2); stream.write('\n')


def prepare(output, aw, field, budget):
    native.need(not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE', 'queue/PAUSE')), 'P8_WARM_PAUSE')
    for name, pin in (('tools/native_class_package_v2.py', PACKAGE_SHA), (STAGER, STAGER_SHA), (COMPANION, COMPANION_SHA)):
        native.need(native.sha((ROOT/name).read_bytes()) == pin, 'P8_WARM_SHARED_TOOL_DRIFT ' + name)
    output = Path(output).resolve(); native.need(not output.exists(), 'P8_WARM_FRESH_OUTPUT')
    manifest, files = role(aw, field)
    source = output/'input/source/fpga'; source.mkdir(parents=True)
    for name, raw in files.items():
        path = source/name; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream: stream.write(raw)
    path = output/'input/manifest.json'; dump(path, manifest); variants = []
    for pair in ('01', '23'):
        profile = f'gcp-c4d-static{pair}-v1'; worker = f's4-p8-aw{aw}-f{field}-warm-{pair}-v1'
        packet = output/('packet-'+pair)
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
                             stager_dependencies=[dict(path=str(ROOT/COMPANION), sha256=COMPANION_SHA)], max_seconds=3700))
    first, second = [json.loads((Path(item['packet'])/'manifest.json').read_text()) for item in variants]
    native.need(all(first[key] == second[key] for key in ('sources', 'build', 'probe', 'steps')), 'P8_WARM_DUAL_IDENTITY')
    result = dict(schema='s4-p8-warm-dual-v1', status='source_ready_not_dispatched', aw=aw, field=field,
                  variants=variants, source_files=len(first['sources']), source_map_sha256=native.sha(canonical(first['sources'])),
                  generated_sha256=manifest['p8_warm']['generated_sha256'], geometry=manifest['p8_warm']['geometry'],
                  exact_23_measured_RTL=aw == 16, select_exactly_one=True, promotion_allowed=False,
                  HDL_or_native_executed=False, full_N_numeric_locally_performed=False)
    dump(output/'preparation.json', result)
    ticket = dict(schema='gfn16-global-ticket-v1', id=identifier(aw, field), owner='canonical-native-bench',
                  created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                  priority='P1', kind='sim', needs='verilator', tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
                  resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4), minimum_ram_gib=8 if aw == 16 else 4,
                  minimum_ram_rationale='Full-size requires8GiB; AW8 only has explicit exploratory4GiB allowance, desired8GiB retained. Unknown P8 compilation aggregate peak; preserve OOM/failures, no expectation relaxation.',
                  est_minutes=10 if aw == 16 else 3, promotion_bound=False, packages=variants)
    if aw == 16: ticket.update(after=[identifier(8, f) for f in range(3)], on='PASS_expected_contracts')
    dump(output/'global-ticket-v1.json', ticket); native.verify()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aw', type=int, choices=(8, 16), required=True)
    parser.add_argument('--field', type=int, choices=range(3), required=True)
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--budget', type=Path, required=True)
    args = parser.parse_args(); print(json.dumps(prepare(args.output, args.aw, args.field, args.budget), indent=2))
