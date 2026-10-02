"""Retained report pure checks, never vendor/HDL/full-N arithmetic."""
import unittest
from fpga.reference import radix22_aa_physical_replay_v1 as a


class AAPhysicalTests(unittest.TestCase):
    def test_exact_retained_area_and_timing_tradeoff(self):
        r=a.replay()
        self.assertEqual(r['candidate_minus_parent']['needed_ALM'],-6208)
        self.assertEqual(r['candidate_minus_parent']['placed_ALM'],-7027)
        self.assertEqual(r['candidate_minus_parent']['LAB'],-554)
        self.assertEqual(r['candidate_minus_parent']['M20K'],0)
        self.assertEqual(r['candidate_minus_parent']['DSP'],0)
        self.assertEqual(r['candidate_minus_parent']['RAM_bits'],-5*65536)
        self.assertEqual(r['setup_delta_ns'],-0.372)
        self.assertFalse(r['scaled_three_field_or_whole_saving_claim'])
        self.assertFalse(r['promotion_allowed'])

    def test_no_missing_duplicate_or_wrong_bank_ram_inventory(self):
        raw=(a.DOSSIER/'evidence/project/output_files/probe.syn.rpt').read_text()
        line=next(x for x in raw.splitlines() if x.startswith('; child|child|memories[0].data_ram|') and 'Simple Dual Port' in x)
        for changed in (raw.replace(line,'',1),raw+'\n'+line,raw.replace(line,line.replace('memories[0].data_ram|','memories[128].data_ram|'),1)):
            with self.assertRaises(ValueError):a.memories(changed,27)

    def test_width_and_physical_allocation_are_not_assumed(self):
        raw=(a.DOSSIER/'evidence/project/output_files/probe.fit.rpt').read_text()
        self.assertEqual(a.memories(raw,27,True)['allocated_data_M20K'],128)
        with self.assertRaises(ValueError):a.memories(raw,32,True)
        line=next(x for x in raw.splitlines() if x.startswith('; child|child|memories[0].data_ram|') and 'Simple Dual Port' in x)
        with self.assertRaises(ValueError):a.memories(raw.replace(line,line.replace('1.000','2.000'),1),27,True)


if __name__=='__main__':unittest.main()
