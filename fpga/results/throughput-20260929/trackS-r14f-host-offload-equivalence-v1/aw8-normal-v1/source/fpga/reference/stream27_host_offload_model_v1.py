"""Private r93 B host boundary model; not a core, native gate, or promotion.

Small conversion/finalization checks are local. Full-size linear conversion
timing is allowed only on an actual Linux aethia worker, never the coordinator.
No NTT or full-PRP execution is provided by this module.
"""
from dataclasses import dataclass
import socket
import sys

from . import stream27_blockcarry_param_model_v1 as carry_profile
from . import stream27_canonical_image_model_v1 as canonical
from . import stream27_signed_boundary_oracle as converter
from . import stream_ntt_model as arithmetic


def need(ok, why):
    if not ok:
        raise ValueError('HOST_OFFLOAD_' + why)


def geometry(n, p):
    need(type(n) is int and n in (32, 256, 65536) and type(p) is int and p == 16,
         'EXPLICIT_P16_GEOMETRY')
    return canonical.geometry(n.bit_length() - 1, p)


def worker_numeric(n):
    if n > 256:
        need(sys.platform.startswith('linux') and socket.gethostname().split('.')[0] == 'aethia',
             'FULL_CONVERSION_AETHIA_ONLY')


def wire32(value):
    need(type(value) is int and -(1 << 31) <= value < (1 << 32), 'FULL32_VALUE')
    return value & 0xffffffff


def signed32(word):
    need(type(word) is int and 0 <= word < (1 << 32), 'UNSIGNED32_WIRE')
    return word - (1 << 32) if word & (1 << 31) else word


@dataclass(frozen=True)
class Profile:
    n: int
    p: int
    base: int
    generation: int
    reciprocal: int
    remainder: int
    coefficient_limit: int


def profile(n, p, base, generation):
    geometry(n, p)
    need(type(generation) is int and 0 <= generation < 256, 'GENERATION8')
    bounds = carry_profile.bounds(n, p, base)
    reciprocal, remainder = divmod(1 << 96, base)
    need(0 < reciprocal < (1 << 96) and 0 <= remainder < base and
         reciprocal * base + remainder == (1 << 96), 'EXACT_SETUP_RECIPROCAL')
    return Profile(n, p, base, generation, reciprocal, remainder, bounds['A'])


def validate_profile(value):
    need(type(value) is Profile, 'TYPED_PROFILE')
    expected = profile(value.n, value.p, value.base, value.generation)
    need(value == expected, 'PROFILE_CONSTANTS')
    return geometry(value.n, value.p)


@dataclass(frozen=True)
class ColdPacket:
    profile: Profile
    context: int
    epoch: int
    # Each field is rows ascending, then physical lane ascending. Words are
    # canonical ordinary residues, NOT Montgomery encodings or lazy28 values.
    field_rows: tuple
    correction_low: tuple
    correction_high: tuple


def prepare_cold(digits, c0, c1, setup, *, context, epoch):
    g = validate_profile(setup)
    worker_numeric(setup.n)
    need(type(context) is int and context in (0, 1) and type(epoch) is int and 0 <= epoch < 65536,
         'CONTEXT1_EPOCH16')
    need(len(digits) == setup.n and len(c0) == len(c1) == setup.p, 'EXACT_IMAGE_LENGTH')
    words = tuple(wire32(d) for d in digits)
    need(all(signed32(d) == -1 or 0 <= signed32(d) < setup.base for d in words), 'DIGIT_BASE_DOMAIN')
    low, high = tuple(wire32(v) for v in c0), tuple(wire32(v) for v in c1)
    planes, lows, highs = [], [], []
    aw, lane_w = setup.n.bit_length() - 1, setup.p.bit_length() - 1
    for prime in converter.FIELDS:
        # Reuse the signed ordinary-modulo reference from the native reducer
        # suite, with the digit-specific full32/base gate above.
        converted = tuple(converter.evaluate(w, 0, setup.base, aw=aw, blocks=setup.p, p=prime)['residue'] for w in words)
        l = tuple(converter.evaluate(w, 0, setup.base, aw=aw, blocks=setup.p, p=prime) for w in low)
        h = tuple(converter.evaluate(w, 1, setup.base, aw=aw, blocks=setup.p, p=prime) for w in high)
        need(all(not x['error'] for x in l + h), 'CORRECTION_RANGE')
        need(all(type(x) is int and 0 <= x < prime for x in converted), 'DIGIT_RESIDUE_RANGE')
        planes.append(tuple(tuple(converted[arithmetic.bit_reverse(lane, lane_w) * g['t'] + row]
                                  for lane in range(setup.p)) for row in range(g['t'])))
        # Logical contiguous block order. The B binder must preserve the
        # existing correction input permutation, twist and small DFT.
        lows.append(tuple(x['residue'] for x in l))
        highs.append(tuple(x['residue'] for x in h))
    return ColdPacket(setup, context, epoch, tuple(planes), tuple(lows), tuple(highs))


