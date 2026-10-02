"""Additive lease-proof correction; retain original failed v1 tickets/packets."""
import argparse
import ast
import json
from pathlib import Path

from fpga.reference import stream27_p8_warm_native_v2 as native
from fpga.reference import stream27_p8_warm_prepare_v1 as parent

ROOT = native.ROOT
SELF = 'reference/stream27_p8_warm_prepare_v2.py'
NATIVE = 'reference/stream27_p8_warm_native_v2.py'
REPLAY = 'reference/stream27_p8_warm_replay_v2.py'
TESTS = ('tests/test_stream27_p8_warm_prepare_v2.py', 'tests/test_stream27_p8_warm_replay_v2.py')
PARENT_SHA = '91215ddaac49a98bbe7f437929859f70b95321ef23efd9303e70c2869d1bbf67'


def identifier(aw, field):
    native.role_arguments(aw, field)
    return f's4-p8-aw{aw}-f{field}-warm-q1-v2'


def role(aw, field):
    native.verify(); manifest, files = parent.role(aw, field)
    bundle, _ = native.parent.emitted_bundle(aw, field); cpp, header = native.compile_bench(bundle, field)
    files[native.CPP] = cpp.encode(); files[native.HEADER] = header.encode()
    for name in (NATIVE, SELF, REPLAY, *TESTS): files[name] = (ROOT/name).read_bytes()
    manifest['sources'] = {name: native.sha(raw) for name, raw in files.items()}
    p = manifest['p8_warm']; p['counts'] = native.counts(aw, field); p['ownership_contract'] = native.ownership_contract(aw, field)
    p['harness_delta'] += ' V2 adds exact per-edge lease count and derived peak, plus wrong-peak typed negative; all v1 numeric/cycle/vectors/fault checks unchanged.'
    p['preserved_failed_ticket'] = parent.identifier(aw, field)
    manifest['steps'] = []
    for mode, flag in (('normal', None), ('oracle', '--negative-oracle'), ('peak', '--negative-peak')):
        manifest['steps'].append(dict(name='p8-warm-'+mode, argv=['{exe}']+([flag] if flag else []),
                                     expected_returncode=int(mode != 'normal'),
                                     validator=dict(source=NATIVE, function='validate',
                                                    config=dict(aw=aw, field=field, mode=mode), assets={})))
    return manifest, files


def prepare(output, aw, field, budget):
    path = ROOT/'reference/stream27_p8_warm_prepare_v1.py'; raw = path.read_text()
    native.need(native.sha(raw.encode()) == PARENT_SHA, 'P8_WARM_FROZEN_PREPARER_V1_DRIFT')
    nodes = [node for node in ast.parse(raw).body if isinstance(node, ast.FunctionDef) and node.name == 'prepare']
    native.need(len(nodes) == 1, 'P8_WARM_PREPARER_FUNCTION')
    node = nodes[0]; body = ''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    for old, new in (("f's4-p8-aw{aw}-f{field}-warm-{pair}-v1'", "f's4-p8-aw{aw}-f{field}-warm-{pair}-v2'"),
                     ("schema='s4-p8-warm-dual-v1'", "schema='s4-p8-warm-dual-v2'")):
        native.need(body.count(old) == 1, 'P8_WARM_PREPARER_DELTA'); body = body.replace(old, new)
    namespace = dict(vars(parent)); namespace.update(native=native, role=role, identifier=identifier)
    exec(compile(body, str(path)+'[independent lease ledger v2]', 'exec'), namespace)
    return namespace['prepare'](output, aw, field, budget)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aw', type=int, choices=(8, 16), required=True)
    parser.add_argument('--field', type=int, choices=range(3), required=True)
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--budget', type=Path, required=True)
    args = parser.parse_args(); print(json.dumps(prepare(args.output, args.aw, args.field, args.budget), indent=2))
