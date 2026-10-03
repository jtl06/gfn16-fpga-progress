"""R15 private transaction model; no vendor IP, CDC or core-bank implementation claim.

Physical routes and grants are supplied by the core integration, never inferred
from context id. Payload storage below is a test witness for the destination
RAM, NOT an N-sized ingress staging buffer. Only a bounded transport deque is
owned by this endpoint. All methods execute in the core-domain event model.
"""
from collections import deque
from dataclasses import dataclass
from enum import IntEnum
import struct

from .stream27_host_offload_model_v1 import Profile, validate_profile

ABI_VERSION = 1
PAYLOAD_FORMAT = 'raw32-natural-digits-c0-c1-v1'
MMIO = {"ID": 0x00, "ABI": 0x04, "SESSION": 0x08, "STATUS": 0x0C,
        "CONTEXT": 0x10, "OWNER_LO": 0x14, "OWNER_HI": 0x18,
        "PROFILE": 0x20, "COMMAND": 0x40, "ACCEPTED": 0x44,
        "APPLIED": 0x48, "ERROR": 0x4C}
DATA_RECORD_MAGIC = 0x52315000
DATA_RECORD_BYTES = 32


class Op(IntEnum):
    BEGIN = 1
    COMMIT = 2
    CANCEL = 3


class LinkFault(ValueError):
    pass


def need(ok, reason):
    if not ok:
        raise LinkFault(reason)


@dataclass(frozen=True)
class Target:
    bank: str
    port: str
    address: int


@dataclass(frozen=True)
class Word:
    session: int
    lease: int
    context: int
    owner: int
    index: int
    value: int


def encode_word(word):
    """Transport record, not a DMA hardware descriptor. Eight LE DWORDs.

    Explicit tokens prevent a late old transfer being retagged with the new
    BEGIN's authority. Host DMA descriptor format belongs to the generated IP.
    """
    need(type(word) is Word, 'WORD_TYPE')
    need(type(word.context) is int and word.context in (0, 1), 'CONTEXT')
    need(type(word.owner) is int and 0 <= word.owner < 1 << 56, 'OWNER56')
    for value in (word.session, word.lease, word.index, word.value):
        need(type(value) is int and 0 <= value < 1 << 32, 'WIRE32')
    return struct.pack('<8I', DATA_RECORD_MAGIC | word.context, word.session,
                       word.lease, word.owner & 0xffffffff, word.owner >> 32,
                       word.index, word.value, 0)


def decode_word(raw):
    need(type(raw) is bytes and len(raw) == DATA_RECORD_BYTES, 'RECORD_LENGTH')
    tag,session,lease,lo,hi,index,value,reserved=struct.unpack('<8I',raw)
    need(tag in (DATA_RECORD_MAGIC,DATA_RECORD_MAGIC|1) and hi < 1 << 24 and
         reserved == 0, 'RECORD_FORMAT')
    return Word(session,lease,tag & 1,lo | (hi << 32),index,value)


def raw_word_ok(n, base, index, word):
    need(type(index) is int and 0 <= index < n + 32, "INDEX")
    need(type(word) is int and 0 <= word < 1 << 32, "RANGE")
    signed = word if word < 1 << 31 else word - (1 << 32)
    if index < n:
        return signed == -1 or 0 <= signed < base
    return abs(signed) <= (base-1 if index < n+16 else 2*n+384)


