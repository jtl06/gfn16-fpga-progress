from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from fpga.host.r15_arithmetic import HostFault, SoftwareBackend
from fpga.host.r15_canonical_job_session import CanonicalJobSession
from fpga.host.r15_checkpoint_store import CheckpointStore
from fpga.host.r15_end_a_window_controller import EndAWindowController, StartAck
from fpga.host.r15_genefer_proof import digits
from fpga.host.r15_image_codec import ExportWord, CANONICAL_A, encode_signed96
from fpga.host.r15_link_adapter import CoreSnapshot
from fpga.host.r15_shell_adapter import CommittedRecord, OwnedCanonicalWord, ShellSnapshot
from fpga.reference.stream27_r15_shell_mmio_v1 import STATUS_BITS


def status(*names):
    return sum(1 << STATUS_BITS[name] for name in names)


class Controller(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='r15-end-a-test-')
        self.root = Path(self.tmp.name)
        for context in (0, 1):
            (self.root / str(context)).mkdir()
        self.stores = tuple(CheckpointStore(self.root / str(c), source='fixture',
            owner=42, context=c, enabled=True) for c in (0, 1))
        self.session = self.fresh_session()
        self.controller = EndAWindowController(self.session, self.stores, enabled=True)

    def tearDown(self):
        self.tmp.cleanup()

    def fresh_session(self):
        return CanonicalJobSession(256, 600, source='fixture', transport_session=7,
            width=4, verify_every=2, initial_values=(1, 7), enabled=True)

    def plan(self, context=0, bits=(True, False, True, True)):
        s = self.session
        return s.plan(context, CoreSnapshot(s.session, context, 65534,
                      s.generation[context] + 1, True), bits)

    def commit(self, plan, *, applied=288):
        record = CommittedRecord(plan.session, 8, plan.transaction.header)
        snap = ShellSnapshot(plan.session, 9,
            status('LINK_READY', 'IDLE0', 'IDLE1', 'LOADED'+str(plan.context)),
            0, (record,), True)
        writes = self.controller.cold_commit(plan, record, snap, accepted=288,
                                             applied=applied)
        return record, snap, writes

    def job(self, context=0, *, bits=(True, False, True, True), corrupt=False,
            final_error=False):
        plan = self.plan(context, bits)
        record, _, writes = self.commit(plan)
        self.assertEqual(writes[1][1], 9)  # newest global BEGIN lease, not cold lease8
        self.controller.start_ack(plan, StartAck(plan.session, 9, 1 << context, True, True,
            1 << context, plan.transaction.header.generation << (8*context)))
        final = ShellSnapshot(plan.session, 9,
            status('LINK_READY', 'IDLE0', 'IDLE1', 'CANONICAL'+str(context)),
            0, (record,), True)
        self.controller.begin_export(plan, final)
        backend = SoftwareBackend(self.session.base, 256, enabled=True)
        backend.load(self.session.current_value[context])
        for bit in plan.bits:
            backend.step(bit)
        value = (backend.read() + int(corrupt)) % backend.modulus
        for index, word in enumerate(digits(value, self.session.base, 256)):
            self.controller.accept_word(plan, OwnedCanonicalWord(plan.session,
                ExportWord(CANONICAL_A, context, record.header.owner, index,
                           encode_signed96(word))))
        if final_error:
            final = replace(final, error=1)
        return self.controller.finish(plan, final)

    def test_only_verified_state_persists_and_restart_restores_global_position(self):
        self.assertIsNone(self.job())
        self.assertEqual(self.stores[0].load().completed, 0)
        self.assertTrue(self.job())
        cp = self.stores[0].load()
        self.assertEqual(cp.completed, 8)
        self.assertEqual(cp.value, pow(2, 0b10111011, 600**256+1))
        restarted = self.fresh_session()
        restarting_controller = EndAWindowController(restarted, self.stores, enabled=True)
        self.assertEqual((restarted.ordinal, restarted.current_value),
                         ([8, 0], [cp.value, 7]))
        self.assertTrue(restarted.recovery_required)
        with self.assertRaisesRegex(HostFault, 'RESET'):
            restarted.plan(0, CoreSnapshot(7, 0, 0, 1, True), (False,))
        restarting_controller.reset_ack(8, core_reset_ack=True, both_domains_drained=True)
        self.assertEqual(restarted.reload_required, {0, 1})
        self.assertFalse(self.controller.accounting['actual_native_endpoint'])
        self.assertIsNone(self.controller.accounting['transport_seconds'])

    def test_complete_small_PRP_programs_through_fenced_adapter_equal_independent_pow(self):
        for base in (599, 600):
            directories = tuple(self.root / f'{base}-{c}' for c in (0, 1))
            for directory in directories:
                directory.mkdir()
            self.stores = tuple(CheckpointStore(directory, source='fixture',
                owner=42, context=c, enabled=True) for c, directory in enumerate(directories))
            self.session = CanonicalJobSession(256, base, source='fixture',
                transport_session=7, width=64, verify_every=4, enabled=True)
            self.controller = EndAWindowController(self.session, self.stores, enabled=True)
            exponent = base**256
            bits = tuple(bit == '1' for bit in bin(exponent)[2:])
            for first in range(0, len(bits), 64):
                block = bits[first:first+64]
                if len(block) != 64:
                    self.assertTrue(self.controller.flush(0))
                self.job(bits=block)
            self.assertTrue(self.controller.flush(0))
            cp = self.stores[0].load()
            self.assertEqual((cp.completed, cp.value),
                (len(bits), pow(2, exponent, exponent+1)))
            self.assertEqual(self.session.accounting['descriptors'], len(bits))
            self.assertEqual(self.session.accounting['raw_cold_words'],
                self.session.accounting['jobs']*288)
            self.assertFalse(self.controller.accounting['actual_device'])

    def test_bad_GL_restores_both_independent_files_and_counts_peer_loss(self):
        for c in (0, 1):
            self.job(c)
            self.assertTrue(self.job(c))
        safe = tuple(s.load() for s in self.stores)
        self.job(1)
        self.job(0)
        self.assertFalse(self.job(0, corrupt=True))
        self.assertEqual(tuple(s.load() for s in self.stores), safe)
        with self.assertRaisesRegex(HostFault, 'DRAIN'):
            self.controller.reset_ack(8, core_reset_ack=True, both_domains_drained=False)
        self.controller.reset_ack(8, core_reset_ack=True, both_domains_drained=True)
        self.assertEqual(self.session.ordinal, [8, 8])
        self.assertEqual(self.session.current_value, [c.value for c in safe])
        self.assertEqual(self.session.reload_required, {0, 1})
        self.assertEqual(self.controller.accounting['discarded_provisional_operations'], 12)

    def test_partial_load_stale_START_and_missing_START_poison_without_checkpoint(self):
        plan = self.plan()
        with self.assertRaisesRegex(HostFault, 'ACK'):
            self.commit(plan, applied=287)
        self.assertTrue(self.session.recovery_required)
        self.controller.reset_ack(8, core_reset_ack=True, both_domains_drained=True)
        plan = self.plan()
        record, snap, _ = self.commit(plan)
        with self.assertRaisesRegex(HostFault, 'START_BEFORE'):
            self.controller.begin_export(plan, snap)
        self.controller.reset_ack(9, core_reset_ack=True, both_domains_drained=True)
        plan = self.plan()
        self.commit(plan)
        with self.assertRaisesRegex(HostFault, 'START_ACK'):
            self.controller.start_ack(plan, StartAck(9, 8, 1, True, True, 1, 1))
        self.assertEqual(self.stores[0].load().completed, 0)

    def test_final_error_after_complete_words_cannot_publish_safe_checkpoint(self):
        self.job()
        with self.assertRaisesRegex(HostFault, 'FENCE'):
            self.job(final_error=True)
        self.assertTrue(self.session.recovery_required)
        self.assertEqual(self.stores[0].load().completed, 0)
        self.controller.reset_ack(8, core_reset_ack=True, both_domains_drained=True)
        self.assertEqual(self.session.ordinal, [0, 0])

    def test_default_off_and_source_bound_restore(self):
        with self.assertRaisesRegex(HostFault, 'OFF'):
            EndAWindowController(self.fresh_session(), self.stores)
        mismatched = self.fresh_session()
        mismatched.source = 'wrong-source'
        with self.assertRaisesRegex(HostFault, 'IDENTITY'):
            EndAWindowController(mismatched, self.stores, enabled=True)

    def test_raw_COMMIT_is_not_START_and_ACK_requires_busy_generation(self):
        plan = self.plan()
        record, snap, _ = self.commit(plan)
        self.assertFalse(self.session.cold_ack[0])
        with self.assertRaisesRegex(HostFault, 'START_ACK'):
            self.controller.start_ack(plan, StartAck(7, 9, 1, True, True, 0, 1))
        self.controller.reset_ack(8, core_reset_ack=True, both_domains_drained=True)
        plan = self.plan()
        record, _, _ = self.commit(plan)
        with self.assertRaisesRegex(HostFault, 'START_ACK'):
            self.controller.start_ack(plan, StartAck(8, 9, 1, True, True, 1, 2))
        self.assertFalse(self.session.cold_ack[0])


if __name__ == '__main__':
    unittest.main()
