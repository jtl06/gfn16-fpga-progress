import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from fpga.reference.paired_process_runner import run_pair


def factory(code):
    return lambda dump: [sys.executable, '-c', code, str(dump)]


WRITE = "from pathlib import Path; import sys; Path(sys.argv[1]).write_text('1 2 3\\n'); print('PASS runs=1')"


def verify(files):
    for kind in ('log', 'dump'):
        if files['baseline'][kind].read_bytes() != files['candidate'][kind].read_bytes():
            raise ValueError('exact ' + kind + ' mismatch')
    if b'PASS runs=1' not in files['baseline']['log'].read_bytes():
        raise ValueError('missing semantic completion')
    return {'exact_logs_and_dumps': True}


class PairProcessTests(unittest.TestCase):
    def test_two_processes_reach_barrier_concurrently(self):
        with tempfile.TemporaryDirectory() as tmp:
            factories = {}
            for label, peer in (('baseline', 'candidate'), ('candidate', 'baseline')):
                code = ("from pathlib import Path; import time,sys; "
                        f"Path('{label}.ready').touch(); end=time.monotonic()+3\n"
                        f"while not Path('{peer}.ready').exists():\n"
                        " if time.monotonic()>end: raise RuntimeError('peer never started')\n"
                        " time.sleep(.01)\n" + WRITE)
                factories[label] = factory(code)
            output = Path(tmp) / 'pair'
            result = run_pair(output, factories, timeout=5, guard=lambda: None, verify=verify)
            self.assertEqual(result['status'], 'passed')
            self.assertNotEqual(result['processes']['baseline']['pid'], result['processes']['candidate']['pid'])
            self.assertEqual(json.loads((output / 'receipt.json').read_text()), result)
            self.assertEqual(len(result['artifact_sha256']), 4)

    def test_nonzero_exit_fails_and_reaps_peer(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'pair'
            with self.assertRaisesRegex(RuntimeError, 'command failed'):
                run_pair(output, {'baseline': factory("raise SystemExit(9)"),
                    'candidate': factory("import time; time.sleep(30)")},
                    timeout=3, guard=lambda: None, verify=verify)
            result = json.loads((output / 'receipt.json').read_text())
            self.assertEqual(result['status'], 'failed')
            self.assertIsNone(result['verification'])
            self.assertEqual(result['processes']['baseline']['returncode'], 9)
            self.assertLess(result['processes']['candidate']['returncode'], 0)

    def test_timeout_preserves_failed_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'pair'
            with self.assertRaises(TimeoutError):
                run_pair(output, {name: factory("import time; time.sleep(30)")
                    for name in ('baseline', 'candidate')}, timeout=.1, guard=lambda: None, verify=verify)
            result = json.loads((output / 'receipt.json').read_text())
            self.assertEqual(result['status'], 'failed')
            self.assertTrue(all(row['returncode'] < 0 for row in result['processes'].values()))

    def test_second_launch_failure_reaps_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'pair'
            with self.assertRaises(FileNotFoundError):
                run_pair(output, {'baseline': factory('import time; time.sleep(30)'),
                    'candidate': lambda dump: [str(output / 'nonexistent-executable')]},
                    timeout=3, guard=lambda: None, verify=verify)
            result = json.loads((output / 'receipt.json').read_text())
            self.assertEqual(result['status'], 'failed')
            self.assertLess(result['processes']['baseline']['returncode'], 0)

    def test_explicit_fuzz_environment_is_preserved(self):
        code = "import os; assert os.environ['NTT_SKIP_HOST_FUZZ']=='1'; " + WRITE
        command = lambda dump: ['env', 'NTT_SKIP_HOST_FUZZ=1', *factory(code)(dump)]
        with tempfile.TemporaryDirectory() as tmp:
            result = run_pair(Path(tmp) / 'pair', {name: command for name in ('baseline', 'candidate')},
                              timeout=3, guard=lambda: None, verify=verify)
            self.assertEqual(result['status'], 'passed')

    def test_mismatched_outputs_never_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'pair'
            with self.assertRaisesRegex(ValueError, 'dump mismatch'):
                run_pair(output, {'baseline': factory(WRITE),
                    'candidate': factory(WRITE.replace('1 2 3', '1 2 4'))},
                    timeout=3, guard=lambda: None, verify=verify)
            self.assertEqual(json.loads((output / 'receipt.json').read_text())['status'], 'failed')

    def test_inherited_fault_and_fuzz_settings_are_removed(self):
        code = "import os; assert 'NTT_NONCANON' not in os.environ; assert 'NTT_SKIP_HOST_FUZZ' not in os.environ; " + WRITE
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {'NTT_NONCANON': 'high', 'NTT_SKIP_HOST_FUZZ': '1'}):
            result = run_pair(Path(tmp) / 'pair', {name: factory(code)
                for name in ('baseline', 'candidate')}, timeout=3, guard=lambda: None, verify=verify)
            self.assertEqual(result['status'], 'passed')

    def test_guard_failure_during_poll_reaps_both(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'pair'
            guard = mock.Mock(side_effect=[None, None, None, RuntimeError('disk guard')])
            with self.assertRaisesRegex(RuntimeError, 'disk guard'):
                run_pair(output, {name: factory("import time; time.sleep(30)")
                    for name in ('baseline', 'candidate')}, timeout=3, guard=guard, verify=verify)
            result = json.loads((output / 'receipt.json').read_text())
            self.assertTrue(all(row['returncode'] is not None for row in result['processes'].values()))
            self.assertEqual(result['status'], 'failed')

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'pair'; output.mkdir()
            sentinel = output / 'receipt.json'; sentinel.write_text('original')
            with self.assertRaises(FileExistsError):
                run_pair(output, {name: factory(WRITE) for name in ('baseline', 'candidate')},
                         timeout=3, guard=lambda: None, verify=verify)
            self.assertEqual(sentinel.read_text(), 'original')

    def test_missing_oracle_refused_before_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch('subprocess.Popen') as popen:
            with self.assertRaises(ValueError):
                run_pair(Path(tmp) / 'pair', {name: factory(WRITE) for name in ('baseline', 'candidate')},
                         timeout=3, guard=lambda: None, verify=None)
            popen.assert_not_called()


if __name__ == '__main__':
    unittest.main()
