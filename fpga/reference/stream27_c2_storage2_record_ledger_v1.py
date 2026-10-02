"""Source-bound internal-publication ledger for the selected original storage2.

Scalar calendar only: no local full-N arithmetic or hardware-clock claim.
Cold profile/setup and serial canonical/copy costs are included. Initial host
loads, output readback, host gaps and board transport are excluded. The two
jobs retain their own interval; one finalization engine serializes publication.
"""
import hashlib
import json
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/throughput-20260929/trackS-c2-storage2-native-v1/full-normal'
BUNDLE_PIN = '7592c3d12f6ecf0ef3e5aa9e9c80a4b4cb0f5c7796e94c179b4f0f9488a77837'
MANIFEST_PIN = 'c5381b56b03507845e397d94c5bbc840a76e3abd2135ece8b4efecca67534afb'
LOG = ROOT / 'queue/evidence/s4-p16-c2-storage2-full-normal-q1-v1/attempt-0/collected/output/native/normal-full-c2-two-bases-context-alone-and-joint.log'
LOG_PIN = 'c04b89b3e68aae115e197dad711e41b1be1a5c856b6c3163fe8d42ee97a8a9c5'
N, P, ROWS, INTERVAL, CARRY_DONE = 65536, 16, 4096, 8459, 12557
FIRST = (204, 4433)
SAMPLE_OPERATIONS = 1911814


def need(ok, label):
    if not ok:
        raise ValueError('C2_STORAGE_LEDGER_' + label)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source():
    bundle_raw = (BASE / 'production-bundle.json').read_bytes()
    manifest_raw = (BASE / 'manifest.json').read_bytes()
    need(sha(bundle_raw) == BUNDLE_PIN and sha(manifest_raw) == MANIFEST_PIN, 'CAPTURE_PIN')
    bundle, manifest = json.loads(bundle_raw), json.loads(manifest_raw)
    need(len(bundle['files']) == 53 and bundle['storage_contract']['clean_parent'] is True,
         'ORIGINAL_STORAGE53_NOT_TIMING')
    need(all(sha(text.encode()) == bundle['generated_sha256'][name] == manifest['sources']['rtl/' + name]
             for name, text in bundle['files'].items()), 'ALL_PRODUCTION_SOURCE_JOIN')
    g = bundle['geometry']
    need((g['n'], g['p'], g['rows'], g['warm_interval'], g['first_digit'], g['carry_done']) ==
         (N, P, ROWS, INTERVAL, 8458, CARRY_DONE), 'OWN_CALENDAR')
    host = bundle['files'][bundle['top'] + '.sv']
    for anchor in ('CONTEXT_OFFSET=4229,SECOND_CORRECTION=8233;',
                   'else phase[c]<=RAW_READY;',
                   'phase[phase[0]!=RAW_READY]<=CANON_LOAD;',
                   'if(canonical_load && row_address_d==ROW_W\'(ROWS-1))phase[canonical_owner]<=CANON_WAIT;',
                   'context_canonical_cycles[canonical_owner]<=canon_cycles;phase[canonical_owner]<=COPY;',
                   "published[canonical_owner]<=1;done_q[canonical_owner]<=1;phase[canonical_owner]<=IDLE;canonical_owned<=0;"):
        need(host.count(anchor) == 1, 'PUBLICATION_SOURCE_ANCHOR:' + anchor)
    image = bundle['files']['genefer_stream27_canonical_image_pipe_v1.sv']
    need('three edges/digit, 9N normal / 10N special.' in image and
         'READ_WORD:state<=VALUE_WORD;' in image and 'SPECIAL_WRITE:begin' in image,
         'CANONICAL_9N_10N')
    return bundle


