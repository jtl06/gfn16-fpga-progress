import hashlib
import unittest

from fpga.reference.track_a4_canonical_controller_vectors_v1 import corpus


class CanonicalControllerVectorsTests(unittest.TestCase):
    def test_direct_integer_readback_and_phases(self):
        for aw in (5, 8):
            text, meta = corpus(aw)
            lines = text.splitlines()[1:]
            n, t = 1 << aw, (1 << aw)//16
            for i in range(0, len(lines), 3):
                base, mode, _, _, clocks, passes, special, maximum = map(int, lines[i].split())
                if mode:
                    continue
                values = [int(v) for v in lines[i+1].split()]
                values = [v-(1 << 32) if v >> 31 else v for v in values]
                expected = [int(v) for v in lines[i+2].split()]
                expected = [v-(1 << 32) if v >> 31 else v for v in expected]
                modulus = base**n+1
                before = sum(v*base**j for j, v in enumerate(values)) % modulus
                after = sum(v*base**j for j, v in enumerate(expected)) % modulus
                self.assertEqual(before, after)
                self.assertEqual(clocks, passes*(n+3)+(t+1 if special else 0))
                self.assertEqual(maximum, max(expected))
                self.assertTrue(all(0 <= d < base for d in expected) or expected == [-1]+[0]*(n-1))
            self.assertEqual(meta["cases"], 35)
            self.assertEqual(meta["normal"], 25)
            self.assertEqual(meta["injected_errors"], 6)
            self.assertEqual(meta["resets"], 4)
            self.assertGreaterEqual(meta["three_pass_cases"], 1)
            self.assertEqual(meta["sha256"], hashlib.sha256(text.encode()).hexdigest())

    def test_no_full_n_numeric_gate_on_mac(self):
        with self.assertRaises(ValueError):
            corpus(16)


if __name__ == "__main__":
    unittest.main()
