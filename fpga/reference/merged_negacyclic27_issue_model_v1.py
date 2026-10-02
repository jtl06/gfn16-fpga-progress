"""A10 compact-factor roots in the frozen engine's physical bank/lane order.

Model only. Same data address/pair/orientation geometry, separately selected
descending CT / ascending GS. No root-generator, clock, edge or RTL claim.
Numeric banked transforms stay at N<=256 locally; AW16 ledger is geometry only.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path

from fpga.reference import merged_negacyclic27_model as arithmetic

ROOT = Path(__file__).resolve().parents[1]
ENGINE = 'rtl/kernel/genefer_ntt_banked27_prefetch_r2_orient8_rootfused_engine.sv'
ENGINE_SHA = 'd52351bdf53c6809208f7a466848b4376cbd8ff87c52f633dc8c2814026b47ee'
MODEL_SHA = '103c7bbe6917288a92c7432e80d50bc317e6c50eb720a6c604b3a121966adfb4'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def source_guard():
    for name, digest in [(ENGINE, ENGINE_SHA), ('reference/merged_negacyclic27_model.py', MODEL_SHA)]:
        need(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, 'frozen source pin: ' + name)
    text = (ROOT / ENGINE).read_text()
    for source in ['b[j%KW]=b[j%KW]^a[j]',
                   'fixed_position=j!=s && !(j<KW && j!=(s%KW));',
                   "assign orientation=base_bank[pairing];",
                   "assign bf_address=base_addr|((1'(bank>>pairing)^orientation) ? stage_toggle_mask : 32'd0);",
                   '.dif(bf_in_valid[lane] && active_dif)',
                   "assign next_stage=active_dif ? stage_bit-5'd1 : stage_bit+5'd1;"]:
        need(source in text, 'source geometry/orientation contract')
    return dict(engine_sha256=ENGINE_SHA, arithmetic_model_sha256=MODEL_SHA,
                frozen_engine_still_couples_stage_direction_and_arithmetic=True)


def geometry(n, lanes):
    aw = arithmetic.geometry(n)
    need(type(lanes) is int and 1 <= lanes <= 64 and not lanes & (lanes - 1), 'power-of-two lanes1..64')
    kw = lanes.bit_length()
    return aw, kw, min(lanes, n // 2), max(1, n // (2 * lanes))


def bank_of(address, kw):
    bank = 0
    mask = (1 << kw) - 1
    while address:
        bank ^= address & mask
        address >>= kw
    return bank


def logical_address(bank, row, kw):
    high = row << kw
    return high | (bank ^ bank_of(high, kw))


def insert_zero(value, bit):
    return (value & ((1 << bit) - 1)) | ((value >> bit) << (bit + 1))


@dataclass(frozen=True)
class ButterflyIssue:
    stage: int
    issue: int
    lane: int
    u_bank: int
    v_bank: int
    u_row: int
    v_row: int
    u_index: int
    v_index: int
    root_group: int
    exponent: int
    basis_slots: tuple


def issue(n, lanes, stage, number):
    aw, kw, active, groups = geometry(n, lanes)
    need(0 <= stage < aw and 0 <= number < groups, 'stage/issue range')
    pair = stage % kw
    base = 0
    source_bit = 0
    for bit in range(aw):
        fixed = bit != stage and not (bit < kw and bit != pair)
        if fixed:
            base |= ((number >> source_bit) & 1) << bit
            source_bit += 1
    orientation = (bank_of(base, kw) >> pair) & 1
    result = []
    for lane in range(active):
        low = insert_zero(lane, pair)
        high = low | (1 << pair)
        u_bank, v_bank = (high, low) if orientation else (low, high)
        def row(bank):
            address = base | ((((bank >> pair) & 1) ^ orientation) << stage)
            return address >> kw
        u_row, v_row = row(u_bank), row(v_bank)
        u = logical_address(u_bank, u_row, kw)
        v = logical_address(v_bank, v_row, kw)
        need(u < n and v == u + (1 << stage) and not u & (1 << stage), 'physical pair/orientation mismatch')
        root_group = u >> (stage + 1)
        # rev_AW(2^(AW-1-stage)+group) = 2^stage +
        # sum_{j>stage} u[j]*2^(AW+stage-j). Distinct bit slots, no carries.
        slots = (stage,) + tuple(aw + stage - bit for bit in range(stage + 1, aw) if u & (1 << bit))
        exponent = sum(1 << bit for bit in slots)
        result.append(ButterflyIssue(stage, number, lane, u_bank, v_bank, u_row, v_row,
                                     u, v, root_group, exponent, slots))
    need(len({r.u_bank for r in result} | {r.v_bank for r in result}) == 2 * active,
         'one read per active data bank')
    return result


@lru_cache(maxsize=96)
def compact_basis(n, field, inverse=False):
    """AW scalars per direction: psi^(+/-2^t) * R, t=0..AW-1."""
    aw = arithmetic.geometry(n)
    psi = arithmetic.psi_for(n, field)
    sign = -1 if inverse else 1
    return tuple(field.encode(pow(psi, sign * (1 << bit), field.p), 1) for bit in range(aw))


def factored_root(n, field, request, inverse=False, mutant=None):
    basis = compact_basis(n, field, inverse and mutant != 'inverse-forward-root')
    result = basis[request.basis_slots[0]]
    for slot in request.basis_slots[1:]:
        result = field.mont(result, basis[slot])
    if mutant == 'ordinary-root':
        result = field.mont(result, 1)
    if mutant == 'within-group-cyclic-root':
        cyclic_exp = (request.u_index & ((1 << request.stage) - 1)) * (n >> request.stage)
        result = field.encode(pow(arithmetic.psi_for(n, field), cyclic_exp, field.p), 1)
    return result


def root_batch(n, lanes, stage, number, field, inverse=False):
    """Pure accepted-issue descriptor, not a latency/ready/valid implementation."""
    requests = issue(n, lanes, stage, number)
    return dict(tag=[field.p, n, lanes, int(inverse), stage, number],
                mask=[lane < len(requests) for lane in range(lanes)],
                roots=[factored_root(n, field, r, inverse) for r in requests],
                coordinates=[(r.u_bank, r.u_row, r.v_bank, r.v_row) for r in requests])


def check_root_batch(batch, n, lanes, stage, number, field, inverse=False):
    expected = root_batch(n, lanes, stage, number, field, inverse)
    for key in ('tag', 'mask', 'roots', 'coordinates'):
        arithmetic.compare(batch[key], expected[key], 'physical-root-' + key)
    return True


def banked_transform(values, field, *, inverse=False, scale=None, lanes=64, mutant=None):
    n = len(values)
    arithmetic.numeric_geometry(n)
    need(all(type(v) is int and 0 <= v < field.p for v in values), 'canonical vector')
    aw, kw, _, groups = geometry(n, lanes)
    memory = {(bank_of(i, kw), i >> kw): value for i, value in enumerate(values)}
    stages = range(aw) if inverse else range(aw - 1, -1, -1)
    for stage in stages:
        touched = set()
        for number in range(groups):
            requests = issue(n, lanes, stage, number)
            weights = [factored_root(n, field, r, inverse, mutant) for r in requests]
            if mutant == 'lane-root-swap':
                weights.reverse()
            writes = []
            for r, weight in zip(requests, weights):
                need(r.u_index not in touched and r.v_index not in touched, 'one complete visit per stage')
                touched.update((r.u_index, r.v_index))
                u, v = memory[r.u_bank, r.u_row], memory[r.v_bank, r.v_row]
                if inverse:
                    final = scale is not None and stage == aw - 1
                    if final:
                        weight = field.mont(weight, scale)
                    y0 = (u + v) % field.p
                    y0 = field.mont(y0, scale) if final and mutant != 'upper-unscaled' else y0
                    y1 = field.mont((u - v) % field.p, weight)
                else:
                    t = field.mont(v, weight)
                    y0, y1 = (u + t) % field.p, (u - t) % field.p
                writes.extend([((r.u_bank, r.u_row), y0), ((r.v_bank, r.v_row), y1)])
            for address, value in writes:
                memory[address] = value
        need(len(touched) == n, 'complete stage coverage')
    return [memory[bank_of(i, kw), i >> kw] for i in range(n)]


def banked_square(digits, field, *, lanes=64, input_exponent=0, mutant=None):
    values = [field.encode(d, input_exponent) for d in digits]
    spectrum = banked_transform(values, field, lanes=lanes, mutant=mutant)
    squared = [field.mont(v, v) for v in spectrum]
    scale = arithmetic.normalization_constant(len(digits), field, input_exponent)
    return banked_transform(squared, field, inverse=True, scale=scale, lanes=lanes, mutant=mutant)


def ledger(n=65536, lanes=64):
    """Full-N scalar geometry only; no numeric NTT or root vector allocated."""
    aw, kw, active, groups = geometry(n, lanes)
    distinct = [1 << max(0, min(aw, kw) - stage - 1) for stage in range(aw)]
    return dict(n=n, lanes=lanes, stages=aw, issues_per_stage=groups, active_butterflies_per_issue=active,
                butterfly_issues_per_direction=aw * groups,
                distinct_merged_roots_per_issue_by_ascending_stage=distinct,
                distinct_root_deliveries_per_direction=groups * sum(distinct),
                compact_basis_words_all_three_fields_both_directions=2 * aw * 3,
                compact_basis_raw_bits=2 * aw * 3 * 27,
                extra_normalization_scalar_words=3,
                maximum_factor_multiplications_per_root=aw - 1,
                mandatory_final_upper_normalizations_per_field=n // 2,
                stage_direction_and_arithmetic_must_be_separate=True,
                cycle_delta=arithmetic.cycle_work(n) if lanes == 64 else None,
                exclusions=['No one-vector-per-clock root generation proof or storage banking implementation.',
                            'Factor basis is storage algebra, not a free root recurrence; products/contexts/tags have costs.',
                            'No setup/drain/edge, RAM-fit, ALM, clock, full-N numeric or RTL claim.'])
