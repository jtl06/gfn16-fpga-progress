"""Mathematical/banking/event-model tests, never RTL or throughput evidence."""
import unittest

from reference.ntt27_experiment import select_basis
from reference.ntt27_radix4_feasibility import (
    check_banks, dif4, dit4, groups, reusable_pipeline,
)


class AdjacentStageFusionTests(unittest.TestCase):
    def test_four_point_formulas(self):
        for prime in select_basis():
            p = prime.p
            i = pow(prime.generator, (p-1)//4, p)
            w = pow(prime.generator, (p-1)//32, p)
            for values in ([0]*4, [p-1]*4, [0,1,p-1,p//2], [5,99,172,34]):
                self.assertEqual(dif4(values,w,w*w%p,i,p),
                                 dif4(values,w,w*w%p,i,p,True))
                fwd = dif4(values,w,w*w%p,i,p)
                back = dit4(fwd,pow(w,-1,p),pow(w,-2,p),pow(i,-1,p),p)
                self.assertEqual(back,[4*x%p for x in values])

    def test_bank_groups_across_fold_boundaries(self):
        for lanes in (16,64):
            for lg in (2,4,5,6,7,8,10):
                for high in range(1,lg):
                    result=check_banks(lg,lanes,high)
                    self.assertEqual(result['addresses_checked'],1<<lg)

    def test_spatial_root_port_counterexamples_exist(self):
        for lanes,high in ((16,6),(64,8)):
            result=check_banks(12,lanes,high)
            self.assertGreater(result['spatial_root_conflicts_at_lag6'],0)
            witness=result['spatial_conflict_example']
            self.assertNotEqual(witness['first_root'],witness['second_root'])

    def test_temporal_schedule_resource_accounting(self):
        for count in (1,2,3,8,32,512,2048):
            result=reusable_pipeline(count)
            self.assertEqual(result['extra_intermediate_frames'],1)
            self.assertEqual(result['baseline_two_stage_cycles']-
                             result['pair_cycles_with_one_setup'],2)

    def test_non_groupable_configuration_is_explicit(self):
        for lanes in (0,1,3):
            with self.assertRaises(ValueError):list(groups(4,lanes,2))
        with self.assertRaises(ValueError):list(groups(4,16,0))


if __name__=='__main__':unittest.main()
