"""Strict passed-only performance view; never overwrites raw folded-core evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
from .square_core27_report import BASIS


def normalize(report):
    if report.get('status') != 'passed':
        raise ValueError('only a completed passing gate can be normalized')
    if report.get('radix_bits') != 32 or report.get('crt_modulus') != 487945222748036195811329:
        raise ValueError('wrong atomic27 profile')
    profiles = report.get('profiles')
    if profiles not in ([[16, 16]], [[64, 16]]):
        raise ValueError('expected one supported arithmetic/IO profile')
    lanes = profiles[0][0]
    sources = report.get('sources', {})
    if sources.get('rtl/kernel/genefer_ntt_banked27_folded_engine.sv') != '475a7500e58485c943961729334f8c03e35eb52095657813f8c770d29cb5167c':
        raise ValueError('unverified folded engine')
    ancestor_names = {'rtl/kernel/genefer_square_core27.sv',
                      'rtl/kernel/genefer_ntt_banked27_host_engine.sv',
                      'rtl/tb/square_core27.cpp'}
    ancestor_sources = {name: sha for name, sha in sources.items() if name in ancestor_names}
    sources = {name: sha for name, sha in sources.items() if name not in ancestor_names}
    metrics = []
    for item in report.get('metrics', []):
        if item.get('ntt_lanes') != lanes or item.get('io_lanes') != 16:
            raise ValueError('mixed metric profile')
        aw = item.get('aw')
        if type(aw) is not int or not 1 <= aw <= 16:
            raise ValueError('invalid transform size')
        n = 1 << aw
        for key in ('cycles', 'conversion', 'roots', 'ntt', 'crt', 'carry', 'cache_before', 'root_loads', 'root_hits'):
            if type(item.get(key)) is not int or item[key] < 0:
                raise ValueError('invalid integer counter: ' + key)
        readback = item.get('readback')
        if type(readback) not in (int, bool) or readback not in (0, 1):
            raise ValueError('readback must be bool or integer zero/one')
        if item['cache_before'] not in (0, 15):
            raise ValueError('successful case has partial/invalid cache')
        warm = item['cache_before'] == 15
        if (item['root_loads'], item['root_hits'], item['roots']) != ((0, 4, 0) if warm else (4, 0, 4*(n+2))):
            raise ValueError('cache/cycle coherence mismatch')
        if item['cycles'] != sum(item[key] for key in ('conversion', 'roots', 'ntt', 'crt', 'carry')):
            raise ValueError('phase accounting mismatch')
        if item['conversion'] != (n+15)//16+9:
            raise ValueError('conversion contract changed')
        expected_ntt = 2*aw*((n+2*lanes-1)//(2*lanes)+9) + 3*((n+lanes-1)//lanes+8) + 10
        if item['ntt'] != expected_ntt:
            raise ValueError('folded NTT exact-cycle mismatch')
        metrics.append(dict(item, n=n, root_cache_warm=warm, readback=bool(readback)))
    if not metrics:
        raise ValueError('no completed metrics')
    return dict(status='passed', host=report['host'], ancestor_sha256=report['ancestor_sha256'],
        configuration=dict(difdit=True, ntt_lanes=lanes, prefix_carry=True, root_cache=True,
            banked_ntt=True, carry_lanes=16, vector_io=True, fast_arith=True, io_lanes=16,
            host_adapter=lanes==64, fuse_input_mont=False, stream_carry=False,
            generated_roots=False, ntt_routing='folded-root-v1',
            field_profile='sparse27-cached-folded-radix32-v1', montgomery_radix_bits=32),
        atomic_profile=dict(basis=BASIS, radix_bits=32, crt_modulus=report['crt_modulus'],
            max_doubled_coefficient=report['max_doubled_coefficient'],
            exposed_parameters=['AW', 'NTT_LANES']),
        sources=sources, ancestor_sources=ancestor_sources, metrics=metrics, steps=report['steps'],
        runtime_threads=report['runtime_threads'], compile_workers=2,
        note='Normalized view only. Original report remains immutable; this is not a rerun or a cached correctness result.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if socket.gethostname() != 'aethia':
        raise RuntimeError('aethia only')
    raw = args.input.read_bytes()
    view = normalize(json.loads(raw))
    view['provenance'] = dict(original_report=str(args.input.resolve()),
        original_sha256=hashlib.sha256(raw).hexdigest(),
        normalizer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with args.output.open('x') as handle:
        json.dump(view, handle, indent=2)
        handle.write('\n')
    print(args.output, len(view['metrics']), 'metrics')


if __name__ == '__main__':
    main()