def validate_cold(packet):
    need(type(packet) is ColdPacket, 'TYPED_COLD_PACKET')
    g = validate_profile(packet.profile)
    need(type(packet.context) is int and packet.context in (0, 1) and
         type(packet.epoch) is int and 0 <= packet.epoch < 65536, 'PACKET_OWNER')
    need(len(packet.field_rows) == len(packet.correction_low) == len(packet.correction_high) == 3,
         'THREE_FIELDS')
    for field, prime in enumerate(converter.FIELDS):
        rows = packet.field_rows[field]
        need(len(rows) == g['t'] and all(len(row) == packet.profile.p for row in rows), 'ROW_LAYOUT')
        values = tuple(x for row in rows for x in row) + tuple(packet.correction_low[field]) + tuple(packet.correction_high[field])
        need(len(packet.correction_low[field]) == len(packet.correction_high[field]) == packet.profile.p and
             all(type(x) is int and 0 <= x < prime for x in values), 'CANONICAL27_NO_TRIM')
    return packet


def cold_payload_bytes(packet):
    """Numeric payload only, not implemented host framing or a core ABI."""
    validate_cold(packet)
    worker_numeric(packet.profile.n)
    words = [x for field in packet.field_rows for row in field for x in row]
    words += [x for field in packet.correction_low for x in field]
    words += [x for field in packet.correction_high for x in field]
    return b''.join(word.to_bytes(4, 'little') for word in words)


def profile_payload_bytes(value):
    validate_profile(value)
    words = [value.base, value.generation]
    for constant in (value.reciprocal, value.coefficient_limit):
        words += [(constant >> (32 * limb)) & 0xffffffff for limb in range(3)]
    return b''.join(word.to_bytes(4, 'little') for word in words)


@dataclass(frozen=True)
class FinalPacket:
    profile: Profile
    context: int
    owner: int
    digits: tuple
    c0: tuple
    c1: tuple


def decode_final_payload(raw, setup, *, context, owner):
    """Core row-major natural carry lanes -> host block-major math image."""
    g = validate_profile(setup)
    worker_numeric(setup.n)
    need(type(raw) is bytes and len(raw) == 4 * (setup.n + 2 * setup.p), 'FINAL_WIRE_BYTE_LENGTH')
    words = [int.from_bytes(raw[j:j + 4], 'little') for j in range(0, len(raw), 4)]
    digits = [0] * setup.n
    for row in range(g['t']):
        for lane in range(setup.p):
            digits[lane * g['t'] + row] = words[row * setup.p + lane]
    return FinalPacket(setup, context, owner, tuple(digits),
                       tuple(signed32(w) for w in words[setup.n:setup.n + setup.p]),
                       tuple(signed32(w) for w in words[setup.n + setup.p:]))


def finalize(packet, *, expected_context, expected_owner):
    need(type(packet) is FinalPacket, 'TYPED_FINAL_PACKET')
    setup = packet.profile
    g = validate_profile(setup)
    worker_numeric(setup.n)
    need(type(packet.context) is int and packet.context in (0, 1) and
         type(expected_context) is int and expected_context == packet.context,
         'FINAL_CONTEXT')
    need(type(packet.owner) is int and 0 <= packet.owner < (1 << 56) and
         type(expected_owner) is int and packet.owner == expected_owner and
         (packet.owner & 255) == setup.generation, 'FULL56_FINAL_OWNER')
    need(len(packet.digits) == setup.n and len(packet.c0) == len(packet.c1) == setup.p,
         'FINAL_EXACT_LENGTH')
    need(all(type(d) is int and 0 <= d < setup.base for d in packet.digits), 'FINAL_DIGIT_RANGE')
    need(all(type(v) is int and abs(v) <= setup.base - 1 for v in packet.c0) and
         all(type(v) is int and abs(v) <= g['k'] for v in packet.c1), 'FINAL_CORRECTION_RANGE')
    if setup.n <= 256:
        return canonical.canonicalize(packet.digits, packet.c0, packet.c1, setup.base)
    # Size-only extension of the exact reference carry/fold loop. It remains
    # worker-only and explicitly does not establish a B-core native equivalence.
    info = canonical.proof(setup.n.bit_length() - 1, setup.p, setup.base)
    image, carry, ends = list(packet.digits), 0, []
    for phase in range(3):
        for j in range(setup.n):
            value = image[j] + carry
            if phase == 0:
                block, row = divmod(j, g['t'])
                value += packet.c0[block] if row == 0 else packet.c1[block] if row == 1 else 0
            carry, image[j] = canonical.fold(value, setup.base)
            need(abs(carry) <= (2 if phase == 0 else 1), 'FINAL_FOLD_INDUCTION')
        ends.append(carry)
        if phase < 2:
            carry = -carry
    special = ends[-1] != 0
    if special:
        need((ends[-1] == 1 and all(d == 0 for d in image)) or
             (ends[-1] == -1 and all(d == setup.base - 1 for d in image)), 'FINAL_SPECIAL_IMAGE')
        image = [-1] + [0] * (setup.n - 1)
    return canonical.CanonicalResult(tuple(image), tuple(ends), special,
                                     info['special_begin_to_done'] if special else info['normal_begin_to_done'])
