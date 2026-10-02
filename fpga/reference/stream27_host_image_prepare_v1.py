"""Prepare immutable paired idle-T5b host jobs; global dispatcher alone launches."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from fpga.reference import stream27_host_image_native_v1 as native
from fpga.tools import native_class_package_v2 as package
from fpga.tools import native_class_v1 as executor

ROOT = native.ROOT
SELF = 'reference/stream27_host_image_prepare_v1.py'
NATIVE = 'reference/stream27_host_image_native_v1.py'
REPLAY = 'reference/stream27_host_image_replay_v1.py'
TESTS = ('tests/test_stream27_host_image_model_v1.py',
         'tests/test_stream27_host_image_prepare_v1.py',
         'tests/test_stream27_host_image_replay_v1.py')
PACKAGE_SHA = '03b6a81aa7d465487da97f854a79e9e43a19c9c637db6178587cfac02476f604'
STAGER = 'tools/native_package_v3.py'
STAGER_SHA = '5ce285d2a880d4b739c02d0daec5a4e15b6ab23b4b570fafed46ebbe5d8239b9'
COMPANION = 'tools/native_package_v2.py'
COMPANION_SHA = '3f2186fa5aac8129ac1ad5a161de39cf221925ee95d5de6364a941b199e7279a'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def role(aw, p):
    native.verify(); native.contracts(aw, p)
    names = (*native.PINS, NATIVE, SELF, REPLAY, *TESTS)
    files = {name: (ROOT/name).read_bytes() for name in names}
    value = dict(schema='native-source-gate-v1', status='prepared_not_executed',
                 source_root='/not-a-dispatch-path/host-image/fpga',
                 output_parent='/not-a-dispatch-path/host-image/output',
                 sources={name: native.sha(raw) for name, raw in files.items()},
                 build=dict(top=native.TOP, sv_sources=[*native.T5B_PINS, native.SV, native.PAIR],
                            cpp_source=native.CPP, parameters=dict(AW=aw, P=p),
                            cflags=['-std=c++17', '-Werror=return-type',
                                    f'-DHOST_IMAGE_AW={aw}', f'-DHOST_IMAGE_P={p}']),
                 probe=dict(argv=['{exe}', '--runtime-probe'],
                            expected_json=dict(context_threads=1, model_threads=1, expected_threads=1)),
                 steps=[],
                 scope='Shadow host-image component paired with actual promoted T5b idle host; start=0. No whole arithmetic, warm runtime, physical or promotion claim.',
                 host_image=dict(geometry=native.model.geometry(aw, p),
                                 counts=native.model.native_counts(aw, p), source_pins=native.PINS,
                                 parent_top=native.T5B_TOP, parent_start=0, parent_NTT_LANES=64,
                                 oracle='Independent flat signed32 memory, exact signed96 and same accepted E0 value/valid against actual T5b.',
                                 native_executed=False, full_N_numeric_locally_performed=False))
    for negative in (False, True):
        value['steps'].append(dict(name='host-image-negative-oracle' if negative else 'host-image-normal',
                                  argv=['{exe}'] + (['--negative-oracle'] if negative else []),
                                  expected_returncode=int(negative),
                                  validator=dict(source=NATIVE, function='validate',
                                                 config=dict(aw=aw, p=p, negative=negative), assets={})))
    return value, files


def dump(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2); stream.write('\n')


def prepare(output, aw, p, budget):
    native.model.need(not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE', 'queue/PAUSE')),
                      'HOST_IMAGE_PAUSE')
    for name, pin in (('tools/native_class_package_v2.py', PACKAGE_SHA),
                      (STAGER, STAGER_SHA), (COMPANION, COMPANION_SHA)):
        native.model.need(native.sha((ROOT/name).read_bytes()) == pin,
                          'HOST_IMAGE_SHARED_TOOL_DRIFT ' + name)
    output = Path(output).resolve()
    native.model.need(not output.exists(), 'HOST_IMAGE_FRESH_OUTPUT')
    manifest, files = role(aw, p)
    source = output/'input/source/fpga'; source.mkdir(parents=True)
    for name, raw in files.items():
        path = source/name; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream: stream.write(raw)
    path = output/'input/manifest.json'; dump(path, manifest)
    variants = []
    for pair in ('01', '23'):
        profile = f'gcp-c4d-static{pair}-v1'
        worker = f's4-host-image-aw{aw}-p{p}-{pair}-v1'
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
    first, second = [json.loads((Path(v['packet'])/'manifest.json').read_text()) for v in variants]
    native.model.need(all(first[key] == second[key] for key in ('sources', 'build', 'probe', 'steps')),
                      'HOST_IMAGE_DUAL_IDENTITY')
    result = dict(schema='s4-host-image-dual-v1', status='source_ready_not_dispatched', aw=aw, p=p,
                  variants=variants, source_files=len(first['sources']), source_pins=native.PINS,
                  source_map_sha256=native.sha(canonical(first['sources'])), select_exactly_one=True,
                  promotion_allowed=False, HDL_or_native_executed=False,
                  full_N_numeric_locally_performed=False)
    dump(output/'preparation.json', result)
    identifier = f's4-host-image-aw{aw}-p{p}-q1-v1'
    ticket = dict(schema='gfn16-global-ticket-v1', id=identifier, owner='canonical-native-bench',
                  created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                  priority='P1', kind='sim', needs='verilator',
                  tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
                  resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4), minimum_ram_gib=4,
                  minimum_ram_rationale='Explicit bounded exploratory4GiB allowance for idle paired T5b/shadow N<=256; not measured requirement. Desired8GiB remains. Preserve failure; no automatic numeric retry.',
                  est_minutes=5, promotion_bound=False, packages=variants)
    if aw == 8:
        ticket.update(after=[f's4-host-image-aw5-p{p}-q1-v1'], on='PASS_expected_contracts')
    dump(output/'global-ticket-v1.json', ticket)
    native.verify()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aw', type=int, choices=(5, 8), required=True)
    parser.add_argument('--p', type=int, choices=(8, 16), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--budget', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.aw, args.p, args.budget), indent=2))
