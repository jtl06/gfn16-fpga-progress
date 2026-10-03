"""Pinned genefer22 d5060c61 Pietrzak-Li/gint/file-compatible prototype.

Arithmetic/codec translated from Yves Gallot's MIT-licensed genefer22.
Copyright (c) 2022 Yves Gallot; original Python adaptation (c) 2026.
The accompanying THIRD-PARTY-NOTICES preserves the MIT notice. Only the
non-CYCLO little-endian int32 ABI is supported. Codec tests alone are not
full upstream-CLI interoperability, primality, or deployed proof evidence.
"""
import struct
import zlib

from .r15_arithmetic import HostFault, need

PINNED_COMMIT = 'd5060c61090942f42a908492628eba13ebd7cd82'
MASK64 = (1 << 64)-1


def digits(value, base, n):
    need(type(base) is int and 2 <= base <= 1000000000 and type(n) is int and
         2 <= n <= 65536 and n & (n-1) == 0, 'PROOF_GEOMETRY')
    need(type(value) is int and 0 <= value <= base**n, 'PROOF_RESIDUE')
    if value == base**n:
        return (-1,) + (0,)*(n-1)
    result = []
    for _ in range(n):
        value, word = divmod(value, base)
        result.append(word)
    return tuple(result)


def hash64(words):
    need(any(words), 'GENEFER_HASH_ZERO')
    result = 0
    for digit in words:
        a = digit & 0xffffffff
        result = (result+a) & MASK64
        x, r = (a+0xc39d8a0552b073e8) & MASK64, (17*a+5) % 64
        result ^= ((x << r) | (x >> ((-r) & 63))) & MASK64
    return result


def challenge(words):
    value = hash64(words)
    return max(2, (value & 0xffffffff) ^ (value >> 32))


def encode_proof(base, n, mus, *, enabled=False):
    need(enabled is True, 'PROOF_CODEC_OFF')
    need(type(mus) in (tuple, list) and 2 <= len(mus) <= 21, 'PROOF_DEPTH')
    depth = len(mus)-1
    body = bytearray(struct.pack('<ii', 1, depth))
    for value in mus:
        words = digits(value, base, n)
        body.extend(struct.pack('<II', n, base))
        body.extend(struct.pack('<'+'i'*n, *words))
    crc = (~zlib.crc32(body) ^ 0xa23777ac) & 0xffffffff
    return bytes(body)+struct.pack('<I', crc)


def decode_proof(raw, base, n, *, enabled=False):
    need(enabled is True, 'PROOF_CODEC_OFF')
    need(type(raw) is bytes and len(raw) >= 12, 'PROOF_LENGTH')
    version, depth = struct.unpack_from('<ii', raw)
    need(version == 1 and 1 <= depth <= 20, 'PROOF_VERSION_DEPTH')
    need(len(raw) == 12+(depth+1)*(8+4*n), 'PROOF_EXACT_LENGTH')
    need(struct.unpack_from('<I', raw, len(raw)-4)[0] ==
         ((~zlib.crc32(raw[:-4]) ^ 0xa23777ac) & 0xffffffff), 'PROOF_CRC')
    values = []
    offset = 8
    for _ in range(depth+1):
        size, radix = struct.unpack_from('<II', raw, offset)
        need((size, radix) == (n, base), 'PROOF_PROFILE')
        words = struct.unpack_from('<'+'i'*n, raw, offset+8)
        special = words == (-1,)+(0,)*(n-1)
        need(special or all(0 <= word < base for word in words), 'PROOF_CANONICAL')
        value = base**n if special else sum(word*base**i for i, word in enumerate(words))
        values.append(value)
        offset += 8+4*n
    return tuple(values)


def generate_proof(backend, exponent, depth, *, enabled=False):
    need(enabled is True and type(depth) is int and 1 <= depth <= 12 and
         type(exponent) is int and exponent > 0, 'PROOF_GENERATOR_OFF_OR_INPUT')
    width = ((exponent.bit_length()-1) >> depth)+1
    length = 1 << depth
    backend.load(1)
    checkpoints = {}
    for i in range(exponent.bit_length()-1, -1, -1):
        backend.step(bool((exponent >> i) & 1))
        if i % width == 0:
            checkpoints[i//width] = backend.read()
    need(all(i in checkpoints for i in range(length)), 'PROOF_DEPTH_UNPOPULATED')
    mu0 = checkpoints[0]
    weights = [0]*(length//2)
    weights[0] = challenge(digits(mu0, backend.base, backend.n))
    mus = [mu0]
    for k in range(1, depth+1):
        i = 1 << (depth-k)
        value = backend.power(checkpoints[i], weights[0])
        for j in range(i, length//2, i):
            value = (value*backend.power(checkpoints[i+2*j], weights[j])) % backend.modulus
        # GMP modular reduction returns mpz. Normalize only this trusted
        # arithmetic result before the exact-int codec boundary; digits()
        # must still reject foreign integer objects, bools and bad ranges.
        value = int(value)
        mus.append(value)
        q = challenge(digits(value, backend.base, backend.n))
        if i > 1:
            for j in range(0, length//2, i):
                weights[i//2+j] = weights[j]*q
    return encode_proof(backend.base, backend.n, mus, enabled=True)


def verify_proof(backend, exponent, raw, *, enabled=False):
    """Deterministic pre-certificate Pietrzak-Li relation (no BOINC server)."""
    mus = decode_proof(raw, backend.base, backend.n, enabled=enabled)
    depth, length = len(mus)-1, 1 << (len(mus)-1)
    width = ((exponent.bit_length()-1) >> depth)+1
    weights = [0]*length
    weights[0] = challenge(digits(mus[0], backend.base, backend.n))
    v1, v2 = backend.power(mus[0], weights[0]), 1
    for k in range(1, depth+1):
        q = challenge(digits(mus[k], backend.base, backend.n))
        v1 = v1*backend.power(mus[k], q) % backend.modulus
        v2 = backend.power(v2, q)*mus[k] % backend.modulus
        i = 1 << (depth-k)
        for j in range(0, length, 2*i):
            weights[i+j] = weights[j]*q
    weighted, remaining = 0, exponent
    for w in weights:
        weighted += (remaining & ((1 << width)-1))*w
        remaining >>= width
    need(remaining == 0, 'PROOF_EXPONENT_COVERAGE')
    return v1 == backend.power(v2, 1 << width)*backend.power(2, weighted) % backend.modulus
