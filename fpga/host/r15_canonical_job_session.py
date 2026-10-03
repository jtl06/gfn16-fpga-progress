# SPDX-License-Identifier: Apache-2.0
"""Small default-OFF software contract for end-of-job canonical A checking.

No R15 RTL, MMIO, DMA, or native GL coupling is executed here. Each arithmetic
job is ONE equal-width GL block; A supplies its end state and the next cold
start. Host GL accumulates products across several such jobs, then verifies
the window. Arbitrary interior checkpoints are NOT assumed. A shorter final
job starts a new verified window, never pads real descriptors with fake zeros.
Two contexts have independent verified checkpoints/GLOBAL PRP ordinals.
"""
from dataclasses import dataclass

from .r15_arithmetic import SoftwareBackend, need, verify_window
from .r15_genefer_proof import digits
from .r15_image_codec import CanonicalImage, load_software_backend
from .r15_link_adapter import CoreSnapshot, TransactionPlan
from .r15_transport import cold_words


@dataclass(frozen=True)
class GlobalCheckpoint:
    context: int
    ordinal: int
    value: int
    last_job_owner: int | None
    source: str


@dataclass(frozen=True)
class ChunkPlan:
    session: int
    context: int
    global_begin: int
    bits: tuple
    transaction: TransactionPlan
    cold_digits: tuple
    raw_cold_words: tuple


