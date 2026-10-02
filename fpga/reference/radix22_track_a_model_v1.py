"""N1 source-bound radix-2² model; geometry and small-N integers, never RTL.

Data banking is the frozen whole64 XOR fold. Paired issue coordinates are NEW:
keep one varying logical bit for each bank coordinate, replacing the two low
representatives by the actual adjacent transform bits. A spatial two-layer
canonical CT/GS pipeline is modeled, including the merged final GS upper scale.
No full-N numeric transforms, source mutation, HDL or vendor tools are invoked.
"""
from __future__ import annotations

from dataclasses import dataclass
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import re

from fpga.reference import merged_negacyclic27_model as arith
from fpga.reference import merged_negacyclic27_issue_model_v1 as physical
from fpga.reference.stream_ntt_schedule import m20k

ROOT = Path(__file__).resolve().parents[1]
FIT = 'results/throughput-20260929/core27-t5b-provisional64-aws-fit-v1/output_files/probe.fit.rpt'
PINS = {
    physical.ENGINE: physical.ENGINE_SHA,
    'reference/merged_negacyclic27_model.py': physical.MODEL_SHA,
    'reference/merged_negacyclic27_issue_model_v1.py': 'fc3c06df9a8c54ba4fa1899c6a33ea06b72dfbdebb80a391042290c70dd93907',
    'rtl/kernel/genefer_ntt_banked27_engine.sv': '7ae89e702b671e3fbe8a1f90beb99ea595c832729e5e94232bf82515f1d74fe9',
    'rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv': '501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b',
    'rtl/kernel/genefer_a10_canonical_butterfly_v1.sv': 'c05f64749b333bbdedee8e470fb9f468f6123cd7d2f0f3b0c725cbfc41c120fc',
    FIT: '525b53c14f4957e035db59ba022841c1c66a0a6940900c8446cc82b61fb7760b',
}


def need(ok, why):
    if not ok:
        raise ValueError(why)


def source_guard():
    physical.source_guard()
    for name, digest in PINS.items():
        need(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest,
             'source-pin:' + name)
    return dict(PINS)


def geometry(n, lanes=64):
    aw, kw, _, beats = physical.geometry(n, lanes)
    need(lanes >= 2, 'paired geometry needs at least two lanes')
    return aw, kw, beats


def paired_bits(n, lanes, high):
    aw, kw, _ = geometry(n, lanes)
    need(1 <= high < aw, 'adjacent pair range')
    low = high - 1
    chosen = {high % kw: high, low % kw: low}
    need(len(chosen) == 2, 'two independent bank coordinates')
    return tuple(chosen.get(coordinate, coordinate)
                 for coordinate in range(min(aw, kw)))


@dataclass(frozen=True)
class PairedBeat:
    high: int
    number: int
    base: int
    varying: tuple
    quartets: tuple

    @property
    def addresses(self):
        return tuple(a for quartet in self.quartets for a in quartet)


def paired_issue(n, lanes, high, number, *, mutant=None):
    aw, kw, beats = geometry(n, lanes)
    need(0 <= number < beats, 'paired issue range')
    varying = paired_bits(n, lanes, high)
    if mutant == 'keep-low-representative':
        varying = tuple(range(min(aw, kw)))
    fixed = [bit for bit in range(aw) if bit not in varying]
    base = sum(((number >> j) & 1) << bit for j, bit in enumerate(fixed))
    free = [bit for bit in varying if bit not in (high, high - 1)]
    base_bank = physical.bank_of(base, kw)
    quartets = []
    for lane in range(1 << len(free)):
        # Group lanes follow PHYSICAL free-bank coordinates, as in the frozen
        # pair route. Only the two selected coordinate orientation bits route
        # data; XORing other coordinates belongs in the packed-root route.
        anchor = base | sum((((lane >> j) ^ (base_bank >> (bit % kw))) & 1) << bit
                            for j, bit in enumerate(free))
        quartets.append(tuple(anchor | (lo << (high-1)) | (hi << high)
                              for hi in (0, 1) for lo in (0, 1)))
    return PairedBeat(high, number, base, varying, tuple(quartets))


