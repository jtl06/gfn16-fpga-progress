"""R15 software backend and Gerbicz-Li windows, OFF unless explicitly enabled.

Original implementation. The product identity generalizes the pinned
genefer22 Gerbicz-Li relation to a non-unit starting checkpoint. Exact modular
equality is checked rather than genefer's 64-bit hash comparison. This is
software-backend evidence, not board, fault-immunity, or full-PRP evidence.
"""
from dataclasses import dataclass, asdict
import hashlib
import json
import platform


class HostFault(ValueError):
    pass


def need(condition, tag):
    if not condition:
        raise HostFault('R15_HOST_' + tag)


@dataclass(frozen=True)
class Features:
    software_backend: bool = False
    gerbicz_li: bool = False
    proof_codec: bool = False
    vfio: bool = False
    boinc_wrapper: bool = False


class SoftwareBackend:
    """One scalar context; GMP is explicit and never silently falls back."""
    def __init__(self, base, n, *, enabled=False, engine='python'):
        need(enabled is True, 'SOFTWARE_BACKEND_OFF')
        need(type(base) is int and 2 <= base <= 1000000000 and
             type(n) is int and n >= 2 and n & (n-1) == 0, 'GEOMETRY')
        need(n <= 256 or platform.system() == 'Linux', 'FULL_NUMERIC_LINUX_ONLY')
        need(engine in ('python', 'gmp'), 'ENGINE')
        if engine == 'gmp':
            import gmpy2
            self._integer = gmpy2.mpz
            self._pow = gmpy2.powmod
            self.runtime = dict(engine='gmpy2', version=gmpy2.version(),
                                gmp=gmpy2.mp_version())
        else:
            need(n <= 256, 'PYTHON_SMALL_ONLY')
            self._integer, self._pow = int, pow
            self.runtime = dict(engine='python-small-reference')
        self.base, self.n = base, n
        self.modulus = self._integer(base)**n + 1
        self.value = self._integer(1)
        self.steps = 0

    def load(self, value):
        need(type(value) is int and 0 <= value < self.modulus, 'RESIDUE')
        self.value = self._integer(value)

    def step(self, double):
        need(type(double) is bool, 'DESCRIPTOR_BOOL')
        self.value = (self.value*self.value*(2 if double else 1)) % self.modulus
        self.steps += 1

    def read(self):
        return int(self.value)

    def power(self, value, exponent):
        return int(self._pow(self._integer(value), self._integer(exponent), self.modulus))


@dataclass(frozen=True)
class Checkpoint:
    base: int
    n: int
    owner: int
    context: int
    completed: int
    value: int
    source: str

    def encode(self):
        value = asdict(self)
        value['value_hex'] = hex(value.pop('value'))
        payload = json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
        return b'R15CP1\n' + hashlib.sha256(payload).hexdigest().encode() + b'\n' + payload

    @classmethod
    def decode(cls, raw, *, expected_source, expected_owner, expected_context):
        need(type(raw) is bytes and len(raw) <= 4*1024*1024, 'CHECKPOINT_BOUND')
        try:
            magic, digest, payload = raw.split(b'\n', 2)
            need(magic == b'R15CP1' and digest == hashlib.sha256(payload).hexdigest().encode(),
                 'CHECKPOINT_DIGEST')
            value = json.loads(payload)
            need(set(value) == (set(cls.__dataclass_fields__)-{'value'})|{'value_hex'},
                 'CHECKPOINT_KEYS')
            need(type(value['value_hex']) is str and value['value_hex'].startswith('0x'),
                 'CHECKPOINT_HEX')
            value['value'] = int(value.pop('value_hex'), 16)
            result = cls(**value)
        except (ValueError, TypeError, UnicodeError) as exc:
            raise HostFault('R15_HOST_CHECKPOINT_ENCODING') from exc
        need(result.source == expected_source and result.owner == expected_owner and
             result.context == expected_context, 'CHECKPOINT_IDENTITY')
        need(type(result.owner) is int and 0 <= result.owner < 1 << 56 and
             type(result.context) is int and result.context in (0, 1) and
             type(result.completed) is int and result.completed >= 0, 'CHECKPOINT_OWNER')
        need(type(result.base) is int and 2 <= result.base <= 1000000000 and
             type(result.n) is int and 2 <= result.n <= 65536 and result.n & (result.n-1) == 0,
             'CHECKPOINT_GEOMETRY')
        need(result.n <= 256 or platform.system() == 'Linux', 'FULL_NUMERIC_LINUX_ONLY')
        # Bound before exponentiation; digest is accidental-corruption
        # detection, not authentication against an adversarial host.
        need(type(result.value) is int and 0 <= result.value < result.base**result.n+1,
             'CHECKPOINT_RESIDUE')
        return result


def verify_window(backend, start, end, product, chunk_sum, width):
    """D*x_end = x_start*D^(2^B)*2^sum(block exponents), modulo M."""
    m = backend.modulus
    return (product*end) % m == (start*backend.power(product, 1 << width)*
                                 backend.power(2, chunk_sum)) % m


def run_verified_window(backend, bits, width, checkpoint, *, enabled=False, inject=None):
    need(enabled is True, 'GERBICZ_LI_OFF')
    need(type(width) is int and 1 <= width <= 4096 and bits and len(bits) % width == 0 and
         all(type(bit) is bool for bit in bits), 'GL_WINDOW')
    need((checkpoint.base, checkpoint.n) == (backend.base, backend.n), 'GL_PROFILE')
    backend.load(checkpoint.value)
    start, product, chunk_sum = checkpoint.value, 1, 0
    for block in range(len(bits)//width):
        product = (product*backend.read()) % backend.modulus
        chunk = 0
        for offset, bit in enumerate(bits[block*width:(block+1)*width]):
            chunk = 2*chunk + int(bit)
            backend.step(bit)
            if inject is not None:
                inject(backend, block*width+offset)
        chunk_sum += chunk
    if not verify_window(backend, start, backend.read(), product, chunk_sum, width):
        # Restore the last validated residue, never publish a bad result.
        backend.load(checkpoint.value)
        return None
    return Checkpoint(checkpoint.base, checkpoint.n, checkpoint.owner, checkpoint.context,
                      checkpoint.completed+len(bits), backend.read(), checkpoint.source)


def genefer_trace(backend, exponent, width):
    """Exact pinned genefer22 PRP d(t) boundary schedule; software only."""
    need(type(exponent) is int and exponent > 0 and type(width) is int and width > 0,
         'EXPONENT')
    backend.load(1)
    product = 1
    checkpoints = {}
    for i in range(exponent.bit_length()-1, -1, -1):
        backend.step(bool((exponent >> i) & 1))
        checkpoints[i] = backend.read()
        if i % width == 0 and i // width != 0:
            product = (product*backend.read()) % backend.modulus
    chunks, remaining = 0, exponent
    while remaining:
        chunks += remaining & ((1 << width)-1)
        remaining >>= width
    valid = (product*backend.read()) % backend.modulus == (
        backend.power(product, 1 << width)*backend.power(2, chunks)) % backend.modulus
    return backend.read(), product, valid, checkpoints
