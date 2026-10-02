import importlib.util
from pathlib import Path
from types import SimpleNamespace
import subprocess
import unittest
from unittest.mock import patch

P = Path(__file__).resolve().parents[1] / 'tools/plain_fit_watch_v2.py'
S = importlib.util.spec_from_file_location('fit_watch_v2_test', P)
M = importlib.util.module_from_spec(S); S.loader.exec_module(M)


class WatchTests(unittest.TestCase):
    def test_transient_then_success_without_metadata_change(self):
        gate = M.AuthLatch('old'); calls = []
        def check():
            calls.append(1)
            return (False, 'normal_sts_unresolved_no_tick') if len(calls)==1 else (True, 'normal_session_verified')
        self.assertFalse(gate.ready('new', check, lambda:'new', now=0))
        self.assertFalse(gate.blocked)
        self.assertFalse(gate.ready('new', check, lambda:'new', now=59))
        self.assertTrue(gate.ready('new', check, lambda:'new', now=60))
        self.assertEqual(len(calls), 2); self.assertEqual(gate.failures, 0)

    def test_expired_unchanged_metadata_never_retries(self):
        gate = M.AuthLatch('old'); calls = []
        def check(): calls.append(1); return False, 'ExpiredToken'
        self.assertFalse(gate.ready('new', check, lambda:'new', now=0))
        for at in (1, 60, 300, 100000):
            self.assertFalse(gate.ready('new', check, lambda:'new', now=at))
        self.assertEqual(calls, [1]); self.assertTrue(gate.blocked)

    def test_backoff_is_60_120_240_then_capped_300(self):
        gate = M.AuthLatch('old'); at = 0
        for delay in (60, 120, 240, 300, 300):
            self.assertFalse(gate.ready('new', lambda:(False,'normal_sts_failed_no_tick'), lambda:'new', now=at))
            self.assertEqual(gate.retry_at-at, delay); at=gate.retry_at

    def test_explicit_denials_and_wrong_account_latch(self):
        for reason in ('explicit_auth_denial_no_tick', 'account_mismatch_no_tick'):
            gate = M.AuthLatch('old')
            self.assertFalse(gate.ready('new', lambda:(False,reason), lambda:'new', now=0))
            self.assertFalse(gate.ready('new', lambda:self.fail('no retry'), lambda:'new', now=10000))
            self.assertTrue(gate.ready('newer', lambda:(True,'normal_session_verified'), lambda:'newer', now=10001))

    def test_check_auth_classifies_timeout_forbidden_expired_and_success(self):
        fixtures = [(254,'ExpiredToken',(False,'ExpiredToken')),
                    (254,'Forbidden',(False,'explicit_auth_denial_no_tick')),
                    (255,'Could not connect to endpoint',(False,'normal_sts_failed_no_tick')),
                    (0,'',(True,'normal_session_verified'))]
        for code, error, expected in fixtures:
            with patch.object(M.subprocess,'run',return_value=SimpleNamespace(returncode=code,stderr=error,stdout='{"Account":"201636920512"}')):
                self.assertEqual(M.check_auth(),expected)
        with patch.object(M.subprocess,'run',side_effect=subprocess.TimeoutExpired('aws',25)):
            self.assertEqual(M.check_auth(),(False,'normal_sts_unresolved_no_tick'))
        with patch.object(M.subprocess,'run',return_value=SimpleNamespace(returncode=0,stderr='',stdout='{"Account":"wrong"}')):
            self.assertEqual(M.check_auth(),(False,'account_mismatch_no_tick'))

    def test_restore_v1_stranded_transient_is_retryable_not_authenticated(self):
        gate = M.restore_latch({'status':'auth_blocked','reason':'normal_sts_unresolved_no_tick','credential_metadata_sha256':'same'})
        self.assertFalse(gate.blocked)
        self.assertFalse(gate.ready('same',lambda:(False,'ExpiredToken'),lambda:'same',now=0))
        self.assertTrue(gate.blocked)

    def test_native_auth_denial_remains_latched(self):
        gate=M.AuthLatch('same',blocked=False); gate.auth_failure('same')
        self.assertFalse(gate.ready('same',lambda:self.fail('no retry'),lambda:'same',now=1000))

    def test_frozen_base_cutoff_and_exact_original_claim_unchanged(self):
        controller,queue=M.B.load_controller()
        self.assertEqual(controller.validate_queue(queue), M.B.END)
        raw=(M.B.STATE/'events.jsonl').read_bytes()
        journal=controller.Journal(M.B.STATE,controller.digest(controller.canonical(queue)))
        claim=journal.current()['anext-writeback-9668']
        self.assertEqual(claim['invocation_id'],M.B.INVOCATION)
        self.assertEqual(claim['request_sha256'],M.B.REQUEST_SHA)
        self.assertEqual(sum(row['event']=='launch_attempt' for row in journal.rows),1)
        self.assertEqual((M.B.STATE/'events.jsonl').read_bytes(),raw)


if __name__ == '__main__':
    unittest.main()
