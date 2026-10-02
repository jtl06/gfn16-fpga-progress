"""T5 source-only edge-contract model, NOT an RTL simulation or qualification.

E0 actual carry commit, E3 reducer output, E4 registered host boundary,
E5 three-field NTT write, E6 completion/registered-host-error observation.
The model deliberately uses event timestamps rather than copying RTL shifts.
"""
from dataclasses import dataclass, field


class PrefillFault(ValueError):
    """Typed protocol failure used by source-only negative tests."""


@dataclass
class Prefill:
    aw: int
    base: int
    time: int = 0
    issued: int = 0
    written: int = 0
    carry_success: bool = False
    eligible: bool = False
    failed: bool = False
    busy: bool = True
    check_at: int | None = None
    tokens: list = field(default_factory=list)
    writes: list = field(default_factory=list)

    def __post_init__(self):
        if not 1 <= self.aw <= 16 or not 2*(1 << self.aw)+4 < self.base <= 10**9:
            raise ValueError("unsupported profile")

    @property
    def n(self): return 1 << self.aw

    @property
    def step(self): return min(self.n, 16)

    @property
    def mask(self): return (1 << self.step)-1

    def fault(self, kind):
        self.failed = True
        self.eligible = False
        self.busy = False
        self.tokens.clear()
        raise PrefillFault(kind)

    def reset(self):
        self.eligible = False
        self.busy = False
        self.failed = False
        self.tokens.clear()
        self.check_at = None
        self.issued = self.written = 0
        self.carry_success = False

    def load(self):
        if not self.busy: self.eligible = False

    def start(self, base, coherent=True):
        if self.busy or self.failed: raise PrefillFault("T5_START_NOT_IDLE")
        fast = self.eligible and base == self.base and coherent
        self.base = base
        self.eligible = False
        self.busy = True
        self.issued = self.written = 0
        self.carry_success = False
        self.check_at = None
        return fast

    def edge(self, emit=None, carry_done=False, host_error=False, coherent=True,
             field_masks=None, address_delta=0, drop_write=False):
        """emit is (logical address, active mask, signed canonical words)."""
        if self.failed: raise PrefillFault("T5_FAILED_REQUIRES_RESET")
        if host_error or not coherent: self.fault("T5_LATE_HOST_OR_PROFILE_ERROR")
        if self.check_at == self.time:
            if self.tokens or not self.carry_success or self.issued != self.n or self.written != self.n:
                self.fault("T5_INCOMPLETE_IMAGE")
            self.eligible = True
            self.busy = False
        if emit is not None:
            address, mask, words = emit
            if address != self.issued or self.issued >= self.n:
                self.fault("T5_EMIT_ADDRESS")
            if mask != self.mask or len(words) != self.step:
                self.fault("T5_EMIT_MASK")
            if any(x != -1 and not 0 <= x < self.base for x in words):
                self.fault("T5_EMIT_DIGIT")
            self.tokens.append((self.time+5, address, mask, tuple(words)))
            self.issued += self.step
        if carry_done:
            if self.issued != self.n: self.fault("T5_EMIT_COUNT")
            self.carry_success = True
        due = [x for x in self.tokens if x[0] == self.time]
        self.tokens = [x for x in self.tokens if x[0] != self.time]
        for _, address, mask, words in due:
            if field_masks is not None and tuple(field_masks) != (mask,)*3:
                self.fault("T5_FIELD_MASK")
            if address+address_delta != self.written:
                self.fault("T5_WRITE_ADDRESS")
            if not drop_write:
                self.writes.append((self.time, address, tuple(tuple(x % p for x in words)
                    for p in (104857601, 69206017, 67239937))))
                self.written += self.step
                if self.written == self.n: self.check_at = self.time+1
        if self.carry_success and not self.tokens and self.written != self.n:
            self.fault("T5_WRITE_COUNT")
        self.time += 1


def native_gate_plan():
    return {
        "status": "source_proposal_not_executed",
        "parent": "rootfused_crtmont_AW5_AW16_qualified_normal",
        "normal": ["AW5 frozen 568 operations/561 readbacks", "AW16 frozen 12 operations/10 readbacks"],
        "required_extra": ["same-base square/double chains", "changed-base fallback", "LOAD_KEEP fallback",
                           "readback does not invalidate", "special -1", "busy host/base poisoning"],
        "tail_events": ["E0 actual final carry commit", "E1 carry done", "E2", "E3 reducer output",
                        "E4 boundary", "E5 final NTT write", "E6 eligibility check"],
        "fault_matrix": ["reset each E0..E6", "registered host error each E0..E6"],
        "mutants": ["forced eligibility after load", "boundary address +16", "one field lane mask",
                    "missing final write count", "ignore base tag", "ignore late host error"],
        "negative_rule": "typed monitor failure with separate freshly passing source control; data mismatch alone insufficient",
        "observations": "selective read-only SV wrapper outputs; no public-flat-rw; actual RAM write enable/address/mask checks",
        "resources": "inherit fixed source-hash bootstrap and bounded tmpfs/cgroup/CPU/model-thread guards; no dispatch yet",
        "claims": "No measured cycle, resource, timing, hardware, or reset qualification",
    }