def route_gate(n, lanes, beat):
    """Check seven pattern options + two orientation bits, forward and write."""
    _, kw, _ = geometry(n, lanes)
    high, low = beat.high, beat.high-1
    hp, lp = high % kw, low % kw
    free_coordinates = [r for r in range(min(arith.geometry(n), kw)) if r not in (hp, lp)]
    orientation = physical.bank_of(beat.base, kw) & ((1 << hp) | (1 << lp))
    for lane, q in enumerate(beat.quartets):
        anchor_bank = sum(((lane >> j) & 1) << r for j, r in enumerate(free_coordinates))
        for index, address in enumerate(q):
            bank = anchor_bank ^ orientation ^ ((index >> 1) << hp) ^ ((index & 1) << lp)
            need(bank == physical.bank_of(address, kw), 'read pattern/orientation routing')
            write_index = ((((bank ^ orientation) >> hp) & 1) << 1) | (((bank ^ orientation) >> lp) & 1)
            need(write_index == index, 'inverse write orientation route')
    return True


def root_exponent(n, stage, u_index):
    aw = arith.geometry(n)
    return arith.bit_reverse((n >> (stage+1)) + (u_index >> (stage+1)), aw)


def beat_roots(n, beat):
    high = beat.high
    return (tuple(root_exponent(n, high, q[0]) for q in beat.quartets),
            tuple((root_exponent(n, high-1, q[0]),
                   root_exponent(n, high-1, q[2])) for q in beat.quartets))


def banking_gate(n=65536, lanes=64, high=15):
    """Exhaustive symbolic address/row checks; contains no field operations."""
    aw, kw, beats = geometry(n, lanes)
    visited = bytearray(n)
    first_roots = second_roots = 0
    for number in range(beats):
        beat = paired_issue(n, lanes, high, number)
        route_gate(n, lanes, beat)
        addresses = beat.addresses
        need(len(addresses) == min(n, 2*lanes), 'paired beat width')
        banks = [physical.bank_of(a, kw) for a in addresses]
        need(len(set(banks)) == len(addresses), 'paired bank conflict')
        indices = set(addresses)
        for a, bank in zip(addresses, banks):
            need(0 <= a < n and not visited[a], 'complete unique visitation')
            visited[a] = 1
            need(a ^ (1 << high) in indices and a ^ (1 << (high-1)) in indices,
                 'complete dependency component')
            need(physical.logical_address(bank, a >> kw, kw) == a, 'bank-row inverse')
        roots = beat_roots(n, beat)
        first_roots += len(set(roots[0]))
        second_roots += len({v for pair in roots[1] for v in pair})
    need(all(visited), 'complete frame visit')
    # Prove why carrying the frozen first-stage batch unchanged is insufficient.
    frozen = physical.issue(n, lanes, high, 0)
    frozen_addresses = {a for r in frozen for a in (r.u_index, r.v_index)}
    witness = next((dict(index=a, missing_partner=a ^ (1 << (high-1)))
                    for a in sorted(frozen_addresses)
                    if a ^ (1 << (high-1)) not in frozen_addresses), None)
    return dict(n=n, lanes=lanes, high=high, low=high-1, beats=beats,
                addresses_checked=n, four_point_components=n//4,
                changed_issue_varying_bits=list(paired_bits(n, lanes, high)),
                frozen_single_stage_batch_pair_closed=witness is None,
                frozen_schedule_counterexample=witness,
                distinct_high_root_reads=first_roots, distinct_low_root_reads=second_roots,
                all_data_banks_distinct=True)


