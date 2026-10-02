"""Small A-next A10 real-RAM interface qualification packets, never dispatch.

Keeps the frozen engine/route unchanged and probes its E0 response with an
actual E1 registered RTL consumer. AW5 first, then AW8 multirow/synchronous
lookup geometry. All arithmetic oracles are native-only and at most N256.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from fpga.reference import a10_native_batch_prepare_v1 as batch
from fpga.reference import anext_a10_block_engine_source_v1 as source

ROOT = source.ROOT
SELF = 'reference/anext_a10_block_probe_prepare_v1.py'
TEST = 'tests/test_anext_a10_block_probe_prepare_v1.py'
TOP = 'genefer_anext_a10_block_probe_v1'
SV = 'rtl/tb/' + TOP + '.sv'
CPP = 'rtl/tb/anext_a10_block_probe_v1.cpp'
PINS = {
    source.TARGET: '2d5f4ce2259b689535aa26dffbd9398512bda2ec588a68f76d83e5da30a17c1f',
    source.ROUTE: source.ROUTE_SHA,
    'reference/anext_a10_block_engine_source_v1.py': '121cc9833f1157f82a9a274d352032cd4d38bf529e0c7528b694352ffcbe881b',
    SV: 'e20289579710c0208acb9bd54e31fa857dd1f9fcc39e256337fdd81fad478fe3',
    CPP: '072e1da2441c7709927e2eabf137e92f02612a6ccdb571391dac6bc61d731689',
}


def source_guard():
    source.verify()
    for name, pin in PINS.items():
        batch.need(batch.sha((ROOT / name).read_bytes()) == pin,
                   'ANEXT_A10_BLOCK_PROBE_SOURCE_DRIFT ' + name)
    return dict(PINS)


def role(aw, field):
    batch.need(type(aw) is int and aw in (5, 8), 'ANEXT_A10_BLOCK_SMALL_ONLY')
    batch.need(type(field) is int and field in (0, 1, 2), 'ANEXT_A10_BLOCK_FIELD')
    source_guard()
    manifest, files = batch.donor()
    m = copy.deepcopy(manifest)
    if aw == 8:
        binding = batch.old.gen.lookup_binding(256, 64)
        normal = '\n'.join(x['source'] for x in binding['compiled']) + '\n' + binding['source']
        lookup_name = 'rtl/kernel/a10_packed_lookup_aw8_lint_bound_v2.sv'
        files[lookup_name] = batch.repair.repair_lookup(normal, 8).encode()
        m['build']['sv_sources'] = [lookup_name if x.endswith('/a10_packed_lookup_aw5_lint_bound_v2.sv') else x
                                    for x in m['build']['sv_sources']]
    for name in (*PINS, SELF, TEST):
        files[name] = (ROOT / name).read_bytes()
    f = batch.old.math.FIELDS[field]
    m['build']['top'] = TOP
    m['build']['sv_sources'] = [source.TARGET if x == batch.repair.ENGINE_V2 else x
        for x in m['build']['sv_sources'] if not x.endswith('/genefer_a10_banked27_host16_engine_v1.sv')]
    m['build']['sv_sources'] += [source.ROUTE, SV]
    m['build']['cpp_source'] = CPP
    m['build']['parameters'] = dict(AW=aw, P=f.p, Q=f.q)
    m['build']['cflags'] = ['-std=c++17', '-Werror=return-type',
        f'-DA10_AW={aw}', f'-DA10_P={f.p}', f'-DA10_G={f.generator}']
    m['steps'] = [dict(name='block-interface-normal', argv=['{exe}'], expected_returncode=0,
        expected_stdout=f'A10_BLOCK_PASS aw={aw} field={f.p} blocks=16 offsets={1 << (aw - 4)} e0_to_e1=1 forward=direct-small\n',
        expected_stderr='')]
    m['sources'] = {name: batch.sha(raw) for name, raw in files.items()}
    m.pop('lint_baseline', None)
    m['source_root'] = '/not-a-dispatch-path/anext-a10-block/fpga'
    m['output_parent'] = '/not-a-dispatch-path/anext-a10-block/output'
    m['scope'] = 'Small real-RAM independent-block/E0→E1 probe; unchanged frozen A10 derivative; not whole-core/fit/promotion.'
    m['block_probe'] = dict(aw=aw, field=field, modulus=f.p, blocks=16, offsets=1 << (aw - 4),
        e0_response_to_e1_consumer_edges=1, parent_arithmetic_report_sha256=batch.PASSED_REPORT,
        source_pins=PINS, native_executed=False, full_N_numeric_NTT_locally_performed=False,
        faults=['independent_offsets', 'same_offset_disjoint_masks', 'overlap_atomic_reject',
            'bad_offsets_atomic_reject', 'masked_noncanonical_reject', 'unmasked_junk_ignored',
            'legacy_scalar_vector_external_conflicts', 'profile_begin_loading_suppression',
            'start_and_pending_read_suppression', 'busy_suppression', 'reset_flush_RAM_retention'],
        source_only_forward_cycles=aw * (((1 << aw) + 127) // 128 + 9))
    batch.need(all(name in files for name in m['build']['sv_sources'] + [CPP]), 'ANEXT_A10_BLOCK_COMPILED_CLOSURE')
    return m, files


def prepare(output, aw, field, budget):
    batch.need(not (ROOT / 'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    output = Path(output).resolve()
    batch.need(not output.exists(), 'ANEXT_A10_BLOCK_FRESH_OUTPUT')
    m, files = role(aw, field)
    source_path = output / 'input/source/fpga'
    source_path.mkdir(parents=True)
    for name, raw in sorted(files.items()):
        path = source_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    batch.geometry_prep.closed(source_path, m['sources'])
    manifest_path = output / 'input/manifest.json'
    with manifest_path.open('x') as stream:
        json.dump(m, stream, indent=2)
        stream.write('\n')
    variants = []
    for pair in ('01', '23'):
        profile = 'gcp-c4d-static' + pair + '-v1'
        worker_id = f'anext-a10-block-aw{aw}-f{field}-{pair}-v1'
        packet = output / ('packet-' + pair)
        prepared = batch.package.prepare(manifest_path, source_path, profile, worker_id, 'run', packet, Path(budget).resolve())
        variants.append(dict(profile=profile, worker_id=worker_id, packet=str(packet),
            archive=str(packet / 'package.tar.gz'), sha256=prepared['archive_sha256'],
            ticket_sha256=prepared['ticket_sha256'], manifest_sha256=batch.sha((packet / 'manifest.json').read_bytes()),
            native_root=prepared['native_root'], build_key=prepared['build_key'], archive_bytes=prepared['archive_bytes'],
            resource_profile_sha256=batch.sha(batch.canonical(batch.executor.profile(profile))),
            runner='tools/native_class_package_v2.py', runner_sha256=batch.PACKAGE_SHA))
    a, b = [json.loads((Path(v['packet']) / 'manifest.json').read_text()) for v in variants]
    batch.need(all(a[k] == b[k] for k in ('sources', 'build', 'probe', 'steps')), 'ANEXT_A10_BLOCK_DUAL_EQUIVALENCE')
    result = dict(schema='anext-a10-block-probe-dual-v1', status='source_ready_not_dispatched',
        aw=aw, field=field, source_files=len(a['sources']), source_pins=PINS,
        source_map_sha256=batch.sha(batch.canonical(a['sources'])), variants=variants,
        select_exactly_one=True, promotion_allowed=False, HDL_or_native_executed=False,
        full_N_numeric_NTT_locally_performed=False,
        required_predecessor='same-field AW5 block-interface actual native PASS' if aw == 8 else None)
    with (output / 'preparation.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    source_guard()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--aw', type=int, choices=(5, 8), required=True)
    parser.add_argument('--field', type=int, choices=(0, 1, 2), required=True)
    parser.add_argument('--budget', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.aw, args.field, args.budget), indent=2))
