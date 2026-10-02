"""Normal-first record-base sample on unchanged native-qualified P8 RTL.

The previous base1e9 gates are preserved, not relabeled as604832956. This
emits source/constants only; all full-N arithmetic/HDL executes in the queue.
"""
import argparse
import ast
import json
from pathlib import Path
from fpga.reference import stream27_host_chain_full_native_v1 as parent

ROOT = parent.ROOT
SELF = 'reference/stream27_host_chain_full_matched_v1.py'
TEST = 'tests/test_stream27_host_chain_full_matched_v1.py'
IDENTIFIER = 's4-aw16-p8-record-base-host-q1-v1'
DEPENDENCY = parent.IDENTIFIER
BASE = 604832956


def validate(stdout, stderr, returncode, config, assets):
    parent.need(type(config) is dict and set(config) == {'aw', 'p', 'base', 'mode'}
        and type(config['base']) is int and config['base'] == BASE and config['mode'] == 'normal',
        'S4_RECORD_BASE_CONFIG')
    result = parent.validate(stdout, stderr, returncode,
        {key: config[key] for key in ('aw', 'p', 'mode')}, assets)
    result.update(base=BASE, scope='New matched604832956 two-host-job/nine-operation normal sample; not inherited base1e9 data, full-N PRP,1000-chain or physical clock.')
    return result


def role():
    manifest, files = parent.role()
    old = files[parent.HEADER].decode()
    parent.need(old.count('BASE=1000000000') == 1, 'S4_RECORD_BASE_HEADER')
    files[parent.HEADER] = old.replace('BASE=1000000000', f'BASE={BASE}').encode()
    files[SELF] = (ROOT / SELF).read_bytes()
    files[TEST] = (ROOT / TEST).read_bytes()
    # Do not wait on or add a newly authored fault role to this normal job.
    manifest['steps'] = [manifest['steps'][0]]
    manifest['steps'][0]['validator'].update(source=SELF,
        config=dict(aw=16, p=8, base=BASE, mode='normal'))
    manifest['sources'] = {name: parent.sha(raw) for name, raw in files.items()}
    manifest['full_host'].update(base=BASE,
        dense_input=f'xorshift32 seed0x9135ba27 modulo{BASE}; signed-1 at17/N-1',
        reused_base1e9_numeric_qualification=False,
        scope='New record-base normal sample: legacy1 then dependent mixedfeed8, all131072 signed96 candidate/T5b/reference words; no full-N PRP or1000-chain.')
    return manifest, files


def prepare(output, budget):
    raw = (ROOT / parent.SELF).read_text()
    parent.need(parent.sha(raw.encode()) == '14837cbb854fcabb1ca94d67c769180a67181cfb82b6087ed08ebae1c59ed96a',
        'S4_RECORD_BASE_PARENT')
    node = next(node for node in ast.parse(raw).body if isinstance(node, ast.FunctionDef) and node.name == 'prepare')
    body = ''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    changes = [("'s4-aw16-p8-full-host-'+pair+'-v1'", "'s4-aw16-p8-record-base-'+pair+'-v1'"),
               ("owner='canonical-native-bench'", "owner='stream-core'"),
               ('promotion_bound=False, packages=variants,', "promotion_bound=False, test_role='normal', packages=variants,")]
    for old, new in changes:
        parent.need(body.count(old) == 1, 'S4_RECORD_BASE_FACTORY_ANCHOR')
        body = body.replace(old, new)
    namespace = dict(vars(parent))
    namespace.update(role=role, IDENTIFIER=IDENTIFIER, DEPENDENCY=DEPENDENCY)
    exec(compile(body, '[record-base normal existing packaging]', 'exec'), namespace)
    return namespace['prepare'](output, budget)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--budget', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.output, args.budget)
    print(json.dumps({'status': result['status'], 'id': IDENTIFIER, 'base': BASE,
        'normal_steps': 1, 'variants': len(result['variants'])}, indent=2))
