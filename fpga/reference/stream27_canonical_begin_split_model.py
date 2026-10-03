"""Model-only base-payload enable split; no emitted RTL or native/clock claim.

Candidate: move ONLY the existing base_reg<=base payload assignment out of
legal_begin into rst_n && IDLE && !error && begin_canonical. Keep correction
capture, authoritative rejection/priority, FSM, RAM and public controls exact.
Rejected BEGIN can change dead private base storage, never eligibility.
This is not a BEGIN pipeline, config cache, or removal of a fault check.
"""
from itertools import product
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT/'results/throughput-20260929/trackS-c2-storage-combo-faultlocal-native-v1/full-normal/production-bundle.json'
LEAF = 'genefer_stream27_canonical_image_loadlocal_v1.sv'
PIN = 'b8d0806344a737ce019a677f49f325442afecd1c388771bb009d5107dd525a6f'
ACTIVE = ('READ_WORD', 'VALUE_WORD', 'PROCESS_WORD', 'SPECIAL_WRITE')
STATES = ('IDLE',) + ACTIVE + ('FAILED',)


def reject(state, error, load, begin, read, pending, ready, base_ok,
           load_bad, order_ok, correction_bad, image):
    """Literal source priority, represented by its documented error codes."""
    if state != 'IDLE' or error:
        return 0
    if load + begin + read > 1 or (pending and (load or begin)):
        return 1
    if load:
        return 3 if not base_ok else 6 if load_bad else 2 if not order_ok else 0
    if begin:
        return 5 if not ready else 3 if not base_ok else 4 if correction_bad else 0
    return 5 if read and not image else 0


def step(state, error, payload, live_base, rst_n, inputs, speculative):
    load, begin, read, pending, ready, base_ok, load_bad, order_ok, bad, image = inputs
    code = reject(state, error, *inputs)
    legal = bool(rst_n and state == 'IDLE' and not error and not code and begin)
    if not rst_n:
        return ('IDLE', False, 2, False, 0)
    capture = (state == 'IDLE' and not error and begin) if speculative else legal
    if capture:
        payload = live_base
    if code:
        state, error = 'FAILED', True
    elif legal:
        state = 'READ_WORD'
    # All non-BEGIN state updates are shared; arbitrary common transitions
    # are handled by the invariant rather than a counterfeit numeric oracle.
    return state, error, payload, legal, code


def source():
    leaf = json.loads(CAPTURE.read_text())['files'][LEAF]
    assert hashlib.sha256(leaf.encode()).hexdigest() == PIN
    for anchor in (
        'wire legal_begin=rst_n && state==IDLE && !error && !idle_reject && begin_canonical;',
        'base_reg<=base;address<=0;pass_index<=0;carry<=0;',
        'base_reg<=2;address<=0;pass_index<=0;',
        'if(idle_reject)begin',
        'state<=FAILED;error<=1;error_code<=idle_code;',
        "base_ext=$signed({2'b00,base_reg});",
        'stored_digit_bad<=pass_index==0 && ram_q[bank]>=base_reg;',
    ):
        assert leaf.count(anchor) == 1, anchor
    # There are no hidden reads of the candidate-private base storage.
    reads = [line.strip() for line in leaf.splitlines() if 'base_reg' in line]
    assert len(reads) == 5
    return dict(parent_leaf_sha256=PIN, base_register_references=reads,
                proposal='existing base_reg payload enable only; no RTL emitted')


def prove():
    cases = differences = 0
    for state, error, rst_n in product(STATES, (False, True), (False, True)):
        for inputs in product((False, True), repeat=10):
            a = step(state, error, 17, 0xffffffff, rst_n, inputs, False)
            b = step(state, error, 17, 0xffffffff, rst_n, inputs, True)
            assert a[:2] + a[3:] == b[:2] + b[3:]
            if a[2] != b[2]:
                differences += 1
                assert a[0] == b[0] == 'FAILED' and a[1] and b[1]
            if a[0] in ACTIVE:
                assert a[2] == b[2]
            cases += 1
    # Live values are sampled on this accepted edge, never job-start cached.
    accepted = (False, True, False, False, True, True, False, True, False, False)
    live_cases = 0
    for old, live in product((0, 1, 2, 131077, 1000000000, 0xffffffff), repeat=2):
        for owner in (0, 1):
            bases = [old, old]
            bases[owner] = live
            for spec in (False, True):
                out = step('IDLE', False, old, bases[owner], True, accepted, spec)
                assert out[2] == live and out[3]
            live_cases += 1
    # Invariant closes across failure/reset and arbitrary live input changes:
    # active values equal; divergent values occur only in sticky FAILED;
    # reset synchronizes base=2; controls never read base_reg in IDLE/FAILED.
    for live in (0, 1, 0x80000000, 0xffffffff):
        malformed = (True, True, True, True, False, False, True, False, True, False)
        a = step('IDLE', False, 17, live, True, malformed, False)
        b = step('IDLE', False, 17, live, True, malformed, True)
        assert a[4] == b[4] == 1
        a = step(a[0], a[1], a[2], live ^ 7, True, accepted, False)
        b = step(b[0], b[1], b[2], live ^ 7, True, accepted, True)
        assert not a[3] and not b[3] and a[0] == b[0] == 'FAILED'
        assert step(a[0], a[1], a[2], live, False, accepted, False) == \
               step(b[0], b[1], b[2], live, False, accepted, True)
    # Abstract common publication contract, not a new R9 barrier proof.
    publication_cases = 0
    for last_commit, fault_now, sticky, full_owner_match, barrier in product((False, True), repeat=5):
        published = last_commit and not fault_now and not sticky and full_owner_match and barrier
        assert not published or (not fault_now and not sticky and full_owner_match and barrier)
        publication_cases += 1
    return dict(exhaustive_priority_state_cases=cases, rejected_dead_payload_differences=differences,
                live_base_owner_cases=live_cases, common_publication_truth_cases=publication_cases,
                extra_registers=0, extra_edges=0, reset_base=2,
                invariant='base equal whenever state active; divergence only sticky FAILED until reset',
                correction_capture_control_fault_owner_publication_unchanged=True,
                limitation='binary scalar/source model only; no arithmetic/native/R9 barrier proof or timing benefit')


if __name__ == '__main__':
    print(json.dumps(dict(source=source(), model=prove()), indent=2))
