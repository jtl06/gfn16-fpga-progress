"""Pure typed-outcome rejection tests; no native execution."""
import unittest
from fpga.reference import radix22_selector_native_replay_v1 as r


class SelectorNativeReplayTests(unittest.TestCase):
    def test_all_static_control_contracts(self):
        for mode in range(3):
            out = f'N1_SELECTOR_PASS mode={mode} cases=8192 responses=8192 aborts=4 faults=1 threads=1\n'.encode()
            r.contract(mode, 0, out, b'')
            with self.assertRaises(ValueError):
                r.contract(mode, 0, out.replace(b'8192', b'8191', 1), b'')

    def test_exact_typed_negative(self):
        for mode in range(3):
            r.contract(mode, 1, b'', b'N1_SELECTOR_MISMATCH\n', True)

    def test_incidental_failure_rejects(self):
        for err in (b'N1_SELECTOR_RESET\n', b'N1_SELECTOR_VALID\n', b'N1_SELECTOR_THREADS\n', b''):
            with self.assertRaises(ValueError):
                r.contract(2, 1, b'', err, True)

    def test_missing_or_extra_outcomes_reject(self):
        for rc, out, err in ((0, b'', b'N1_SELECTOR_MISMATCH\n'), (1, b'PASS\n', b'N1_SELECTOR_MISMATCH\n'),
                             (1, b'', b'N1_SELECTOR_MISMATCH'), (1, b'', b'N1_SELECTOR_MISMATCH\nextra\n')):
            with self.assertRaises(ValueError):
                r.contract(2, rc, out, err, True)

    def test_untyped_mode_and_streams_reject(self):
        for mode in (-1, 3, True, '2'):
            with self.assertRaises(ValueError):
                r.contract(mode, 1, b'', b'N1_SELECTOR_MISMATCH\n', True)
        for rc, out, err in ((True, b'', b'N1_SELECTOR_MISMATCH\n'), (1, '', b'N1_SELECTOR_MISMATCH\n'),
                             (1, b'', 'N1_SELECTOR_MISMATCH\n')):
            with self.assertRaises(ValueError):
                r.contract(2, rc, out, err, True)


if __name__ == '__main__':
    unittest.main()
