from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fpga.host.r15_arithmetic import Checkpoint, HostFault, SoftwareBackend
from fpga.host.r15_checkpoint_store import CheckpointStore, VerifiedSession


class CheckpointStorage(unittest.TestCase):
    def store(self, directory):
        return CheckpointStore(str(Path(directory).resolve()), source='small-fixture',
                               owner=1, context=0, enabled=True)

    def initial(self):
        return Checkpoint(600, 32, 1, 0, 0, 7, 'small-fixture')

    def test_off_and_restart_identity(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(HostFault, 'OFF'):
                CheckpointStore(d, source='small-fixture', owner=1, context=0)
            store = self.store(d)
            cp = self.initial()
            store.commit(cp)
            self.assertEqual(store.load(), cp)
            self.assertEqual(store.path.stat().st_mode & 0o777, 0o600)
            wrong = CheckpointStore(str(Path(d).resolve()), source='wrong',
                                    owner=1, context=0, enabled=True)
            with self.assertRaisesRegex(HostFault, 'IDENTITY'):
                wrong.load()

    def test_pre_replace_error_keeps_old_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as d:
            store = self.store(d)
            cp = self.initial()
            store.commit(cp)
            with patch('fpga.host.r15_checkpoint_store.os.replace', side_effect=OSError('interrupted')):
                with self.assertRaises(OSError):
                    store.commit(replace(cp, completed=4, value=8))
            self.assertEqual(store.load(), cp)
            self.assertEqual(tuple(Path(d).resolve().iterdir()), (store.path,))

    def test_truncation_corruption_and_symlink_refuse(self):
        with tempfile.TemporaryDirectory() as d:
            store = self.store(d)
            cp = self.initial()
            raw = cp.encode()
            for broken in (raw[:-1], raw.replace(b'0x7', b'0x8')):
                store.path.write_bytes(broken)
                with self.assertRaises(HostFault):
                    store.load()
            store.path.unlink()
            other = Path(d) / 'other'
            other.write_bytes(raw)
            store.path.symlink_to(other)
            with self.assertRaises(OSError):
                store.load()

    def test_no_regression_or_cross_profile_commit(self):
        with tempfile.TemporaryDirectory() as d:
            store = self.store(d)
            cp = replace(self.initial(), completed=8)
            store.commit(cp)
            for wrong in (replace(cp, completed=7), replace(cp, value=8), replace(cp, base=599),
                          replace(cp, source='other')):
                with self.assertRaises(HostFault):
                    store.commit(wrong)
            self.assertEqual(store.load(), cp)

    def test_corrupt_window_rewinds_residue_and_descriptor_position(self):
        with tempfile.TemporaryDirectory() as d:
            store = self.store(d)
            cp = self.initial()
            store.commit(cp)
            backend = SoftwareBackend(600, 32, enabled=True)
            session = VerifiedSession(backend, store, enabled=True)
            bits = [True, False, True, True] * 4
            def corrupt(b, index):
                if index == 3:
                    b.load((b.read() + 1) % b.modulus)
            self.assertFalse(session.window(bits, 4, inject=corrupt))
            self.assertEqual((backend.read(), backend.steps), (7, 0))
            self.assertEqual(store.load(), cp)
            self.assertTrue(session.window(bits, 4))
            wanted = SoftwareBackend(600, 32, enabled=True)
            wanted.load(7)
            for bit in bits:
                wanted.step(bit)
            self.assertEqual((backend.read(), backend.steps), (wanted.read(), 16))
            restarted = VerifiedSession(SoftwareBackend(600, 32, enabled=True), store, enabled=True)
            self.assertEqual((restarted.backend.read(), restarted.backend.steps),
                             (wanted.read(), 16))

    def test_execution_exception_never_leaves_partial_software_state(self):
        with tempfile.TemporaryDirectory() as d:
            store = self.store(d)
            cp = self.initial()
            store.commit(cp)
            session = VerifiedSession(SoftwareBackend(600, 32, enabled=True), store, enabled=True)
            def stop(b, index):
                if index == 3:
                    raise RuntimeError('simulated software interruption')
            with self.assertRaisesRegex(RuntimeError, 'interruption'):
                session.window([True, False, True, True] * 4, 4, inject=stop)
            self.assertEqual((session.backend.read(), session.backend.steps), (cp.value, cp.completed))
            self.assertEqual(store.load(), cp)


if __name__ == '__main__':
    unittest.main()
