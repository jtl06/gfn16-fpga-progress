"""Frozen canonical-BF old/new pair and exact finite native output contracts."""
from collections import deque
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOP = 'genefer_a10_upper_sum_pair_v2'
OLD = 'rtl/kernel/genefer_a10_canonical_butterfly_v1.sv'
NEW = 'rtl/kernel/genefer_a10_canonical_butterfly_sumlaunch_v2.sv'
LOWER = 'rtl/kernel/genefer_ntt_banked27_engine.sv'
MONT = 'rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv'
PAIR = 'rtl/tb/' + TOP + '.sv'
CPP = 'rtl/tb/a10_upper_sum_pair_v2.cpp'
SV_SOURCES = (MONT, LOWER, OLD, NEW, PAIR)
FIELDS = ((104857601, 4190109697), (69206017, 4225761281), (67239937, 4227727361))
PINS = {
    OLD: 'c05f64749b333bbdedee8e470fb9f468f6123cd7d2f0f3b0c725cbfc41c120fc',
    NEW: '6e6688e37df413b2506c03bd27a3c8eb7962ae45a94d9935150d2175afad6f8b',
    LOWER: '7ae89e702b671e3fbe8a1f90beb99ea595c832729e5e94232bf82515f1d74fe9',
    MONT: '501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b',
    PAIR: 'f96ab94037ae497e781348f938d44446bff6f23f6e03e82e09b4528b2ff5ea90',
    CPP: '1056ba9cbfab5cf56d180bc62475417f1978c26a5b7d2ba58879fce864dfe58a',
}


def need(ok, tag):
    if not ok:
        raise ValueError(tag)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify(root=ROOT):
    for name, pin in PINS.items():
        path = Path(root)/name
        need(path.is_file() and not path.is_symlink() and sha(path.read_bytes()) == pin,
             'A10_UPPER_SUM_SOURCE_DRIFT ' + name)
    return dict(PINS)


def field_basis(field):
    need(type(field) is int and field in range(3), 'A10_UPPER_SUM_FIELD')
    return FIELDS[field]


def native_counts():
    """Independent eligibility/event ledger; no RTL or numerical simulation."""
    counts = dict(cycles=0, accepted=0, outputs=0, ct=0, gs=0, normalized=0,
                  bubbles=0, resets=0, cancelled=0)
    pending = deque()

    def reset():
        counts['cancelled'] += len(pending); pending.clear(); counts['resets'] += 1

    def edge(mode=None, rst=True):
        counts['cycles'] += 1
        if rst and mode is not None:
            counts['accepted'] += 1; pending.append((counts['cycles'] + 5, mode))
        elif rst:
            counts['bubbles'] += 1
        if rst and pending and pending[0][0] == counts['cycles']:
            _, emitted = pending.popleft(); counts['outputs'] += 1
            counts[('ct', 'gs', 'normalized')[emitted]] += 1
        need(not pending or pending[0][0] > counts['cycles'], 'A10_UPPER_SUM_EVENT_LATE')

    def drain():
        for _ in range(6): edge()
        need(not pending, 'A10_UPPER_SUM_EVENT_DRAIN')

    reset(); edge(rst=False); edge()
    for _ in range(7**3):
        for mode in range(3): edge(mode)
    for index in range(2048): edge(index % 3)
    drain()
    for _ in range(64): edge(2)
    drain()
    for index in range(128): edge(index % 3 if index % 5 not in (1, 4) else None)
    drain()
    for _ in range(8): edge(2)
    drain()
    for age in range(7):
        edge(2)
        for _ in range(age): edge()
        reset(); edge(rst=False); drain()
        for mode in range(3): edge(mode)
        drain()
    counts.update(before_checks=2*counts['cycles'], latency=5, ii=1)
    return counts


def contracts(field):
    p, _ = field_basis(field)
    counts = native_counts()
    footer = f'A10_UPPER_SUM_PASS field={field} modulus={p} ' + ' '.join(
        f'{key}={value}' for key, value in counts.items()) + '\n'
    return dict(counts=counts,
                normal=dict(returncode=0, stdout=footer, stderr=''),
                negative=dict(returncode=1, stdout='', stderr='A10_UPPER_SUM_NEGATIVE_ORACLE_REJECT\n'))


def validate(stdout, stderr, returncode, config, assets):
    need(set(config) == {'field', 'negative'} and type(config['negative']) is bool and assets == {},
         'A10_UPPER_SUM_NATIVE_CONFIG')
    expected = contracts(config['field'])['negative' if config['negative'] else 'normal']
    need(type(stdout) is str and type(stderr) is str and type(returncode) is int and
         (stdout, stderr, returncode) == (expected['stdout'], expected['stderr'], expected['returncode']),
         'A10_UPPER_SUM_NATIVE_TYPED_OUTPUT')
    return dict(status='PASS_expected_contracts', field=config['field'], negative=config['negative'],
                promotion_allowed=False,
                scope='Canonical BF old/new/oracle component pair; not engine, full-N, fit or clock qualification.')