def ledger(counts=(2, 2), *, enabled=(True, True), special=(False, False)):
    """Event calendar; positive count includes the cold/leading operation.

    warm_done is observed before the host can set RAW_READY at the next edge.
    The allocator therefore starts at warm+2, or one edge after a previous
    publisher releases the shared scratch. From allocation, ordinary service
    takes ROWS+9N+N+6 edges (load pipeline, canonical, copy and acknowledge).
    A special image adds N only to its own service. No raw image is copied twice.
    """
    need(len(counts) == len(enabled) == len(special) == 2, 'TWO_CONTEXTS')
    need(all(type(c) is int and 1 <= c <= 0xffffffff for c in counts), 'FULL32_COUNTS')
    need(all(type(x) is bool for x in enabled + special) and any(enabled), 'BOOLEAN_MASKS')
    first = FIRST if all(enabled) else tuple(104 if x else None for x in enabled)
    warm = [first[c] + (counts[c] - 1) * INTERVAL + CARRY_DONE + 1 if enabled[c] else None
            for c in range(2)]
    remaining = {c for c in range(2) if enabled[c]}
    allocation, publication, order = [None, None], [None, None], []
    release = -1
    while remaining:
        # Exact C0 priority when both RAW_READY phases are already waiting.
        edge, c = min((max(warm[c] + 2, release + 1), c) for c in remaining)
        allocation[c] = edge
        publication[c] = edge + ROWS + 10 * N + 6 + (N if special[c] else 0)
        release = publication[c]
        order.append(c)
        remaining.remove(c)
    return dict(counts=list(counts), enabled=list(enabled), special=list(special),
        first_edges=list(first), per_context_interval=INTERVAL,
        launch_gaps=[4229, 4230] if all(enabled) else None,
        warm_edges=warm, canonical_allocation_edges=allocation,
        publication_edges=publication, publication_order=order,
        pair_completion_cycles=max(x for x in publication if x is not None),
        external_load_readback_cycles_included=False, hardware_clock_claim=False)


def check_native():
    source()
    raw = LOG.read_bytes()
    need(sha(raw) == LOG_PIN, 'ACTUAL_NATIVE_LOG_PIN')
    need(raw.startswith(b'R84_C2_FULL_PASS ') and raw.endswith(b'\n'), 'NATIVE_FOOTER')
    value = json.loads(raw.removeprefix(b'R84_C2_FULL_PASS '))
    actual = ledger()
    need(value['interval'] == INTERVAL and value['warm_edges'] == actual['warm_edges'] and
         value['done_edges'] == actual['publication_edges'], 'ACTUAL_C2_PUBLICATION_EDGES')
    for c in (0, 1):
        mask = (c == 0, c == 1)
        solo = ledger(enabled=mask)
        need(value['single_first'][c] == solo['first_edges'][c] and
             value['single_cycles'][c] == solo['publication_edges'][c] + N, 'SOLO_AND_READBACK_EDGE')
    need(value['joint_cycles'] == actual['pair_completion_cycles'] + N and
         value['setup_edges'] == [99, 199] and value['signed96'] is True and
         value['context_alone_bit_identical'] is True, 'EXACT_NATIVE_SCOPE')
    return actual


def sample(period_ns=None):
    """Equal-length two-job throughput example, not a measured complete PRP.

    The sample operation count matches the existing N=65536/base604832956
    example. Qualification uses two different bases; this equal-count example
    does not silently replace that corpus or claim complete sample execution.
    """
    value = ledger((SAMPLE_OPERATIONS, SAMPLE_OPERATIONS))
    value.update(sample_n=N, sample_base=604832956,
        operations_including_leading_bit=SAMPLE_OPERATIONS,
        equation='204+(1911814-1)*8459+12558+2*(4096+10*65536)+15',
        scope='Cold equal-length pair through both internal ordinary publications. Includes both profile setups, one canonical/copy per job; excludes external loads/readback/gaps. Own long, routed clock and promotion review required.',
        measured_full_sample_PRP=False, promotion_allowed=False)
    if period_ns is not None:
        period = Decimal(str(period_ns))
        need(period.is_finite() and period > 0, 'CONDITIONAL_POSITIVE_PERIOD')
        pair_seconds = Decimal(value['pair_completion_cycles']) * period / Decimal(10**9)
        value.update(assumed_period_ns=str(period), conditional_pair_seconds=str(pair_seconds),
                     amortized_seconds_per_test=str(pair_seconds / 2), audited_period_used=False)
    return value
