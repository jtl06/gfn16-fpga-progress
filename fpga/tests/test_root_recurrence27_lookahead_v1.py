import itertools
import unittest
from fpga.reference import root_recurrence27_lookahead_v1 as s


class LookaheadTests(unittest.TestCase):
    def test_exact_sources(self):
        self.assertEqual(len(s.verify()), 3)

    def test_exhaustive_issued_period(self):
        self.assertEqual(s.prove_selectors(), 2359378)

    def test_exhaustive_small_bubble_traces(self):
        for period in (0, 1, 2, 4, 8, 16):
            for length in range(9):
                for gaps in itertools.product((False, True), repeat=length):
                    for issued, baseline, candidate, ready, candidate_ready in s.trace(period, gaps):
                        self.assertEqual(baseline, candidate, (period, gaps, issued))
                        self.assertEqual(ready, candidate_ready)
                        if issued < 12:
                            self.assertTrue(ready)

    def test_bubble_mutant_witness(self):
        witness = s.trace(0, (False, True), broken=True)
        self.assertEqual(witness[1][0], 0)
        self.assertEqual(witness[1][1][:3], (True, 0, 0))
        self.assertEqual(witness[1][2][:3], (True, 1, 1))

    def test_start_reset_selector(self):
        for period in [0]+[1 << bit for bit in range(17)]:
            self.assertEqual(s.selector(0, period, False, 0), (True, 0, 0, False))
            for depth in range(5):
                tail = s.trace(period, [True]*depth+[False]*7)
                self.assertTrue(all(row[1] == row[2] for row in tail))

    def test_mutant_is_one_change(self):
        text = (s.ROOT/'rtl/kernel'/(s.NAMES[s.REC]+'.sv')).read_text()
        mutated = s.mutant(text)
        self.assertNotEqual(text, mutated)
        self.assertEqual(mutated.replace("issued+17'(state==RUN)", "issued+17'(fire)"), text)


if __name__ == '__main__':
    unittest.main()
