import unittest
from decimal import Decimal
from fpga.reference import stream27_p8_canon1_promotion_v1 as q


class PromotionScalarTests(unittest.TestCase):
    def test_exact_primary_sample(self):
        d=q.sample_ledger()
        self.assertEqual(d['cold_primary_cycles'],31838102204)
        self.assertEqual(Decimal(d['cold_primary_seconds']),Decimal('407.973441642056'))
        self.assertEqual(d['cached_alternate_cycles'],31838102105)
        self.assertEqual(Decimal(d['cached_alternate_seconds']),Decimal('407.973440373470'))
        self.assertEqual(d['canonical_and_copy_occurrences'],1)

    def test_actual_finite_calendars(self):
        g=dict(warm_interval=16653,carry_done=24847)
        for count,cycles in [(1,680315),(100,2328962),(1000,17316662)]:
            with self.subTest(count=count):
                self.assertEqual(q.source_cycles(65536,g,count)['host_done'],cycles)

    def test_no_hidden_root_or_special_cost(self):
        g=dict(warm_interval=16653,carry_done=24847)
        cold=q.source_cycles(65536,g,1000)['host_done']
        self.assertEqual(cold-q.source_cycles(65536,g,1000,True)['host_done'],99)
        self.assertEqual(q.source_cycles(65536,g,1000,False,True)['host_done']-cold,65536)

    def test_count_bounds(self):
        for count in (0,-1,2**32):
            with self.assertRaises(ValueError):
                q.source_cycles(65536,dict(warm_interval=16653,carry_done=24847),count)

    def test_fit_closure(self):
        d=q.fit_sources()
        self.assertEqual(len(d['source_sha256']),49)
        self.assertEqual(d['source_sha256'][q.LEAF],q.LEAF_PIN)


if __name__ == '__main__':
    unittest.main()
