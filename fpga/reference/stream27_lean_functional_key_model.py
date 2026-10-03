"""R93 scalar lifetime/key model. No RTL transformation or numerical NTT.

Closed, error-free host schedules only. This is NOT fault equivalence. Public
ordinal counters, data, valid state, rows, lease allocation and job drain remain.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/throughput-20260929/trackS-c2-storage2-native-v1'
PINS = {256: 'b46fa68fbdb4b7d7bee8c799919490a3329285538e95e087e4ea4a322a1137c9',
        65536: '7592c3d12f6ecf0ef3e5aa9e9c80a4b4cb0f5c7796e94c179b4f0f9488a77837'}
MAIN_MASK = 0x01000300
TERM_MASK = 0x07000300


def encode(context, epoch, generation=0, bank=0):
    return bank << 25 | context << 24 | (epoch & 65535) << 8 | generation


def key(owner, term=False):
    return owner & (TERM_MASK if term else MAIN_MASK)


def next_key(owner):
    return key((owner & 0x01000000) | ((((owner >> 8) + 1) & 3) << 8))


def capture(n):
    path = BASE / ('aw8-normal' if n == 256 else 'full-normal') / 'production-bundle.json'
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PINS[n]
    bundle = json.loads(raw)
    assert len(bundle['files']) == 53
    for name, text in bundle['files'].items():
        assert hashlib.sha256(text.encode()).hexdigest() == bundle['generated_sha256'][name]
    return bundle


def source_contract(bundle):
    files = bundle['files']
    def one(part):
        found = [v for k, v in files.items() if part in k]
        assert len(found) == 1, part
        return found[0]
    contracts = [
        (one('epoch_protocol_contexts'), [
            "if(!valid[i] && !free_found)begin free_found=1;free_index=BANK_W'(i);end", 'sink_row==ROW_W\'(ROWS-1)',
            "valid[sink_index]<=0;received[sink_index]<=0;ready[sink_index]<=0;",
            'next_epoch[frame_ci]<=frame_epoch+EPOCH_W\'(1);']),
        (one('term_context_param'), [
            'wire bypass=product_slot && product_owner==pointwise_owner && product_row==pointwise_row;',
            'bank_owner[seed_bank]<=seed_owner;context_valid[seed_bank]<=0;',
            'wire update_slot=pointwise_slot && wide_target<(ROW_W+1)\'(ROWS);',
            'if(product_slot && bank_owner[prod_bank]==product_owner)begin',
            'context_row[prod_bank][product_row[1:0]]<=product_row;']),
        (one('host_contexts_aw'), [
            'if((|start_contexts) && !(|busy) && !canonical_owned && !error)begin',
            "next_epoch[canonical_owner]<=job_epoch[canonical_owner]+16'(job_count[canonical_owner]);",
            'published[canonical_owner]<=1;done_q[canonical_owner]<=1;phase[canonical_owner]<=IDLE;canonical_owned<=0;']),
        (one('threefield_carry_aw'), [
            'if(joined && field_row[0]==ROW_W\'(ROWS-1) && !join_bad && !out_error)bank_live[bank]<=0;',
            'crt_double[0]<=bank_double[bank];', 'if(begin_carry)begin carry_epoch<=field_epoch[0];']),
    ]
    for text, anchors in contracts:
        for anchor in anchors:
            assert text.count(anchor) == 1, anchor
    return sum(len(anchors) for _, anchors in contracts)


def analyze(n):
    b = capture(n)
    anchors = source_contract(b)
    g = b['geometry']
    interval, rows, pw = g['warm_interval'], g['rows'], g['pointwise_accept']
    # Include an extra conservative edge beyond carry completion and four
    # beyond the final PW row, although updates stop at row ROWS-5.
    tail = max(g['carry_done'] + 1, pw + rows - 1 + 4, g['last_sink'] + 1)
    assert 4 * interval > tail
    # All16-bit epoch phases, including65535->0; two contexts are disjoint.
    wrap_checks = 0
    for epoch in range(65536):
        for delta in range(1, 5):
            same = key(encode(0, epoch)) == key(encode(0, epoch + delta))
            assert same == (delta == 4)
            assert not same or delta * interval > tail
            wrap_checks += 1
        assert next_key(key(encode(1, epoch, 255))) == key(encode(1, epoch + 1))
        assert key(encode(0, epoch)) != key(encode(1, epoch))
    # E4 address/owner recurrence: issue row r+4 only while it exists. Each
    # consumer either uses initialized rows0..3 or exact same-edge bypass.
    row_checks = 0
    for epoch in (0, 3, 4, 65534, 65535, 65536):
        for context in (0, 1):
            for bank in range(4):
                owner = encode(context, epoch, 255, bank)
                for row in range(rows):
                    if row >= 4:
                        issue = pw + row - 4
                        assert issue + 4 == pw + row
                        for delta in (-1, 0, 1):
                            product_owner = encode(context, epoch + delta, 255, bank)
                            # Adjacent frames can overlap elsewhere; row equality
                            # alone must never turn their products into a bypass.
                            assert (owner == product_owner) == (key(owner, True) == key(product_owner, True))
                    else:
                        assert g['term_seed_first'] + row + 4 <= pw + row
                    row_checks += 1
                for other_bank in range(4):
                    assert (key(owner, True) == key(encode(context, epoch, 0, other_bank), True)) == (bank == other_bank)
    # New seed cannot collide with the preceding frame's last E4 product.
    # Feedback correction offset is carry_done-I; seed0 follows correction70.
    feedback_seed = g['carry_done'] - interval + g['term_seed_first']
    last_product = pw + rows - 1
    seed_margin = interval + feedback_seed - last_product
    assert seed_margin > 0
    # At host job boundary, all contexts have published after final raw rows
    # and canonical/copy drain. Quarantined/error jobs cannot restart without
    # reset. Numeric payload may persist but seed_start clears context_valid.
    job_drain_floor = max(g['last_digit'] + 1, g['carry_done'])
    assert job_drain_floor > g['last_sink'] and job_drain_floor > last_product
    return dict(n=n, interval=interval, key_reuse_edges=4 * interval,
        conservative_last_live_edge=tail, reuse_margin=4 * interval - tail,
        metadata_last_sink=g['last_sink'], term_last_product=last_product,
        next_seed_after_last_product=seed_margin, job_drain_floor=job_drain_floor,
        context_only_overlap_witness=g['last_sink'] >= interval,
        wrap_comparisons=wrap_checks, scalar_row_checks=row_checks,
        exact_source_anchors=anchors, source_bundle_sha256=PINS[n])


def result():
    return dict(status='CONDITIONAL_CLOSED_HOST_MODEL_PASS_NOT_RTL',
        geometries=[analyze(256), analyze(65536)],
        main_mask=hex(MAIN_MASK), term_mask=hex(TERM_MASK),
        conditions=['Keep term/correction lease-bank bits26:25 and context24; low epoch9:8; generation zero only in lean.',
            'Normalize every owner state write/comparison/epoch increment modulo4, not just external ports.',
            'Retain valid/received/ready, lease allocation/retirement, row counters, E4 bypass/cache and seed invalidation.',
            'New jobs require original global idle plus canonical drain; reset flushes all authority. No recovery from sticky error without reset.',
            'Ordinals/counts and host final-publication selection stay full width; key is not a replacement for job sequence arithmetic.'],
        excluded=['Malformed or adversarial traffic', 'Fault equivalence', 'Native qualification', 'Area savings', 'Combined numerical equivalence'])


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    with a.output.open('x') as stream:
        json.dump(result(), stream, indent=2)
        stream.write('\n')
