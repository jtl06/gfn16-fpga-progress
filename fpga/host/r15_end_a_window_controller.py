# SPDX-License-Identifier: Apache-2.0
"""Default-OFF host controller for the end-job canonical A contract.

This plans/validates application actions; it never accesses a device. Real
BEGIN/COMMIT/START acknowledgments, framed words, and common-reset/drain ACKs
must come from an adapter. The current executable session is small N32/N256.
No in-job checkpoint, native endpoint, CDC, or board equivalence is claimed.
"""
from dataclasses import dataclass

from .r15_arithmetic import Checkpoint, need
from .r15_canonical_job_session import CanonicalJobSession, GlobalCheckpoint
from .r15_checkpoint_store import CheckpointStore
from .r15_shell_adapter import CommittedRecord, FencedCanonicalExport, start_writes


@dataclass(frozen=True)
class StartAck:
    session: int
    latest_begin_lease: int
    mask: int
    coherent_command_ack: bool
    accepted: bool
    busy_mask: int
    job_generations: int


class EndAWindowController:
    def __init__(self, session, stores, *, enabled=False):
        need(enabled is True, 'END_A_CONTROLLER_OFF')
        need(type(session) is CanonicalJobSession and type(stores) is tuple and
             len(stores) == 2 and all(type(s) is CheckpointStore for s in stores),
             'END_A_TWO_CHECKPOINT_STORES')
        self.session, self.stores = session, stores
        self.jobs = {}
        self.accounting = dict(checkpoint_writes=0, discarded_provisional_operations=0,
                              aborted_active_jobs=0, hardware_reset_delivery_bound=False,
                              actual_native_endpoint=False, actual_device=False,
                              host_seconds=None, transport_seconds=None,
                              inherits_internal_compute_projection=False)
        for c, store in enumerate(stores):
            need(store.identity['expected_context'] == c and
                 store.identity['expected_source'] == session.source,
                 'END_A_CHECKPOINT_IDENTITY')
        restarted = any(s.path.exists() or s.path.is_symlink() for s in stores)
        self._restore_files(initial=True)
        # A disk checkpoint does not establish current core generation, idle,
        # session, or drained DMA state. Restart must acknowledge common reset.
        if restarted:
            self._poison()

    def _checkpoint_file(self, c):
        cp = self.session.checkpoint(c)
        # Store owner is a stable host-run identity, not a reused per-job owner.
        # Per-job owner authority remains in the committed/export record.
        return Checkpoint(self.session.base, self.session.n,
            self.stores[c].identity['expected_owner'], c, cp.ordinal, cp.value,
            self.session.source)

    def _restore_files(self, *, initial=False):
        for c, store in enumerate(self.stores):
            if initial and not store.path.exists() and not store.path.is_symlink():
                store.commit(self._checkpoint_file(c))
            cp = store.load()
            need((cp.base, cp.n) == (self.session.base, self.session.n),
                 'END_A_RESTART_PROFILE')
            self.session.verified[c] = GlobalCheckpoint(c, cp.completed, cp.value,
                                                        None, cp.source)
            self.session.current_value[c] = cp.value
            self.session.ordinal[c] = cp.completed

    def _poison(self):
        self.session.recovery_required = True

    def abort(self, reason):
        """Transport/link/command exceptions revoke the entire host session."""
        need(type(reason) is str and reason, 'END_A_EXPLICIT_ABORT_REASON')
        self._poison()

    def cold_commit(self, plan, record, coherent_snapshot, *, accepted, applied):
        """Return START writes, only after exact raw ACK and BOTH-idle fence."""
        try:
            self.session._active(plan)
            need(not self.session.recovery_required and
                 type(record) is CommittedRecord and record.session == plan.session and
                 record.header == plan.transaction.header, 'END_A_EXACT_COLD_RECORD')
            writes = start_writes(coherent_snapshot, (record,), enabled=True)
            need(coherent_snapshot.session == plan.session, 'END_A_COLD_SESSION')
            plan.transaction.commit_plan(record.lease, accepted=accepted,
                                          applied=applied, coherent_idle_ack=True)
            self.jobs[plan.context] = dict(plan=plan, record=record,
                global_lease=coherent_snapshot.latest_begin_lease, started=False,
                accepted=accepted, applied=applied, collector=None)
            return writes
        except BaseException:
            self._poison()
            raise

    def start_ack(self, plan, ack):
        try:
            job = self.jobs.get(plan.context)
            need(not self.session.recovery_required and job and job['plan'] is plan and
                 not job['started'] and type(ack) is StartAck and
                 ack.coherent_command_ack is True and ack.accepted is True and
                 type(ack.session) is int and ack.session == plan.session and
                 type(ack.latest_begin_lease) is int and
                 ack.latest_begin_lease == job['global_lease'] and
                 type(ack.mask) is int and ack.mask == 1 << plan.context and
                 type(ack.busy_mask) is int and 0 <= ack.busy_mask < 4 and
                 ack.busy_mask & ack.mask == ack.mask and
                 type(ack.job_generations) is int and 0 <= ack.job_generations < 1 << 16 and
                 ((ack.job_generations >> (8*plan.context)) & 255) ==
                    plan.transaction.header.generation,
                 'END_A_ACTUAL_START_ACK')
            job['started'] = True
        except BaseException:
            self._poison()
            raise

    def begin_export(self, plan, coherent_final_snapshot):
        try:
            job = self.jobs.get(plan.context)
            need(not self.session.recovery_required and job and job['plan'] is plan and
                 job['started'] and job['collector'] is None,
                 'END_A_START_BEFORE_EXPORT')
            job['collector'] = FencedCanonicalExport(job['record'], coherent_final_snapshot,
                                                     enabled=True)
        except BaseException:
            self._poison()
            raise

    def accept_word(self, plan, framed):
        try:
            job = self.jobs.get(plan.context)
            need(not self.session.recovery_required and job and job['plan'] is plan and
                 job['collector'] is not None, 'END_A_OWNED_EXPORT_ACTIVE')
            job['collector'].accept(framed)
        except BaseException:
            self._poison()
            raise

    def finish(self, plan, coherent_final_snapshot):
        try:
            job = self.jobs.get(plan.context)
            need(not self.session.recovery_required and job and job['plan'] is plan and
                 job['collector'] is not None, 'END_A_COMPLETE_EXPORT')
            image = job['collector'].finish(coherent_final_snapshot)
            # The captured retained core performs private PROFILE before its
            # source-bound canonical publication. Only that complete end-A
            # result discharges the legacy SOFTWARE model's profile gate.
            # No intermediate PROFILE ACK/register/operation_accept is claimed.
            record = job['record']
            self.session.acknowledge_cold(plan, lease=record.lease,
                accepted=job['accepted'], applied=job['applied'], coherent_idle_ack=True,
                retained_profile_ready=True)
            verified = self.session.accept_canonical(plan, image,
                                                     response_session=plan.session)
            del self.jobs[plan.context]
            if verified is True:
                self._persist(plan.context)
            return verified  # None means provisional, not safe proof/checkpoint publication.
        except BaseException:
            self._poison()
            raise

    def _persist(self, context):
        self.stores[context].commit(self._checkpoint_file(context))
        self.accounting['checkpoint_writes'] += 1

    def flush(self, context):
        try:
            good = self.session.flush(context)
            if good:
                self._persist(context)
            return good
        except BaseException:
            self._poison()
            raise

    def reset_ack(self, new_session, *, core_reset_ack, both_domains_drained):
        """Restore BOTH independent safe checkpoints after real common drain.

        The adapter must reload both contexts before resumed jobs. Reading a
        file is not restoring already-written hardware payload or a peer tail.
        """
        need(core_reset_ack is True and both_domains_drained is True,
             'END_A_ACTUAL_COMMON_RESET_DRAIN')
        persisted = tuple(store.load() for store in self.stores)
        lost = sum(max(0, self.session.ordinal[c] - persisted[c].completed) for c in (0, 1))
        active = sum(plan is not None for plan in self.session.active)
        self.session.acknowledge_common_reset(new_session, core_reset_ack=core_reset_ack,
                                               both_domains_drained=both_domains_drained)
        self._restore_files()
        self.jobs.clear()
        # Exact completed provisional operations only; in-flight work is not
        # converted to an invented operation/time estimate.
        self.accounting['discarded_provisional_operations'] += lost
        self.accounting['aborted_active_jobs'] += active
        return tuple(self.session.checkpoint(c) for c in (0, 1))