class CanonicalJobSession:
    def __init__(self, n, base, *, source, transport_session, width, verify_every,
                 initial_values=(1, 1), enabled=False, engine='python'):
        need(enabled is True, 'CANONICAL_JOB_SESSION_OFF')
        need(type(n) is int and n in (32, 256), 'SESSION_SMALL_MODEL_ONLY')
        need(type(width) is int and 1 <= width <= 65536 and type(verify_every) is int and
             1 <= verify_every <= 255 and type(transport_session) is int and
             0 <= transport_session < 1 << 32 and type(source) is str and source,
             'SESSION_EXPLICIT_CONTRACT')
        self.n, self.base, self.source = n, base, source
        self.session, self.width, self.verify_every = transport_session, width, verify_every
        self.checker = SoftwareBackend(base, n, enabled=True, engine=engine)
        need(type(initial_values) is tuple and len(initial_values) == 2 and
             all(type(v) is int and 0 <= v < self.checker.modulus for v in initial_values),
             'TWO_INDEPENDENT_INITIAL_RESIDUES')
        self.verified = [GlobalCheckpoint(c, 0, initial_values[c], None, source) for c in (0, 1)]
        self.current_value = list(initial_values)
        self.ordinal = [0, 0]
        self.generation = [0, 0]
        self.pending = [[], []]
        self.active = [None, None]
        self.cold_ack = [False, False]
        self.recovery_required = False
        self.reload_required = {0, 1}
        self.accounting = dict(jobs=0, descriptors=0, raw_cold_words=0,
            canonical_words=0, profile_setups=0, host_GL_checks=0, common_resets=0,
            backend_seconds=None, transport_seconds=None, host_GL_seconds=None,
            includes_extra_cold_canonical_profile_work=True,
            inherits_old_compute_projection=False, native_GL_coupling=False)

    def checkpoint(self, context):
        need(type(context) is int and context in (0, 1), 'CONTEXT')
        return self.verified[context]

    def plan(self, context, snapshot, bits):
        need(not self.recovery_required, 'COMMON_RESET_DRAIN_RELOAD_REQUIRED')
        self.checkpoint(context)
        need(self.active[context] is None and type(bits) is tuple and
             1 <= len(bits) <= self.width and all(type(bit) is bool for bit in bits),
             'ONE_ACTIVE_JOB_TYPED_BITS')
        need(type(snapshot) is CoreSnapshot and snapshot.context == context and
             snapshot.session == self.session and
             snapshot.prospective_generation == self.generation[context] + 1,
             'EXACT_COHERENT_SESSION_GENERATION')
        # Equal-width blocks are needed for the GL product identity. Flush a
        # partial group before a shorter terminal block, without extra squares.
        need(not self.pending[context] or len(bits) == len(self.pending[context][0]['bits']),
             'FLUSH_BEFORE_WIDTH_CHANGE')
        mode = 3 | (4 if bits[0] else 0)  # batch/feed/first-double; rest are FIFO descriptors
        transaction = TransactionPlan(self.n, self.base, len(bits), mode, 0, snapshot,
                                      enabled=True)
        image = tuple(digits(self.current_value[context], self.base, self.n))
        raw = cold_words(self.n, self.base, image, [0]*16, [0]*16)
        plan = ChunkPlan(self.session, context, self.ordinal[context], bits, transaction, image, raw)
        self.active[context] = plan
        self.cold_ack[context] = False
        return plan

    def _active(self, plan):
        need(type(plan) is ChunkPlan and plan.session == self.session and
             plan.context in (0, 1) and self.active[plan.context] is plan,
             'CURRENT_OWNED_JOB_ONLY')
        return plan.context

    def acknowledge_cold(self, plan, *, lease, accepted, applied, coherent_idle_ack,
                         retained_profile_ready):
        c = self._active(plan)
        plan.transaction.commit_plan(lease, accepted=accepted, applied=applied,
                                     coherent_idle_ack=coherent_idle_ack)
        need(retained_profile_ready is True, 'COMMIT_NOT_PROFILE_READY')
        # This is an injected software acknowledgment, NOT proof of a real
        # destination bank grant, MMIO response, profile engine, or START.
        self.cold_ack[c] = True
        self.reload_required.discard(c)

    def accept_canonical(self, plan, image, *, response_session):
        c = self._active(plan)
        need(not self.recovery_required and self.cold_ack[c], 'OWNED_ACK_BEFORE_EXPORT')
        h = plan.transaction.header
        try:
            need(type(response_session) is int and response_session == self.session,
                 'CURRENT_EXPORT_SESSION')
            need(type(image) is CanonicalImage and image.publication.context == c and
                 image.publication.owner == h.owner and image.publication.completed == h.count,
                 'EXACT_PER_JOB_OWNER_NOT_GLOBAL_ORDINAL')
            value = load_software_backend(image, self.checker)
        except BaseException:
            self.recovery_required = True
            raise
        self.pending[c].append(dict(start=self.current_value[c], end=value, bits=plan.bits,
                                    owner=h.owner))
        self.current_value[c] = value
        self.ordinal[c] += len(plan.bits)
        self.generation[c] = h.generation
        self.active[c] = None
        self.cold_ack[c] = False
        self.accounting['jobs'] += 1
        self.accounting['descriptors'] += len(plan.bits)
        self.accounting['raw_cold_words'] += self.n + 32
        self.accounting['canonical_words'] += self.n
        self.accounting['profile_setups'] += 1
        if len(self.pending[c]) >= self.verify_every:
            return self.flush(c)
        return None  # provisional, never a verified checkpoint/proof publication

    def flush(self, context):
        self.checkpoint(context)
        need(not self.recovery_required and self.active[context] is None,
             'VERIFY_IDLE_CURRENT_SESSION')
        blocks = self.pending[context]
        if not blocks:
            return True
        width = len(blocks[0]['bits'])
        product, chunk_sum = 1, 0
        for block in blocks:
            product = (product * block['start']) % self.checker.modulus
            chunk = 0
            for bit in block['bits']:
                chunk = 2*chunk + int(bit)
            chunk_sum += chunk
        self.accounting['host_GL_checks'] += 1
        good = verify_window(self.checker, self.verified[context].value,
                             self.current_value[context], product, chunk_sum, width)
        if not good:
            self.recovery_required = True
            # Last independently verified state of BOTH contexts is retained.
            # Core payload is not magically rolled back: common reset, drain,
            # and each context's full cold reload are required before retry.
            return False
        self.verified[context] = GlobalCheckpoint(context, self.ordinal[context],
            self.current_value[context], blocks[-1]['owner'], self.source)
        self.pending[context] = []
        return True

    def acknowledge_common_reset(self, new_session, *, core_reset_ack, both_domains_drained):
        need(core_reset_ack is True and both_domains_drained is True and
             type(new_session) is int and self.session < new_session < 1 << 32,
             'COMMON_RESET_AND_BOTH_DOMAIN_DRAIN')
        self.session = new_session
        self.pending, self.active, self.cold_ack = [[], []], [None, None], [False, False]
        self.generation = [0, 0]
        self.ordinal = [cp.ordinal for cp in self.verified]
        self.current_value = [cp.value for cp in self.verified]
        self.reload_required = {0, 1}
        self.recovery_required = False
        self.accounting['common_resets'] += 1

    def proof_checkpoint(self, context, global_ordinal):
        cp = self.checkpoint(context)
        need(type(global_ordinal) is int and global_ordinal == cp.ordinal,
             'NO_UNEXPORTED_INTERMEDIATE_PROOF_CHECKPOINT')
        return cp


def window_counts(total_operations, width=65536):
    """Integer-only full-size planning; no full-N numeric or timing claim."""
    need(type(total_operations) is int and 1 <= total_operations < 1 << 32 and
         type(width) is int and 1 <= width < 1 << 32, 'WINDOW_COUNT32')
    full, tail = divmod(total_operations, width)
    need(full + bool(tail) <= 255, 'WINDOW_PLAN_NEEDS_EXPLICIT_RESET_POLICY')
    return (width,) * full + ((tail,) if tail else ())
