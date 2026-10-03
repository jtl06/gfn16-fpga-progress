"""Source-bound raw B endpoint comparison on the worker; no core trimming.

The frozen finalizer is used verbatim. Its full-size host-only guard is adapted
only here to the already-admitted GCP/aethia native validation process. Full-N
arithmetic remains forbidden on the coordinator, even for fixture replay.
"""
import hashlib
import json
from pathlib import Path
import re
import socket
import sys

from fpga.reference import stream27_host_offload_model_v1 as model

MODEL_PIN = 'f9fab4b5a3042046bc90ab2c719a3ae84c1c0504e4a14609b2ddc5b11b6358c5'
KEYS = {'label', 'n', 'p', 'context', 'base', 'owner', 'rows', 'boundaries',
        'words', 'raw', 'actual', 'reference'}


def need(ok, why):
    if not ok:
        raise ValueError('B_ENDPOINT_' + why)


def worker_numeric(n):
    if n > 256:
        need(sys.platform.startswith('linux') and
             socket.gethostname().split('.')[0] in ('aethia', 'gfn16-pilot-c4d'),
             'FULL_FINALIZER_ADMITTED_LINUX_ONLY')


def packet(value, n, mode):
    worker_numeric(n)  # BEFORE decoding or any full-size numeric work.
    need(type(value) is dict and set(value) == KEYS, 'PACKET_KEYS')
    need(all(type(value[k]) is int for k in ('n', 'p', 'context', 'base', 'owner', 'rows', 'boundaries', 'words')),
         'INTEGER_FIELDS')
    need((value['n'], value['p'], value['rows'], value['boundaries'], value['words']) ==
         (n, 16, n // 16, 1, n), 'COMPLETE_ENDPOINT')
    need(value['context'] in (0, 1), 'CONTEXT')
    need(type(value['label']) is str and (value['label'] == 'sentinel' if mode == 'sentinel' else
         value['label'] in ('dense', 'single1', 'single2', 'joint3')), 'RUN_LABEL')
    for name, words in (('raw', n + 32), ('actual', n), ('reference', n)):
        need(type(value[name]) is str and len(value[name]) == words * 8 and
             re.fullmatch('[0-9a-f]+', value[name]), 'WIRE_HEX_' + name)
    need(0 <= value['owner'] < 1 << 56 and value['owner'] & 255 == 1, 'FULL56_OWNER')
    setup = model.profile(n, 16, value['base'], 1)
    raw = bytes.fromhex(value['raw'])
    old = model.worker_numeric
    try:
        model.worker_numeric = worker_numeric
        image = model.decode_final_payload(raw, setup, context=value['context'], owner=value['owner'])
        result = model.finalize(image, expected_context=value['context'], expected_owner=value['owner'])
    finally:
        model.worker_numeric = old
    actual = bytes.fromhex(value['actual'])
    expected = bytes.fromhex(value['reference'])
    finalized = b''.join((word & 0xffffffff).to_bytes(4, 'little') for word in result.digits)
    need(finalized == actual == expected, 'RAW_HOST_DUT_INDEPENDENT_BIT_EQUAL')
    need(result.special is (mode == 'sentinel'), 'SPECIAL_IMAGE_SCOPE')
    if mode == 'sentinel':
        need(result.digits == (-1,) + (0,) * (n - 1), 'SPECIAL_SENTINEL')
    return {'context': value['context'], 'label': value['label'], 'owner': value['owner'],
            'raw_sha256': hashlib.sha256(raw).hexdigest(),
            'canonical_sha256': hashlib.sha256(finalized).hexdigest(), 'special': result.special}


def validate(stdout, stderr, returncode, config, assets):
    need(type(config) is dict and set(config) == {'stage', 'mode'} and
         config['stage'] in ('aw8', 'full') and config['mode'] in ('dense', 'sentinel') and assets == {}, 'CONFIG')
    n = 256 if config['stage'] == 'aw8' else 65536
    worker_numeric(n)
    need(hashlib.sha256(Path(model.__file__).read_bytes()).hexdigest() == MODEL_PIN, 'FROZEN_FINALIZER')
    need(type(stdout) is str and type(stderr) is str and type(returncode) is int and
         returncode == 0 and stderr == '' and stdout.endswith('\n') and len(stdout) < 16 * 1024 * 1024,
         'ACTUAL_OUTPUT')
    lines = stdout.splitlines()
    need(len(lines) >= 3 and all(line.startswith('B_ENDPOINT_PACKET ') for line in lines[:-1]), 'TRANSCRIPT_SHAPE')
    values = [json.loads(line.removeprefix('B_ENDPOINT_PACKET ')) for line in lines[:-1]]
    mode = config['mode']
    expected = ([('sentinel', 0), ('sentinel', 1)] if mode == 'sentinel' else
                [('dense', 0), ('dense', 1)] if n == 256 else
                [('single1', 0), ('single2', 1), ('joint3', 0), ('joint3', 1)])
    need([(v.get('label'), v.get('context')) for v in values] == expected, 'EXACT_PACKETS')
    bases = [1009, 2017] if n == 256 else [604832956, 999999937]
    counts = [1, 1] if mode == 'sentinel' else [3, 14] if n == 256 else [2, 2]
    for value in values:
        c = value['context']
        owner = ((counts[c] - 1) << 24) | ((([65534, 42][c] + counts[c] - 1) & 65535) << 8) | 1
        need(value['base'] == bases[c] and value['owner'] == owner, 'SAME_DUT_FINAL_JOB_PROFILE_OWNER')
    results = [packet(value, n, mode) for value in values]
    if mode == 'sentinel':
        need(lines[-1].startswith('B_ENDPOINT_SENTINEL_PASS '), 'SENTINEL_FOOTER')
        need(json.loads(lines[-1].removeprefix('B_ENDPOINT_SENTINEL_PASS ')) ==
             dict(n=n, p=16, squares=2, reads=2*n, special=True, signed96=True, independent_reference=True),
             'EXACT_SENTINEL_FOOTER')
    elif n == 256:
        need(lines[-1] == 'S4_HOST_CONTEXTS_PASS kind=dense aw=8 p=16 counts=3/14 chains=2 squares=17 reads=1024 peer_live_reads=256 waiting_b=1 capture_during_copy=1 canonical_peer_arithmetic=1 owner_bits=56 signed96=1 canonical_host=1',
             'UNCHANGED_DENSE_FOOTER')
    else:
        from fpga.reference import stream27_p16_two_context_full_native as donor
        donor.validate(lines[-1] + '\n', '', 0, donor.config(), {})
        need(results[0]['canonical_sha256'] == results[2]['canonical_sha256'] and
             results[1]['canonical_sha256'] == results[3]['canonical_sha256'], 'CONTEXT_ALONE_JOINT_IDENTITY')
    return dict(status='PASS_expected_contracts', packets=results, n=n, p=16,
                raw_host_protected_independent_equal=True, exact_frozen_finalizer=True,
                native_trimmed_core=False, full_prp_equivalence=False, transport_measured=False,
                promotion_allowed=False)