def field100_routes(n, context, index):
    """Actual retained shadow leaf shape, plus small correction registers.

    This describes names/address mapping only; host_fire is still the arbiter.
    No field shuffle/NTT pipeline RAM is a direct-load destination.
    """
    need(context in (0, 1) and 0 <= index < n+32, 'ROUTE_INPUT')
    if index < n:
        block, row = divmod(index, n//16)
        return Target(f'contexts[{context}].natural_blocks[{block}].image_ram', 'write', row)
    kind, lane = divmod(index-n, 16)
    return Target(f'context[{context}].correction{kind}', 'write', lane)


class DirectWrite:
    """Single in-progress transaction, two independently published contexts.

    Core must prove route injectivity and exclusivity for the entire lease.
    A grant names the exact bank/port/address. busy_ports includes *all*
    same-edge core uses, even addresses of a different context. Backpressure
    keeps the queued Word unchanged; fixed compute schedules are never stalled.
    """
    def __init__(self, n, routes, fifo_depth=4):
        need(n in (32, 256, 65536), "GEOMETRY")
        need(type(fifo_depth) is int and 1 <= fifo_depth <= 32, "FIFO_BOUND")
        self.n, self.routes, self.fifo_depth = n, routes, fifo_depth
        self.session = 0
        self.next_lease = 1
        self.queue = deque()
        self.tx = None
        self.published = {}
        self.memory = {}  # destination witness only
        self.writes = []
        self.drained = False

    @property
    def words(self):
        return self.n + 32

    def reset(self):
        # Unbounded model session: RTL finite token MUST not wrap/reuse until
        # both CDC domains and all issued writes acknowledge a drain barrier.
        self.session += 1
        self.queue.clear()
        self.tx = None
        self.published.clear()
        self.drained = False

    def drain_ack(self, session):
        need(session == self.session, "DRAIN_SESSION")
        need(not self.queue and self.tx is None, "NOT_DRAINED")
        self.drained = True

    def begin(self, context, owner, profile, *, core_idle, lease_safe):
        need(self.drained, "RESET_DRAIN")
        need(self.tx is None, "TRANSACTION_BUSY")
        need(type(context) is int and context in (0, 1), "CONTEXT")
        need(type(owner) is int and 0 <= owner < 1 << 56, "OWNER56")
        need(type(profile) is Profile and profile.n == self.n and profile.p == 16,
             "PROFILE_GEOMETRY")
        validate_profile(profile)
        need(owner & 255 == profile.generation, "OWNER_GENERATION")
        need(core_idle and lease_safe, "NO_PHYSICAL_LEASE")
        # Fail closed if integrator aliases two logical body words. A separate
        # temporal port proof is still required; this check is not that proof.
        route = tuple(self.routes(context, i) for i in range(self.words))
        need(all(type(t) is Target and t.address >= 0 for t in route), "ROUTE")
        need(len({(t.bank, t.address) for t in route}) == self.words, "ROUTE_ALIAS")
        self.published.pop(context, None)
        lease = self.next_lease
        self.next_lease += 1
        self.tx = dict(context=context, owner=owner, profile=profile, lease=lease,
                       accepted=0, applied=0, route=route, fault=None)
        return self.session, lease

    def cancel(self):
        # Already-applied data need not be erased; authority is revoked before
        # the next transfer, and a complete new load is required to publish.
        if self.tx:
            self.published.pop(self.tx['context'], None)
        self.tx = None
        self.queue.clear()

    def accept(self, word):
        t = self.tx
        need(t is not None and t['fault'] is None, "NO_TRANSACTION")
        need(type(word) is Word, "WORD_TYPE")
        try:
            need((word.session, word.lease, word.context, word.owner) ==
                 (self.session, t['lease'], t['context'], t['owner']), "STALE_AUTHORITY")
            need(word.index == t['accepted'], "ORDER")
            need(raw_word_ok(self.n, t['profile'].base, word.index, word.value), "RANGE")
        except LinkFault as exc:
            t['fault'] = str(exc)
            self.queue.clear()
            raise
        if len(self.queue) == self.fifo_depth:
            return False  # transport retains valid and identical payload
        self.queue.append(word)
        t['accepted'] += 1
        return True

    def step(self, *, grant=None, busy_ports=frozenset(), context_still_idle=True):
        t = self.tx
        if t is None or t['fault'] or not self.queue:
            return None
        if not context_still_idle:
            t['fault'] = 'LEASE_REVOKED'
            self.queue.clear()
            return None
        word = self.queue[0]
        target = t['route'][word.index]
        if grant != (self.session, t['lease'], target) or (target.bank, target.port) in busy_ports:
            return None
        # This edge is the destination RAM write ACK, not merely CDC dequeue.
        self.memory[(target.bank, target.address)] = word.value
        self.writes.append((word, target))
        self.queue.popleft()
        t['applied'] += 1
        return word

    def commit(self, *, session, lease, context, owner, core_idle, profile_ok):
        t = self.tx
        need(t is not None and t['fault'] is None, "NO_TRANSACTION")
        need((session, lease, context, owner) ==
             (self.session, t['lease'], t['context'], t['owner']), "STALE_COMMIT")
        need(core_idle and profile_ok, "COMMIT_AUTHORITY")
        need(t['accepted'] == t['applied'] == self.words and not self.queue,
             "PARTIAL_OR_UNACKNOWLEDGED")
        self.published[context] = (owner, t['profile'], lease, self.session)
        self.tx = None
        return self.published[context]


class FixedOutput:
    """Lossless external queue while capacity lasts; overflow is typed abort.

    Fixed-calendar core cannot be backpressured. A tiny FIFO does not prove
    arbitrary PCIe stall tolerance. After overflow, no successful publication
    is possible; caller must cancel/rollback. Checkpoint buffering or a maximum
    service-gap proof is required separately for successful uninterrupted work.
    """
    def __init__(self, depth):
        need(type(depth) is int and depth > 0, "OUTPUT_DEPTH")
        self.depth, self.queue, self.error = depth, deque(), False

    def tick(self, payload=None, ready=False):
        delivered = self.queue.popleft() if ready and self.queue else None
        if payload is not None and not self.error:
            if len(self.queue) == self.depth:
                self.error = True
            else:
                self.queue.append(payload)
        return delivered
