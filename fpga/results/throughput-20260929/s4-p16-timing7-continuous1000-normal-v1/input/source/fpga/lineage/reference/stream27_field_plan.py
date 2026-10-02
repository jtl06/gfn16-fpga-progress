"""S3 one-field topology/root compiler and explicit implementation gap ledger.

Geometry-only full-N planning is allowed locally. Numeric NTTs are limited to
small N. Emitted transform source is a source-only candidate, never an RTL or
100 MHz qualification. The frozen S1 files are read, not modified.
"""
from __future__ import annotations

from math import ceil
from pathlib import Path
import hashlib

from .stream_ntt_model import FIELDS, bit_reverse
from .stream_ntt_schedule import dimensions, index_of, m20k


FROZEN = {
    'reference/stream_ntt_schedule.py': '03c1c855e0f6e31f0fcb85d32ed2e604a935e482dfa725d7207e635cb1e963cc',
    'reference/stream_ntt_blockcarry_schedule.py': 'eca87517cada3413f18313d447b76e1fcf3c3826e70391f3baf39561ab23b632',
}


def verify_sources():
    root = Path(__file__).resolve().parents[1]
    for path, expected in FROZEN.items():
        if hashlib.sha256((root / path).read_bytes()).hexdigest() != expected:
            raise ValueError('FIELD_FROZEN_SOURCE_DRIFT: ' + path)
    paths = (*FROZEN, 'rtl/kernel/genefer_ntt_banked27_engine.sv',
             'rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv',
             'rtl/kernel/genefer_digit_reduce27_pipe.sv',
             'rtl/kernel/genefer_stream27_signed_boundary_reduce27_pipe.sv')
    return {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in paths}


def topology(n=65536, p=8, *, inverse=False):
    """O(AW*P) geometry, with no N-element arithmetic or observer arrays.

    Root exponent = low target-bit portion of the butterfly's lower index,
    multiplied by N/2^(target+1). Every time-varying root trace has a power-of-
    two period. Distinct fixed lane portions identify independent ROM streams.
    """
    aw, pw, ticks = dimensions(n, p)
    if not 3 <= aw <= 16 or p != 8:
        raise ValueError('FIELD_GEOMETRY: AW3..16/P8 (AW3 is correction transform only)')
    lane_bits = list(range(pw)) if inverse else list(range(aw - 1, aw - pw - 1, -1))
    time_bits = list(range(pw, aw)) if inverse else list(range(aw - pw))
    stages = []
    first = 0
    for number, target in enumerate(range(aw) if inverse else range(aw - 1, -1, -1)):
        depth = 0
        swap_position = None
        replaced = None
        incoming = first
        if target not in lane_bits:
            time_position = time_bits.index(target)
            depth = 1 << time_position
            replaced = min(lane_bits) if inverse else max(lane_bits)
            swap_position = lane_bits.index(replaced)
            lane_bits[swap_position], time_bits[time_position] = target, replaced
            first += depth + 1  # registered commutator -> next-edge BF
        pair_position = lane_bits.index(target)
        pairs = [(lane, lane ^ (1 << pair_position)) for lane in range(p)
                 if not lane & (1 << pair_position)]
        varying = [(position, bit) for position, bit in enumerate(time_bits) if bit < target]
        period = 1 << (max(position for position, _ in varying) + 1) if varying else 1
        fixed = [index_of(0, lower, lane_bits, time_bits) & ((1 << target) - 1)
                 for lower, _ in pairs]
        unique = sorted(set(fixed))
        streams = [dict(fixed_index=base, period=period,
                        stored_words=period if varying else 0,
                        constant_exponent=None if varying else base * (n >> (target + 1)))
                   for base in unique]
        stages.append(dict(stage=number, target_index_bit=target,
                           lane_bits=list(lane_bits), time_bits=list(time_bits),
                           commutator_replaced_lane_bit=replaced,
                           commutator_lane_position=swap_position,
                           shuffle_depth_per_buffer=depth,
                           shuffle_buffer_count=p if depth else 0,
                           pairs=pairs, root_stream_for_pair=[unique.index(base) for base in fixed],
                           unique_root_streams=streams, varying_root_bits=varying,
                           input_first_accept=incoming, butterfly_first_accept=first,
                           butterfly_first_output=first + 5,
                           next_stage_first_accept=first + 6))
        first += 6  # frozen BF k+5 -> next-edge consumer
    final_bits = list(range(aw - 1, aw - pw - 1, -1)) if inverse else list(range(pw))
    position = {bit: j for j, bit in enumerate(lane_bits)}
    terminal_wire = [sum(((lane >> j) & 1) << position[bit] for j, bit in enumerate(final_bits))
                     for lane in range(p)]
    return dict(n=n, p=p, aw=aw, pw=pw, frame_ticks=ticks,
                direction='DIT' if inverse else 'DIF', stages=stages,
                terminal_wire=terminal_wire, first_output_edge=first - 1,
                first_next_consumer_edge=first, physical_dense_rows=ticks,
                root_ROM_contract='prefetch next row; first row uses static root0; no extra stage edge',
                status='source_only_geometry_not_RTL_qualified')


