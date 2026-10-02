import hashlib
import unittest

from fpga.reference.track_a4_control_primitives_vectors_v1 import corpus


class A4ControlPrimitiveCorpusTests(unittest.TestCase):
    def test_setup_final_values_and_full_97_edge_latency(self):
        for aw in (5, 16):
            text, meta = corpus(aw)
            n, k = 1 << aw, 2*(1 << aw)+384
            minimum = max(2*n+5, (2*k+2)//3+1)
            accepted = None
            successes = 0
            for edge, line in enumerate(text.splitlines()[1:]):
                row = line.split()
                rst, cancel, begin, base, gen = map(int, row[:5])
                busy, done, error, cfg, ab, ag = map(int, row[10:16])
                if not rst or cancel:
                    accepted = None
                elif begin:
                    if minimum <= base <= 10**9 and not error:
                        accepted = (edge, base, gen)
                    else:
                        accepted = None
                if done and not error:
                    self.assertIsNotNone(accepted)
                    start, b, generation = accepted
                    self.assertEqual(edge-start, 97)
                    self.assertEqual((busy, cfg, ab, ag), (0, 1, b, generation))
                    B = b-1
                    self.assertEqual(int(row[16], 16), 2*((n+48)*B*B+64*B*k+16*k*k))
                    self.assertEqual(int(row[17], 16), (1 << 96)//b)
                    successes += 1
                    accepted = None
            self.assertEqual(successes, 11)
            self.assertEqual(meta["sha256"], hashlib.sha256(text.encode()).hexdigest())

    def test_cell_wire_decoding_ranges_and_old_cell_counterexample(self):
        old_cell_reject_new_cell_accept = 0
        for aw in (5, 16):
            text, _ = corpus(aw)
            n, k = 1 << aw, 2*(1 << aw)+384
            minimum = max(2*n+5, (2*k+2)//3+1)
            digit = carry = tag = 0
            for line in text.splitlines()[1:]:
                row = line.split()
                rst, valid = int(row[0]), int(row[5])
                b, y, c, incoming_tag = map(int, row[6:10])
                y = y-(1 << 33) if y >> 32 else y
                c = c-8 if c >> 2 else c
                legal = minimum <= b <= 10**9 and -2 <= c <= 2 and -max(b-1,k) <= y <= max(2*(b-1),b-1+k)
                v, e = int(row[18]), int(row[19])
                if not rst:
                    digit = carry = tag = 0
                    self.assertEqual((v, e), (0, 0))
                elif valid:
                    tag = incoming_tag
                    self.assertEqual((v, e), (int(legal), int(not legal)))
                    if legal:
                        carry, digit = divmod(y+c, b)
                        self.assertIn(carry, (-2,-1,0,1,2))
                        old_cell_reject_new_cell_accept += y < -(2*n+23*16)
                else:
                    self.assertEqual((v, e), (0, 0))
                self.assertEqual(tuple(map(int, row[20:23])), (digit, carry & 7, tag))
        self.assertGreater(old_cell_reject_new_cell_accept, 0)

    def test_scope(self):
        with self.assertRaises(ValueError):
            corpus(8)


if __name__ == "__main__":
    unittest.main()
