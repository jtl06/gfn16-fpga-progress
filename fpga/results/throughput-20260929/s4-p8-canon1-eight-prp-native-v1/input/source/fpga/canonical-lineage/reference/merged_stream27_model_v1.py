"""S-M2 merged CT/GS MDC model and compact gathered-row-bit root layout.

Numeric transforms are small<=256 only. Full-N generation creates scalar ROM
constants/geometry, never executes a numeric NTT. Frozen S1/P2 are unchanged.
Canonical27 first; lazy2P and a folded double are separate, explicit contracts.
"""
from pathlib import Path
import hashlib

from fpga.reference import merged_negacyclic27_model as math
from fpga.reference import stream_ntt_schedule as schedule

ROOT = Path(__file__).resolve().parents[1]
PROFILE = 'merged-stream27-ctgs-ordinary-v1'
PINS = {
    'reference/merged_negacyclic27_model.py': '103c7bbe6917288a92c7432e80d50bc317e6c50eb720a6c604b3a121966adfb4',
    'reference/stream_ntt_schedule.py': '03c1c855e0f6e31f0fcb85d32ed2e604a935e482dfa725d7207e635cb1e963cc',
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def source_guard():
    for name, digest in PINS.items():
        need(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, 'MERGED_STREAM_SOURCE_DRIFT:' + name)
    return dict(PINS)


def topology(n=65536, p=8, *, inverse=False):
    aw, pw, ticks = schedule.dimensions(n, p)
    need(p in (8, 16) and pw <= aw <= 16, 'MERGED_STREAM_GEOMETRY:P8/P16, N>=P')
    lane_bits = list(range(pw)) if inverse else list(range(aw - 1, aw - pw - 1, -1))
    time_bits = list(range(pw, aw)) if inverse else list(range(aw - pw))
    stages = []
    first = 0
    for number, target in enumerate(range(aw) if inverse else range(aw - 1, -1, -1)):
        depth, replaced, swap = 0, None, None
        incoming = first
        if target not in lane_bits:
            position = time_bits.index(target)
            depth = 1 << position
            replaced = min(lane_bits) if inverse else max(lane_bits)
            swap = lane_bits.index(replaced)
            lane_bits[swap], time_bits[position] = target, replaced
            first += depth + 1
        pair_position = lane_bits.index(target)
        pairs = [(lane, lane ^ (1 << pair_position)) for lane in range(p) if not lane & (1 << pair_position)]
        varying = [(position, bit) for position, bit in enumerate(time_bits) if bit > target]
        fixed = [schedule.index_of(0, lower, lane_bits, time_bits) >> (target + 1) for lower, _ in pairs]
        unique = sorted(set(fixed))
        address_bits = len(varying)
        streams = [dict(fixed_group=group, stored_words=(1 << address_bits) if address_bits else 0,
                        address_words=1 << address_bits) for group in unique]
        stages.append(dict(stage=number, target_index_bit=target, arithmetic_dif=int(inverse),
                           lane_bits=list(lane_bits), time_bits=list(time_bits), pairs=pairs,
                           commutator_replaced_lane_bit=replaced, commutator_lane_position=swap,
                           shuffle_depth_per_buffer=depth, shuffle_buffer_count=p if depth else 0,
                           root_stream_for_pair=[unique.index(group) for group in fixed],
                           unique_root_streams=streams, varying_group_bits=varying,
                           address_row_positions=[position for position, _ in varying], address_bits=address_bits,
                           packed_root_width=27 * len(streams),
                           input_first_accept=incoming, butterfly_first_accept=first,
                           butterfly_first_output=first + 5, next_stage_first_accept=first + 6))
        first += 6
    final_bits = list(range(aw - 1, aw - pw - 1, -1)) if inverse else list(range(pw))
    position = {bit: j for j, bit in enumerate(lane_bits)}
    terminal_wire = [sum(((lane >> j) & 1) << position[bit] for j, bit in enumerate(final_bits)) for lane in range(p)]
    return dict(profile=PROFILE, n=n, p=p, aw=aw, pw=pw, frame_ticks=ticks,
                direction='GS' if inverse else 'CT', inverse=inverse, stages=stages,
                terminal_wire=terminal_wire,
                input_order='contiguous bit-reversed spectral slots' if inverse else 'bit_reverse(lane,PW)*T+row',
                output_order='bit_reverse(lane,PW)*T+row' if inverse else 'slot=P*row+lane; frequency=bit_reverse(slot,AW)',
                first_output_edge=first - 1, first_next_consumer_edge=first,
                root_contract='physical-row counter; gather address_row_positions; next-row sync prefetch; row0 static bypass',
                canonical_bits=27, lazy2P_supported=False, contexts=1,
                normalization='last GS lower root and separate parallel upper multiplier; no extra output edge assumed until native proof',
                status='source_only_geometry_and_arithmetic_not_RTL_clock')


def root_address(plan, stage, physical_row):
    need(0 <= physical_row < plan['frame_ticks'], 'MERGED_STREAM_PHYSICAL_ROW')
    positions = plan['stages'][stage]['address_row_positions']
    return sum(((physical_row >> position) & 1) << bit for bit, position in enumerate(positions))


def root_exponent(plan, stage, stream, address):
    spec = plan['stages'][stage]
    need(0 <= address < (1 << spec['address_bits']), 'MERGED_STREAM_ROOT_ADDRESS')
    target = spec['target_index_bit']
    group = spec['unique_root_streams'][stream]['fixed_group']
    group += sum(((address >> k) & 1) << (bit - target - 1)
                 for k, (_, bit) in enumerate(spec['varying_group_bits']))
    return math.bit_reverse((plan['n'] >> (target + 1)) + group, plan['aw'])


def root_word(plan, stage, stream, address, field, *, normalized_final=False, input_domain=0, fold_double=0):
    need(field in (0, 1, 2) and fold_double in (0, 1), 'MERGED_STREAM_FIELD_OR_DOUBLE')
    f = math.FIELDS[field]
    exponent = root_exponent(plan, stage, stream, address)
    root = pow(math.psi_for(plan['n'], f), -exponent if plan['inverse'] else exponent, f.p)
    final = plan['inverse'] and stage == plan['aw'] - 1 and normalized_final
    if final:
        scale = math.normalization_constant(plan['n'], f, input_domain) * (1 << fold_double) % f.p
        return root * scale % f.p
    need(not fold_double, 'MERGED_STREAM_DOUBLE_ONLY_FINAL_NORMALIZATION')
    return f.encode(root, 1)


def packed_root_word(plan, stage, address, field, **kwargs):
    return sum(root_word(plan, stage, stream, address, field, **kwargs) << (27 * stream)
               for stream in range(len(plan['stages'][stage]['unique_root_streams'])))


def transform(values, p=8, field=0, *, inverse=False, normalized=False, input_domain=0, fold_double=0, mutant=None):
    n = len(values)
    need(n <= 256, 'MERGED_STREAM_SMALL_NUMERIC_ONLY')
    f = math.FIELDS[field]
    need(all(type(v) is int and 0 <= v < f.p for v in values), 'MERGED_STREAM_CANONICAL')
    plan = topology(n, p, inverse=inverse)
    lane_bits = list(range(plan['pw'])) if inverse else list(range(plan['aw'] - 1, plan['aw'] - plan['pw'] - 1, -1))
    time_bits = list(range(plan['pw'], plan['aw'])) if inverse else list(range(plan['aw'] - plan['pw']))
    frames = [[schedule.Token(schedule.index_of(row, lane, lane_bits, time_bits),
                              values[schedule.index_of(row, lane, lane_bits, time_bits)])
               for lane in range(p)] for row in range(plan['frame_ticks'])]
    for spec in plan['stages']:
        stage, target = spec['stage'], spec['target_index_bit']
        if spec['shuffle_depth_per_buffer']:
            frames = schedule.commutator(frames, spec['commutator_lane_position'], spec['shuffle_depth_per_buffer'])
        for row, frame in enumerate(frames):
            for lane, token in enumerate(frame):
                need(token.index == schedule.index_of(row, lane, spec['lane_bits'], spec['time_bits']), 'MERGED_STREAM_TOKEN_ORDER')
            address = root_address(plan, stage, row)
            for k, (upper, lower) in enumerate(spec['pairs']):
                a, b = frame[upper], frame[lower]
                stream = spec['root_stream_for_pair'][k]
                w = root_word(plan, stage, stream, address, field,
                              normalized_final=normalized, input_domain=input_domain,
                              fold_double=fold_double if inverse and stage == plan['aw'] - 1 else 0)
                if mutant == 'old-cyclic-roots':
                    exponent = (a.index & ((1 << target) - 1)) * (n >> target)
                    w = f.encode(pow(math.psi_for(n, f), -exponent if inverse else exponent, f.p), 1)
                elif mutant == 'physical-row-address':
                    wrong = row & ((1 << spec['address_bits']) - 1)
                    w = root_word(plan, stage, stream, wrong, field, normalized_final=normalized,
                                  input_domain=input_domain, fold_double=fold_double if inverse and stage == plan['aw'] - 1 else 0)
                elif mutant == 'inverse-forward-root' and inverse:
                    exponent = root_exponent(plan, stage, stream, address)
                    w = f.encode(pow(math.psi_for(n, f), exponent, f.p), 1)
                final = inverse and normalized and stage == plan['aw'] - 1
                if inverse:
                    y0 = (a.value + b.value) % f.p
                    if final and mutant != 'upper-unscaled':
                        scale = math.normalization_constant(n, f, input_domain) * (1 << fold_double) % f.p
                        y0 = f.mont(y0, scale)
                    y1 = f.mont((a.value - b.value) % f.p, w)
                else:
                    product = f.mont(b.value, w)
                    y0, y1 = (a.value + product) % f.p, (a.value - product) % f.p
                frame[upper], frame[lower] = schedule.Token(a.index, y0), schedule.Token(b.index, y1)
    frames = [[frame[index] for index in plan['terminal_wire']] for frame in frames]
    expected_order = [[math.bit_reverse(lane, plan['pw']) * plan['frame_ticks'] + row if inverse else row * p + lane
                       for lane in range(p)] for row in range(plan['frame_ticks'])]
    need([[token.index for token in frame] for frame in frames] == expected_order, 'MERGED_STREAM_OUTPUT_ORDER')
    output = [0] * n
    for frame in frames:
        for token in frame:
            output[token.index] = token.value
    return output


def square(digits, p=8, field=0, *, input_domain=0, fold_double=0, mutant=None):
    f = math.FIELDS[field]
    spectrum = transform([f.encode(d, input_domain) for d in digits], p, field, input_domain=input_domain, mutant=mutant)
    return transform([f.mont(x, x) for x in spectrum], p, field, inverse=True, normalized=True,
                     input_domain=input_domain, fold_double=fold_double, mutant=mutant)


def centered_recover(planes, *, double_bit=0, doubling='post_crt', proved_doubled_bound=None):
    need(double_bit in (0, 1) and doubling in ('post_crt', 'normalization'), 'MERGED_STREAM_DOUBLING_CONTRACT')
    if doubling == 'normalization' and double_bit:
        need(type(proved_doubled_bound) is int and 0 <= proved_doubled_bound <= math.HALF,
             'MERGED_STREAM_FOLDED_DOUBLE_NEEDS_CENTERED_BOUND')
    result = []
    for row in zip(*planes):
        value = sum(r * w for r, w in zip(row, math.CRT_WEIGHTS)) % math.MODULUS
        value = value - math.MODULUS if value > math.HALF else value
        result.append(value * (1 << double_bit) if doubling == 'post_crt' else value)
    return result


def block_state_square(state, *, doubling='post_crt', double_bit=0, mutant=None):
    from fpga.reference import stream_ntt_blockcarry_model as block
    n, p = len(state.digits), len(state.c0)
    need(n <= 256, 'MERGED_STREAM_SMALL_NUMERIC_ONLY')
    proof = block.proof(n, p, state.base)
    planes = []
    for field, f in enumerate(math.FIELDS):
        values = transform([d % f.p for d in state.digits], p, field, mutant=mutant)
        tables = block.proposal.correction_tables(state, field)
        values = [(x + block.proposal.spectral_correction(state, field, slot, tables)) % f.p
                  for slot, x in enumerate(values)]
        squared = [f.mont(x, x) for x in values]
        planes.append(transform(squared, p, field, inverse=True, normalized=True,
                                fold_double=double_bit if doubling == 'normalization' else 0, mutant=mutant))
    return centered_recover(planes, double_bit=double_bit, doubling=doubling,
                            proved_doubled_bound=proof['doubled_coefficient_bound'])


def root_layout(n=65536, p=8, field=0, *, normalized_final=True, emit_words=False, allow_full_constants=False):
    need(not emit_words or n <= 256 or allow_full_constants, 'MERGED_STREAM_FULL_CONSTANTS_EXPLICIT_ONLY')
    layouts = []
    files = {}
    for inverse in (False, True):
        plan = topology(n, p, inverse=inverse)
        for spec in plan['stages']:
            stage = spec['stage']
            width = spec['packed_root_width']
            depth = 1 << spec['address_bits']
            name = f'merged_stream27_{"gs" if inverse else "ct"}_aw{plan["aw"]}_p{p}_f{field}_s{stage}.hex'
            entry = dict(direction=plan['direction'], stage=stage, target=spec['target_index_bit'],
                         streams=len(spec['unique_root_streams']), address_bits=spec['address_bits'],
                         row_positions=spec['address_row_positions'], width=width, depth=depth,
                         file=name if spec['address_bits'] else None,
                         first_word=packed_root_word(plan, stage, 0, field, normalized_final=normalized_final),
                         M20K_tiling_proxy=schedule.m20k(depth, width) if spec['address_bits'] else 0)
            if emit_words and spec['address_bits']:
                digits = (width + 3) // 4
                files[name] = ''.join(f'{packed_root_word(plan,stage,address,field,normalized_final=normalized_final):0{digits}x}\n'
                                      for address in range(depth))
            layouts.append(entry)
    return dict(profile=PROFILE, n=n, p=p, field=field, entries=layouts, files=files,
                packed_transform_root_M20K_proxy=sum(x['M20K_tiling_proxy'] for x in layouts),
                IO_twist_untwist_root_tables=0, normalization_upper_multipliers=p // 2,
                net_removed_twist_untwist_multiplier_lanes=2 * p - p // 2,
                full_N_numeric_NTT_performed=False, inferred_RAM_or_fit=False)
