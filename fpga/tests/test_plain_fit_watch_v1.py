import importlib.util
from pathlib import Path
import tempfile
import unittest

P = Path(__file__).resolve().parents[1] / 'tools/plain_fit_watch_v1.py'
S = importlib.util.spec_from_file_location('fit_watch_test', P)
M = importlib.util.module_from_spec(S); S.loader.exec_module(M)


class WatchTests(unittest.TestCase):
    def test_auth_blocked_unchanged_metadata_makes_zero_calls(self):
        calls = []
        gate = M.AuthLatch('old')
        for _ in range(100):
            self.assertFalse(gate.ready('old', lambda: calls.append(1), lambda: 'old'))
        self.assertEqual(calls, [])

    def test_login_metadata_change_checks_once_and_failure_latches(self):
        calls = []
        gate = M.AuthLatch('old')
        def rejected():
            calls.append(1); return False, 'ExpiredToken'
        self.assertFalse(gate.ready('new', rejected, lambda: 'new'))
        self.assertFalse(gate.ready('new', rejected, lambda: 'new'))
        self.assertEqual(calls, [1])

    def test_success_then_native_auth_failure_requires_new_login(self):
        gate = M.AuthLatch('old')
        self.assertTrue(gate.ready('new', lambda: (True, 'normal_session_verified'), lambda: 'new'))
        gate.auth_failure('new')
        self.assertFalse(gate.ready('new', lambda: self.fail('must not retry'), lambda: 'new'))
        self.assertTrue(gate.ready('newer', lambda: (True, 'normal_session_verified'), lambda: 'newer'))

    def test_stat_only_metadata_changes_without_reading_contents(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = M.metadata(root)
            (root/'config').touch()
            self.assertNotEqual(before, M.metadata(root))

    def test_original_bound_and_journal_claim_replay(self):
        controller, queue = M.load_controller()
        self.assertEqual(controller.validate_queue(queue), M.END)
        original = (M.STATE/'events.jsonl').read_bytes()
        journal = controller.Journal(M.STATE, controller.digest(controller.canonical(queue)))
        claim = journal.current()['anext-writeback-9668']
        self.assertEqual(claim['invocation_id'], M.INVOCATION)
        self.assertEqual(claim['request_sha256'], M.REQUEST_SHA)
        self.assertEqual(claim['phase'], 'started')
        self.assertEqual(sum(row['event']=='launch_attempt' for row in journal.rows), 1)
        self.assertEqual((M.STATE/'events.jsonl').read_bytes(), original)

    def test_existing_controller_lock_excludes_second_owner(self):
        controller, _ = M.load_controller()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            with controller.controller_lock(directory):
                with self.assertRaises(BlockingIOError):
                    with controller.controller_lock(directory):
                        self.fail('second owner acquired exact flock')


if __name__ == '__main__':
    unittest.main()