def root_exponent(plan, stage, stream, row):
    spec = plan['stages'][stage]
    root = spec['unique_root_streams'][stream]
    if not 0 <= row < root['period']:
        raise ValueError('FIELD_ROOT_ADDRESS')
    low = root['fixed_index'] + sum(((row >> position) & 1) << bit
                                  for position, bit in spec['varying_root_bits'])
    return low * (plan['n'] >> (spec['target_index_bit'] + 1))


def root_word(plan, stage, stream, row, field):
    prime, generator = FIELDS[field]
    omega = pow(generator, (prime - 1) // plan['n'], prime)
    if plan['direction'] == 'DIT':
        omega = pow(omega, -1, prime)
    return pow(omega, root_exponent(plan, stage, stream, row), prime) * (1 << 32) % prime


def resource_plan(n=65536, p=8, *, payload_bits=1, generation_bits=8):
    """Keep attributable field proxies separate from shared CRT/carry/control.

    PAYLOAD1 has no index semantics: the proposed field ties that bit to zero
    and derives index/root addresses from physical frame counters. Native
    proof of that production specialization is still required. No tag-RAM
    compression or cross-FIFO packing is credited to the literal cell shape.
    """
    forward = topology(n, p)
    inverse = topology(n, p, inverse=True)
    stages = forward['stages'] + inverse['stages']
    aw, pw, ticks = dimensions(n, p)
    if aw < 5:
        raise ValueError('FIELD_PROFILE_GEOMETRY: full field requires AW5..16')
    if payload_bits < 1 or generation_bits < 1:
        raise ValueError('FIELD_TOKEN_WIDTH')
    word_bits = 27 + payload_bits + generation_bits + 1 + 1
    depths = [s['shuffle_depth_per_buffer'] for s in stages if s['shuffle_buffer_count']]
    packed_deep = sum(m20k(depth, p * 27) for depth in depths if depth > 32)
    literal_deep = p * sum(m20k(depth, word_bits) for depth in depths if depth > 32)
    packed_mlab = sum(ceil(p * 27 / 20) for depth in depths if depth <= 32)
    literal_mlab = p * sum(ceil(word_bits / 20) for depth in depths if depth <= 32)
    roots = sum(m20k(root['stored_words'], 27) for s in stages
                for root in s['unique_root_streams'] if root['stored_words'])
    components = {
        'forward_inverse_butterflies': dict(units=2 * aw * (p // 2), ALM_per_unit_proxy=375),
        'small_P_point_correction_butterflies': dict(units=pw * (p // 2), ALM_per_unit_proxy=375),
        'twist_square_fused_untwist_multipliers': dict(units=3 * p, ALM_per_unit_proxy=375),
        'segmented_correction_term_multipliers': dict(units=p, ALM_per_unit_proxy=375),
        'small_correction_twist_multipliers': dict(units=p, ALM_per_unit_proxy=375),
        'digit_and_shared_c0_c1_signed_reducers': dict(units=2 * p, ALM_per_unit_proxy=375),
        'shallow_FIFO_MLAB_source_shape': dict(units=literal_mlab, ALM_per_unit_proxy=10),
    }
    for component in components.values():
        component['ALM_planning_proxy'] = component['units'] * component['ALM_per_unit_proxy']
    subtotal = sum(component['ALM_planning_proxy'] for component in components.values())
    original_subtotal = subtotal - 10 * (literal_mlab - packed_mlab)
    io_rom = 2 * m20k(ticks, p * 27)
    seed_rom = m20k(4 * p, p * 27)
    recurrence_rom = m20k(max(1, aw - pw - 2), p * 27)
    field_ram = literal_deep + roots + io_rom + seed_rom + recurrence_rom
    # Readback is a shared digit image, not replicated once per RNS field.
    readback_ram = p * m20k(ticks, 32)
    s1_whole_ram = 3 * (packed_deep + roots + io_rom + seed_rom + recurrence_rom) + readback_ram
    whole_literal_ram = 3 * field_ram + readback_ram
    return dict(n=n, p=p, physical_token=dict(data_bits=27, payload_bits=payload_bits,
                generation_bits=generation_bits, owner_bits=1, slot_bits=1, total_bits=word_bits,
                payload_semantics='constant zero; order/root addresses use physical row counters',
                specialization_RTL_qualified=False),
                components=components, per_field_ALM_planning_proxy=subtotal,
                per_field_original_S1_noncontrol_ALM_proxy=original_subtotal,
                comparison_110_percent_noncontrol_proxy=ceil(subtotal * 110 / 100),
                field_control_ALM_allowance='unallocated part of S1 whole 25000 reserve; needs explicit allocation before threshold adoption',
                shared_excluded=dict(CRT_P8_ALM_proxy=ceil(11257 * p / 16),
                    carry_P8_ALM_proxy=ceil(29500 * p / 16),
                    whole_control_valid_base_ALM_reserve=25000, readback_digit_M20K=readback_ram),
                memory=dict(S1_packed_data_only_delay_M20K=packed_deep,
                    literal_tagged_per_FIFO_delay_M20K=literal_deep,
                    S1_packed_data_only_shallow_MLAB=packed_mlab,
                    literal_tagged_per_FIFO_shallow_MLAB=literal_mlab,
                    roots_M20K=roots, twist_untwist_M20K=io_rom,
                    term_seed_M20K=seed_rom, term_factor_M20K=recurrence_rom,
                    field_listed_M20K=field_ram, S1_whole_listed_M20K=s1_whole_ram,
                    whole_literal_listed_M20K=whole_literal_ram,
                    whole_M20K_margin_before_possible_divider8=2713 - whole_literal_ram,
                    possible_divider_M20K_addition=8, inferred_or_fitted=False),
                DSP_proxy=sum(components[name]['units'] for name in components
                    if name not in ('digit_and_shared_c0_c1_signed_reducers', 'shallow_FIFO_MLAB_source_shape')),
                status='itemized_planning_proxies_not_component_fit')


def field_contract(n=65536, p=8):
    """Concrete field partition; unimplemented pieces fail the completion gate.

    A field takes ordinary digits plus same-image signed c0/c1, and emits
    ordinary square residues in bit_reverse(lane,3)*T+row order for the shared
    CRT. It does not own CRT, carry, canonical readback, or host base change.
    """
    forward, inverse = topology(n, p), topology(n, p, inverse=True)
    aw, pw, ticks = dimensions(n, p)
    if aw < 5:
        raise ValueError('FIELD_PROFILE_GEOMETRY: full field requires AW5..16')
    fwd_x = 8 + forward['first_output_edge']
    inverse_start = fwd_x + 1 + 2 + 4
    residue = inverse_start + inverse['first_next_consumer_edge'] + 3
    return dict(n=n, p=p, contexts=1,
        input_order='index=bit_reverse(lane,3)*T+row',
        spectral_order='slot=P*row+lane; frequency=bit_reverse(slot,AW)',
        output_order='index=bit_reverse(lane,3)*T+row',
        domains=dict(input='ordinary digits/reduced residues', roots='Montgomery R',
            correction_tables='ordinary residues', square='ordinary square times R^-1',
            output='ordinary square residues', final_constant='psi^-index*N^-1*R^2'),
        cycle_model=dict(first_digit_accept=0, first_twisted_BF_accept=8,
            first_forward_X_output=fwd_x, first_inverse_BF_accept=inverse_start,
            first_field_residue_output=residue,
            first_CRT_accept=residue + 1, physical_frame_rows=ticks,
            dependent_whole_square_interval_conditional=2 * ticks + 12 * aw + 2 * (aw - pw) + 58,
            root_read_latency='next-row prefetch plus static root0; no added BF acceptance edge',
            observed_native=False),
        physical_contract=dict(slot_valid='transport every occupied row including canceled generations',
            frame_start='physical first row; never suppress on cancellation',
            row_counter='advance on slot_valid, never on advisory eligible',
            cancellation='generation/enabled affects terminal eligibility, not cadence',
            quarantine='registered aggregate stage error freezes physical transport',
            commit='check current generation/enabled and all fault_pending at actual sink write edge',
            reset='clear all slot/tag/counters; RAM retains data; require coherent reload',
            generation_reuse='forbidden until all old physical rows drained'),
        implementation_ledger=[
            dict(block='digit reducer', status='existing source helper', edges=3),
            dict(block='twist/fused untwist', status='existing sparse mul helper; new ROM/tag wrapper required', edges=3),
            dict(block='forward/inverse MDC', status='generated source-only transform candidate; native integration required', BF_edges=5),
            dict(block='composable commutator', status='v2 owned by stream_interface; native gate pending', edges='DEPTH'),
            dict(block='c0/c1 normalization', status='shared signed reducer native gate; field scheduling wrapper required', edges=4),
            dict(block='small correction transforms', status='AW=log2P specialization of generated transform; wrapper required'),
            dict(block='segmented 4-context term', status='exact S1 model; RTL seed/reseed/feedback wrapper required', edges=3),
            dict(block='two canonical modular add stages', status='new tagged row wrapper required', edges=2),
            dict(block='pointwise square', status='existing sparse mul helper; tagged wrapper required', edges=3),
            dict(block='field reset/error/completion', status='new physical controller; native reset/drain gates required'),
        ],
        complete_field_RTL_ready=False, component_clock_qualified=False,
        next_gate='settle composable cell; integrate complete tagged field; small AW then AW16; synthesis then 100MHz component fit')


def require_complete_field(contract):
    if not contract.get('complete_field_RTL_ready'):
        raise ValueError('FIELD_INCOMPLETE: transform scaffold cannot be staged as a complete field fit')


def manifest(n=65536):
    return dict(source_sha256=verify_sources(), field=field_contract(n),
                forward=topology(n), inverse=topology(n, inverse=True),
                production_payload1=resource_plan(n, payload_bits=1),
                diagnostic_payload16=resource_plan(n, payload_bits=16),
                limits=['Source-only planning; no HDL, native/cloud execution or component clock claim.',
                        'Full-N geometry only; numeric transform tests stay small N.',
                        'S1 16660 interval is conditional until all wrappers honor their declared edges.',
                        'Per-field control reserve allocation is pending; do not automatically adopt the computed 110% noncontrol threshold.'])