def quartet(values, roots, field, *, inverse=False, scale=None, mutant=None):
    """Four canonical residues, bit-exact R=2^32 sparse Montgomery arithmetic.

    Logical order is [00,01,10,11] for bits [high,low]. Forward descending
    CT: high first, then low. Inverse ascending GS: low first, then high.
    The three roots are the high group and the low groups for high=0/1.
    """
    a, b, c, d = values
    wh, w0, w1 = roots
    p = field.p
    if mutant == 'swap-low-roots':
        w0, w1 = w1, w0
    if inverse:
        x0, x1 = (a+b) % p, field.mont((a-b) % p, w0)
        x2, x3 = (c+d) % p, field.mont((c-d) % p, w1)
        upper0, upper1 = (x0+x2) % p, (x1+x3) % p
        if scale is not None:
            wh = field.mont(wh, scale)
            if mutant != 'omit-upper-normalization':
                upper0, upper1 = field.mont(upper0, scale), field.mont(upper1, scale)
        return [upper0, upper1, field.mont((x0-x2) % p, wh),
                field.mont((x1-x3) % p, wh)]
    x0, x2 = (a+field.mont(c, wh)) % p, (a-field.mont(c, wh)) % p
    x1, x3 = (b+field.mont(d, wh)) % p, (b-field.mont(d, wh)) % p
    t0, t1 = field.mont(x1, w0), field.mont(x3, w1)
    return [(x0+t0) % p, (x0-t0) % p, (x2+t1) % p, (x2-t1) % p]


def fused_transform(values, field, *, inverse=False, scale=None, lanes=64, mutant=None):
    n = len(values)
    need(n <= 256, 'N1 local numeric transforms limited to N256')
    aw, kw, beats = geometry(n, lanes)
    need(all(type(v) is int and 0 <= v < field.p for v in values), 'canonical input')
    data = list(values)
    order = list(range(aw) if inverse else range(aw-1, -1, -1))
    psi = arith.psi_for(n, field)
    for position in range(0, aw, 2):
        stages = order[position:position+2]
        if len(stages) == 1:
            stage = stages[0]
            for number in range(beats):
                for r in physical.issue(n, lanes, stage, number):
                    root = field.encode(pow(psi, -r.exponent if inverse else r.exponent, field.p), 1)
                    u, v = data[r.u_index], data[r.v_index]
                    if inverse:
                        final = scale is not None and stage == aw-1
                        weight = field.mont(root, scale) if final else root
                        upper = (u+v) % field.p
                        data[r.u_index] = field.mont(upper, scale) if final and mutant != 'omit-upper-normalization' else upper
                        data[r.v_index] = field.mont((u-v) % field.p, weight)
                    else:
                        t = field.mont(v, root)
                        data[r.u_index], data[r.v_index] = (u+t) % field.p, (u-t) % field.p
            continue
        high = max(stages)
        for number in range(beats):
            beat = paired_issue(n, lanes, high, number)
            high_exp, low_exp = beat_roots(n, beat)
            for indices, eh, el in zip(beat.quartets, high_exp, low_exp):
                exponents = (eh,) + el
                roots = [field.encode(pow(psi, -e if inverse else e, field.p), 1)
                         for e in exponents]
                result = quartet([data[i] for i in indices], roots, field, inverse=inverse,
                                 scale=scale if inverse and high == aw-1 else None, mutant=mutant)
                for index, value in zip(indices, result):
                    data[index] = value
    return data


def fused_square(digits, field, *, lanes=64, mutant=None):
    spectrum = fused_transform([d % field.p for d in digits], field, lanes=lanes, mutant=mutant)
    squared = [field.mont(x, x) for x in spectrum]
    return fused_transform(squared, field, inverse=True,
                           scale=arith.normalization_constant(len(digits), field),
                           lanes=lanes, mutant=mutant)


