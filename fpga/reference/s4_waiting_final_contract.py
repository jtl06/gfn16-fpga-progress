"""Proposed two-context shadow reuse transaction contract; NOT RTL timing.

Each context has one N-word shadow. Dense P-word raw rows are in natural
block order, not field butterfly order. One shared canonical scratch first
loads the entire raw image, then returns N ordered scalar words into that
same context's shadow. Only a completed copy may publish it to the host.

This models ownership, storage and phase exclusion only. Arithmetic, RAM
latency, same-edge arbitration and canonical cycle counts are NOT qualified.
Caller supplies already-normalized words from its independent arithmetic
reference. Cancellation cannot reclaim storage until an external drain fence.
Never-reused full tags model the finite-tag reuse obligation, not its RTL.
This is only the busy waiting-final lifecycle, not cold partial host loading.
Transaction methods represent accepted transfers; RTL must separately qualify
synchronous response tokens, arbitration and publication-edge ordering.
Context cancel is a controller request, NOT proof of context-local fault
recovery: a shared child fault aborts both contexts via abort_all().
"""
from dataclasses import dataclass


class ContractError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise ContractError(code)


@dataclass(frozen=True)
class Owner:
    context: int
    generation: int
    epoch: int
    ordinal: int


class WaitingFinal:
    def __init__(self, n=32, p=8):
        require(n in (32, 256) and p in (8, 16), 'SMALL_CONTRACT_GEOMETRY')
        self.n, self.p, self.rows = n, p, n // p
        self.memory = [[None] * n for _ in range(2)]
        self.slots = [None, None]
        self.scratch = None
        self.used_tags = set()
        self.reset_fenced = False

    def begin(self, owner, base, c0, c1):
        require(isinstance(owner, Owner), 'OWNER_TYPE')
        require(owner.context in (0, 1), 'CONTEXT')
        require(0 <= owner.generation < 256 and 0 <= owner.epoch < 65536
                and 0 <= owner.ordinal < 2**32, 'TAG_WIDTH')
        require(not self.reset_fenced, 'RESET_DRAIN_REQUIRED')
        require(self.slots[owner.context] is None, 'CONTEXT_BUSY')
        require(owner not in self.used_tags, 'TAG_REUSE_REQUIRES_PROOF')
        require(1 < base <= 10**9, 'BASE')
        c0, c1 = tuple(c0), tuple(c1)
        require(len(c0) == self.p and len(c1) == self.p, 'CORRECTION_WIDTH')
        require(all(-2**31 <= x < 2**31 for x in c0 + c1), 'SIGNED32')
        self.used_tags.add(owner)
        self.slots[owner.context] = dict(owner=owner, base=base, c0=c0, c1=c1,
                                        phase='capture', rows=0, loaded=0, copied=0)

    def slot(self, owner, phase):
        require(isinstance(owner, Owner) and owner.context in (0, 1), 'CONTEXT')
        slot = self.slots[owner.context]
        require(slot is not None and slot['owner'] == owner, 'STALE_OWNER')
        require(slot['phase'] == phase, 'PHASE')
        return slot

    def capture(self, owner, row, words):
        slot = self.slot(owner, 'capture')
        words = tuple(words)
        require(row == slot['rows'] and row < self.rows, 'ROW_ORDER')
        require(len(words) == self.p, 'ROW_WIDTH')
        require(all(0 <= x < slot['base'] for x in words), 'RAW_DIGIT_RANGE')
        for block, word in enumerate(words):
            self.memory[owner.context][block * self.rows + row] = word
        slot['rows'] += 1
        if slot['rows'] == self.rows:
            slot['phase'] = 'waiting'

    def acquire_scratch(self, owner):
        slot = self.slot(owner, 'waiting')
        require(self.scratch is None, 'SCRATCH_BUSY')
        self.scratch = owner
        slot['phase'] = 'load'
        return slot['base'], slot['c0'], slot['c1']

    def load_row(self, owner, row):
        slot = self.slot(owner, 'load')
        require(self.scratch == owner, 'SCRATCH_OWNER')
        require(row == slot['loaded'] and row < self.rows, 'LOAD_ORDER')
        words = tuple(self.memory[owner.context][b * self.rows + row]
                      for b in range(self.p))
        slot['loaded'] += 1
        if slot['loaded'] == self.rows:
            slot['phase'] = 'normalize'
        return words

    def canonical_ready(self, owner):
        slot = self.slot(owner, 'normalize')
        require(self.scratch == owner, 'SCRATCH_OWNER')
        slot['phase'] = 'copy'

    def commit(self, owner, address, word):
        slot = self.slot(owner, 'copy')
        require(self.scratch == owner, 'SCRATCH_OWNER')
        require(address == slot['copied'] and address < self.n, 'COPY_ORDER')
        require(-2**31 <= word < 2**31, 'SIGNED32')
        self.memory[owner.context][address] = word
        slot['copied'] += 1

    def publish(self, owner):
        slot = self.slot(owner, 'copy')
        require(self.scratch == owner and slot['copied'] == self.n,
                'INCOMPLETE_PUBLICATION')
        slot['phase'] = 'published'
        self.scratch = None

    def host_read(self, owner, address):
        self.slot(owner, 'published')
        require(0 <= address < self.n, 'ADDRESS')
        return self.memory[owner.context][address]

    def release(self, owner):
        self.slot(owner, 'published')
        self.slots[owner.context] = None

    def cancel(self, owner):
        require(isinstance(owner, Owner) and owner.context in (0, 1), 'CONTEXT')
        slot = self.slots[owner.context]
        require(slot is not None and slot['owner'] == owner, 'STALE_OWNER')
        slot['phase'] = 'quarantine'
        # Do not release shared scratch or the bank before physical tails drain.

    def drained(self, owner):
        self.slot(owner, 'quarantine')
        if self.scratch == owner:
            self.scratch = None
        self.slots[owner.context] = None

    def reset(self):
        # Retain payload RAM, revoke eligibility, and require a global fence.
        self.slots = [None, None]
        self.scratch = None
        self.reset_fenced = True

    def reset_drained(self):
        require(self.reset_fenced, 'NO_RESET_FENCE')
        self.reset_fenced = False

    def abort_all(self):
        """Shared fault scope: revoke both contexts and await physical drain."""
        self.reset()
