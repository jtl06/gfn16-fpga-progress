# SPDX-License-Identifier: Apache-2.0
"""Default-OFF application-window START and final canonical A fence planner.

Uses the PCIe owner's additive logical register semantics; no device access or
vendor BAR/DMA assignment. Snapshots/committed records must be supplied by the
future coherent ACK decoder, not unowned independent register polling.
"""
from dataclasses import dataclass

from .r15_arithmetic import need
from .r15_image_codec import (Publication, CanonicalCollector, ExportWord, CANONICAL_A)
from fpga.reference.stream27_r15_host_mmio_v1 import Header, CMD_START, register_writes
from fpga.reference.stream27_r15_shell_mmio_v1 import REG, STATUS_BITS, ERROR_BITS


@dataclass(frozen=True)
class CommittedRecord:
    session: int
    lease: int
    header: Header


@dataclass(frozen=True)
class ShellSnapshot:
    session: int
    latest_begin_lease: int
    status: int
    error: int
    committed: tuple
    coherent_command_ack: bool


@dataclass(frozen=True)
class OwnedCanonicalWord:
    session: int
    word: ExportWord


def _flag(snapshot, name):
    return bool(snapshot.status & (1 << STATUS_BITS[name]))


def _snapshot(snapshot):
    need(type(snapshot) is ShellSnapshot and snapshot.coherent_command_ack is True and
         type(snapshot.session) is int and 0 <= snapshot.session < 1 << 32 and
         type(snapshot.latest_begin_lease) is int and 0 <= snapshot.latest_begin_lease < 1 << 32,
         'SHELL_COHERENT_SESSION_LEASE')
    need(type(snapshot.status) is int and 0 <= snapshot.status < 1 << len(STATUS_BITS) and
         type(snapshot.error) is int and 0 <= snapshot.error < 1 << len(ERROR_BITS) and
         snapshot.error == 0 and _flag(snapshot, 'LINK_READY') and
         not _flag(snapshot, 'LOCAL_ERROR') and not _flag(snapshot, 'CORE_ERROR') and
         not _flag(snapshot, 'COMMAND_PENDING'), 'SHELL_HEALTHY_FINAL_FENCE')
    need(type(snapshot.committed) is tuple, 'SHELL_COMMITTED_ROSTER')
    records = {}
    for record in snapshot.committed:
        need(type(record) is CommittedRecord and type(record.header) is Header and
             type(record.session) is int and
             record.session == snapshot.session and type(record.lease) is int and
             0 <= record.lease < 1 << 32 and record.header.context not in records,
             'SHELL_OWNED_COMMITTED_RECORD')
        register_writes(record.header, session=record.session)  # full header revalidation
        records[record.header.context] = record
    return records


def start_writes(snapshot, expected_records, *, enabled=False):
    need(enabled is True, 'SHELL_START_ADAPTER_OFF')
    actual = _snapshot(snapshot)
    need(type(expected_records) is tuple and 1 <= len(expected_records) <= 2 and
         _flag(snapshot, 'IDLE0') and _flag(snapshot, 'IDLE1'), 'START_BOTH_CONTEXTS_IDLE')
    mask = 0
    for record in expected_records:
        need(type(record) is CommittedRecord and type(record.header) is Header and
             actual.get(record.header.context) == record and
             not mask & (1 << record.header.context) and
             _flag(snapshot, 'LOADED'+str(record.header.context)), 'START_EXACT_COMMITTED_READY')
        mask |= 1 << record.header.context
    # Current global lease can differ from the older context's own cold lease.
    # Explicitly echo the latest coherent BEGIN lease; never silently retag data.
    return ((REG['TOKEN_SESSION'], snapshot.session),
            (REG['TOKEN_LEASE'], snapshot.latest_begin_lease),
            (REG['START_MASK'], mask), (REG['COMMAND'], CMD_START))


class FencedCanonicalExport:
    def __init__(self, record, initial_snapshot, *, enabled=False):
        need(enabled is True, 'SHELL_EXPORT_ADAPTER_OFF')
        self.record = record
        self.failed = False
        self._fence(initial_snapshot)
        h = record.header
        self.collector = CanonicalCollector(Publication(h.n, h.base, h.context,
                                                       h.owner, h.count, True), enabled=True)

    def _fence(self, snapshot):
        actual = _snapshot(snapshot)
        need(type(self.record) is CommittedRecord and type(self.record.header) is Header and
             actual.get(self.record.header.context) == self.record and
             _flag(snapshot, 'IDLE'+str(self.record.header.context)) and
             _flag(snapshot, 'CANONICAL'+str(self.record.header.context)) and
             not _flag(snapshot, 'EXPORT_PENDING'), 'EXACT_COMPLETED_CANONICAL_FENCE')

    def accept(self, framed):
        need(not self.failed, 'SHELL_EXPORT_POISONED')
        self.failed = True
        need(type(framed) is OwnedCanonicalWord and type(framed.word) is ExportWord and
             type(framed.session) is int and
             framed.session == self.record.session and framed.word.format == CANONICAL_A,
             'OWNED_CANONICAL_SESSION_FORMAT')
        self.collector.accept(framed.word)
        self.failed = False

    def finish(self, final_snapshot):
        need(not self.failed, 'SHELL_EXPORT_POISONED')
        self.failed = True
        self._fence(final_snapshot)  # recheck actual final error/owner/publication status
        image = self.collector.finish()
        self.failed = False
        return image