def packed_root_layout(n=65536, lanes=64):
    """One high/low combined ROM word per paired beat, per direction/pass.

    Store high roots in natural group order then the two low roots per high
    group. A structured XOR of the high-group stream coordinates supplies
    logical quartet lanes. Higher stages broadcast 1 high and 2 low constants.
    Separate pass/direction ROMs avoid any dual-fetch assumption.
    """
    aw, kw, beats = geometry(n, lanes)
    need(aw % 2 == 0, 'packed pair ledger currently even AW only')
    rows = []
    for high in range(1, aw, 2):
        streams = 1 << max(0, min(aw, kw)-high-1)
        depth = 1 << max(0, aw-max(high+1, kw))
        words = 3*streams
        rows.append(dict(high=high, low=high-1, high_streams=streams,
                         low_streams=2*streams, packed_words=words, depth=depth,
                         width=27*words, issue_address_shift=int(math.log2(beats//depth)),
                         M20K_per_direction=m20k(depth, 27*words) if depth > 1 else 0,
                         stream_xor_mux_bits=27*words*(streams.bit_length()-1)))
    return dict(n=n, rows=rows, both_directions_M20K_per_field=2*sum(r['M20K_per_direction'] for r in rows),
                one_direction_raw_table_bits_per_field=sum(r['depth']*r['width'] for r in rows),
                reads_per_beat=1, ROMs_concurrently_active=1,
                distinct_output_roots_per_quartet=3,
                no_numeric_full_N_roots_generated=True)


def packed_root_exponents(n, lanes, high, number):
    """Executable root-address/stream routing, exponents only even at full N."""
    aw, kw, _ = geometry(n, lanes)
    spec = next(r for r in packed_root_layout(n, lanes)['rows'] if r['high'] == high)
    address = number >> spec['issue_address_shift']
    streams = spec['high_streams']
    table = []
    for stream in range(streams):
        group = address*streams+stream
        table.append((arith.bit_reverse((n >> (high+1))+group, aw),
                      arith.bit_reverse((n >> high)+2*group, aw),
                      arith.bit_reverse((n >> high)+2*group+1, aw)))
    beat = paired_issue(n, lanes, high, number)
    result = []
    for q in beat.quartets:
        stream = (q[0] >> (high+1)) & (streams-1)
        result.append(table[stream])
    return result


def spatial_schedule(beats=512, *, setup=1, issue_interval=1, gaps=(), boundary_guard=1):
    """Explicit edge calendar for two unchanged 6-stage canonical BF layers.

    E0 RAM/root issue; E1 destination data/root registers; E2 first BF accept;
    E7 first output; E8 inter-layer accept; E13 second output; E14 RAM commit.
    Second-layer roots are captured at E1, then six extra delay registers
    retain the value through E7 for acceptance at E8.
    Separate spatial arrays sustain II1. Setup/drain is NOT halved from parent.
    """
    need(beats >= 1 and issue_interval >= 1 and setup >= 0, 'schedule arguments')
    gap_map = dict(gaps)
    starts = []
    tick = setup
    for beat in range(beats):
        tick += gap_map.get(beat, 0)
        starts.append(tick)
        tick += issue_interval
    edges = [dict(beat=g, read=t, root_capture=t+1, first_accept=t+2,
                  first_output=t+7, second_accept=t+8, second_output=t+13, commit=t+14)
             for g, t in enumerate(starts)]
    for name in ('read', 'first_accept', 'second_accept', 'commit'):
        need(len({e[name] for e in edges}) == beats, 'per-array port conflict:' + name)
    return dict(beats=beats, setup=setup, issue_interval=issue_interval,
                gap_cycles=sum(gap_map.values()), read_to_commit_edges=14,
                cycles=edges[-1]['commit']+boundary_guard,
                per_pass_overhead_at_II1=setup+14+boundary_guard-1,
                boundary_guard=boundary_guard, first=edges[0], last=edges[-1],
                outstanding_root_frames=max(sum(e['root_capture'] <= t < e['second_accept']
                                                for e in edges) for t in range(starts[-1]+9)),
                status='exact_for_declared_calendar_not_measured_RTL')


def cycle_ledger(n=65536, lanes=64, *, root_setup=0, root_stalls=0, routing_guard=0):
    aw, _, beats = geometry(n, lanes)
    pairs, single = divmod(aw, 2)
    paired = spatial_schedule(beats)
    # An odd AW retains one independent radix2 pass (+9 frozen-ROM calendar).
    transforms = 2*(pairs*paired['cycles'] + single*(beats+9))
    point = math.ceil(n/lanes)+7
    controller = 6
    ntt = transforms+point+controller+root_setup+root_stalls+routing_guard
    parent = arith.cycle_work(n, lanes)
    return dict(n=n, spatial_butterflies_per_field=2*lanes, issues_per_pass=beats,
                passes_per_direction=pairs+single, pair_pass_cycles=paired['cycles'],
                pair_overhead_per_pass=paired['per_pass_overhead_at_II1'],
                pair_read_to_commit=14, merged_point_pass_cycles=point,
                controller_edges=controller, root_setup=root_setup, root_stalls=root_stalls,
                additional_routing_guard=routing_guard,
                ntt_cycles_for_declared_calendar=ntt,
                parent_ntt_cycles=parent['parent_ntt_cycles'],
                delta_against_parent_ntt=parent['parent_ntt_cycles']-ntt,
                G4_warm_conditional=32920-parent['parent_ntt_cycles']+ntt,
                T5b_warm_conditional=28826-parent['parent_ntt_cycles']+ntt,
                A4_warm_conditional=24720-parent['parent_ntt_cycles']+ntt,
                status='conditional composition; A4 fit failed, registered repair not qualified',
                exclusions=['No frequency prediction; no inherited setup halving.',
                            'Cold profile/init/cache eligibility not specified; cold total unassigned.',
                            'Additional root readiness/route/bank transition edges remain input parameters.'])


def fit_calibration():
    """Aggregate exactly identified hierarchy nodes, no parent/child doubling."""
    source_guard()
    rows = []
    for line in (ROOT/FIT).read_text().splitlines():
        cells = [v.strip() for v in line.split(';')][1:-1]
        if len(cells) == 20:
            rows.append(cells)
    patterns = dict(butterflies=r'field_lane\[\d\].engine\|child\|arithmetic\[\d+\].butterfly',
                    multiplier_children=r'field_lane\[\d\].engine\|child\|arithmetic\[\d+\].butterfly\|multiplier',
                    root_recurrences=r'field_lane\[\d\].engine\|child\|generated',
                    compact_profiles=r'field_lane\[\d\].engine\|child\|compact_profile')
    out = {}
    for name, pattern in patterns.items():
        selected = [c for c in rows if re.fullmatch(pattern, c[17])]
        need(len(selected) == (192 if name in ('butterflies', 'multiplier_children') else 3),
             'calibration hierarchy count:' + name)
        out[name] = dict(nodes=len(selected), **{key: round(sum(float(c[i].split()[0]) for c in selected), 1)
                         for key, i in dict(ALMs_needed=1, ALMs_placed=2, registers=7, M20K=10, DSP_needed=11).items()})
    out.update(parent_whole=dict(ALMs_needed=255052, ALMs_placed=302592, M20K=987,
                                DSP_needed=738, DSP_placed=755, LABs=36202),
               fit_sha256=PINS[FIT], status='finalize hierarchy packing estimates, not isolated cell fit')
    return out


def selector_ledger(n=65536, lanes=64, width=27):
    """Literal binary-mux-equivalent structure, not a Quartus ALM report.

    Read/write selectors factor seven adjacency patterns and two orientation
    bits; four data words/quartet. Inter-layer pairs are fixed wires after that.
    Root ROM: unique stream XORs, per-ROM direction select, then pass select on
    three roots/quartet. Broadcast outputs are conservative replicated logic.
    """
    aw, kw, _ = geometry(n, lanes)
    patterns = len({tuple(sorted((h % kw, (h-1) % kw))) for h in range(1, aw, 2)})
    words = 2*lanes
    parent_data = 2*words*width*(kw-1+1)
    pair_data = 2*words*width*(patterns-1+2)
    roots = packed_root_layout(n, lanes)
    stream = sum(r['stream_xor_mux_bits'] for r in roots['rows'])
    direction = sum(r['width'] for r in roots['rows'])
    pass_select = 3*(lanes//2)*27*(len(roots['rows'])-1)
    parent_root = lanes*width*(kw-1)
    return dict(payload_width=width, pattern_choices=patterns, quartet_orientation_bits=2,
                parent_data_mux_bits=parent_data, paired_data_mux_bits=pair_data,
                delta_data_mux_bits=pair_data-parent_data,
                root_stream_xor_mux_bits=stream, root_direction_mux_bits=direction,
                root_pass_select_mux_bits=pass_select,
                paired_root_mux_bits=stream+direction+pass_select,
                parent_generated_root_mux_bits=parent_root,
                delta_root_mux_bits=stream+direction+pass_select-parent_root,
                inter_layer_routing='fixed wires for each selected ordered quartet',
                validity_address_control_excluded=True,
                excludes='ALM packing, constant pruning, fanout replication and LAB fragmentation')


def resource_ledger(*, alm_per_mux_bit=0.5, control_reserve=4096):
    calibration = fit_calibration()
    select = selector_ledger()
    root = packed_root_layout()
    bf = calibration['butterflies']['ALMs_needed']
    mul = calibration['multiplier_children']['ALMs_needed']
    recurrence = calibration['root_recurrences']['ALMs_needed']
    compact = calibration['compact_profiles']['ALMs_needed']
    baseline = calibration['parent_whole']['ALMs_needed']
    data_route = 3*select['delta_data_mux_bits']*alm_per_mux_bit
    root_route = 3*select['delta_root_mux_bits']*alm_per_mux_bit
    rom_alm = baseline+bf+mul-recurrence-compact+data_route+root_route+control_reserve
    recurrence_alm = baseline+bf+mul+recurrence+data_route+control_reserve
    # Root payload holds second-layer roots for six edges; all first-layer data
    # results remain in the BF registers until the next layer accept edge.
    registers = dict(second_layer_root_payload=3*64*27*6,
                     extra_data_destination=3*128*27,
                     extra_row_tag_for_six_edges=3*128*9*6,
                     upper_normalizer_pipeline_included_in_measured_mul_proxy=True)
    return dict(calibration=calibration, selectors=select,
                assumptions=dict(ALM_per_binary_mux_bit=alm_per_mux_bit,
                                 uncalibrated_control_and_tag_reserve=control_reserve,
                                 area_budget_needed_ALMs=320000,
                                 butterfly_and_normalizer_proxy='duplicate measured canonical cells; placement interaction unmodeled'),
                packed_ROM=dict(ALMs_needed_planning=round(rom_alm, 1),
                    ledger=dict(baseline=baseline, extra_butterfly_layer=bf,
                                final_GS_upper_normalizers=mul, removed_recurrence=-recurrence,
                                removed_compact_profile=-compact, data_selector_delta=data_route,
                                root_selector_delta=root_route, control_reserve=control_reserve),
                    DSP_needed_proxy=738+192+192-192,
                    M20K_proxy=987-192-96+3*root['both_directions_M20K_per_field'],
                    root_M20K_per_field=root['both_directions_M20K_per_field'],
                    decision='NO_GO_canonical_conservative_selector_plan' if rom_alm > 320000 else 'CONDITIONAL_GO_model_only'),
                duplicated_recurrence=dict(ALMs_needed_planning=round(recurrence_alm, 1),
                    DSP_needed_proxy=738+192+192+192, M20K_proxy=987+192+96,
                    root_supply_status='extra recurrence descriptor/ready/context model absent; area bound alone exceeds gate',
                    decision='NO_GO'),
                incremental_register_bits=registers,
                zero_new_route_floor=round(baseline+bf+mul-recurrence-compact, 1),
                root_and_data_route_plus_control_allowance=round(320000-(baseline+bf+mul-recurrence-compact), 1),
                mux_cost_break_even_at_reserve=round((320000-control_reserve-(baseline+bf+mul-recurrence-compact))/
                      (3*(select['delta_data_mux_bits']+select['delta_root_mux_bits'])), 6),
                physical=False, raw_placement_projection=None,
                excludes=['No A4/lean27/X1 resource savings credited.',
                          'M20K is legal-rectangle proxy, not inferred packing.',
                          'No physical resource bound; mux cost sensitivity and root routing may be improved.'])


def small_numeric_gate():
    cases = 0
    for n in (2, 4, 8, 16, 32, 64, 128, 256):
        rng = random.Random(223100+n)
        for field in arith.FIELDS:
            patterns = ([0]*n, [field.p-1]*n, [rng.randrange(field.p) for _ in range(n)])
            for values in patterns:
                forward = fused_transform(values, field)
                arith.compare(forward, arith.merged_forward(values, field), 'paired-vs-single-forward')
                arith.compare(forward, arith.direct_spectrum(values, field), 'paired-direct-spectrum')
                inverse = fused_transform(forward, field, inverse=True)
                arith.compare(inverse, [n*x % field.p for x in values], 'paired-roundtrip')
                arith.compare(fused_square(values, field),
                              [v % field.p for v in arith.direct_coefficients(values)], 'paired-direct-square')
                cases += 1
    return dict(cases=cases, maximum_numeric_n=256, bit_exact_Montgomery_radix=2**32,
                fields=3, direct_spectrum_and_negacyclic_square=True, passed=True)


def report():
    need(not (ROOT/'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    pins = source_guard()
    bank = [banking_gate(high=high) for high in range(1, 16, 2)]
    roots_checked = 0
    for high in range(1, 16, 2):
        for number in range(512):
            beat = paired_issue(65536, 64, high, number)
            h, l = beat_roots(65536, beat)
            actual = packed_root_exponents(65536, 64, high, number)
            need(actual == [(eh,) + el for eh, el in zip(h, l)], 'packed root exponent route')
            roots_checked += len(actual)*3
    resources = resource_ledger()
    return dict(task='B20261001N-N1', status='model_complete_banking_PASS_canonical_area_NO_GO',
                source_hashes=pins, model_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                banking=bank, full_N_symbolic_addresses_checked=sum(r['addresses_checked'] for r in bank),
                packed_root_symbolic_exponents_checked=roots_checked,
                arithmetic=small_numeric_gate(), cycle_ledger=cycle_ledger(),
                calendar=spatial_schedule(), root_supply=packed_root_layout(), resources=resources,
                sensitivity=[dict(ALM_per_mux_bit=cost, reserve=reserve,
                    ALMs=resource_ledger(alm_per_mux_bit=cost, control_reserve=reserve)['packed_ROM']['ALMs_needed_planning'])
                    for cost in (0.25, 0.5, 0.75) for reserve in (0, 4096)],
                decision='Banking GO; canonical spatial architecture NO-GO at declared area proxy. No successor RTL authoring.',
                evidence_class='source-bound symbolic model and N<=256 integer oracle only',
                frequency_mhz=None, hardware_throughput=None, cold_cycles=None,
                next_step='Reduce/root-route and canonical-cell measured area before requesting an architectural prototype.',
                deviations=['Actual CT/GS merged roots used; not the earlier cyclic DIF/DIT feasibility formulas.',
                            'Existing single-stage batches must be regrouped at high pairs; bank_of remains unchanged.',
                            '+192 DSP alone omits mandatory +192 parallel upper normalizers. ROM removal can offset192 recurrence DSP.',
                            'Memory pass count halves; modeled paired setup/drain remains15 edges/pass, not half parent overhead.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', action='store_true')
    parser.parse_args()
    print(json.dumps(report(), indent=2)+'\n')
