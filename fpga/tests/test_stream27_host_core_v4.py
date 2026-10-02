import unittest
from fpga.reference import stream27_host_core_v3 as old
from fpga.reference import stream27_host_core_v4 as current


class AcceptedColdCompletion(unittest.TestCase):
    def test_no_arithmetic_cycle_or_smaller_core_change(self):
        for n in (32,256):
            a=old.prepare(n);b=current.prepare(n)
            self.assertEqual(a['cycle_contract'],b['cycle_contract'])
            for name,text in a['files'].items():
                if name!=a['top']+'.sv':self.assertEqual(b['files'][name],text)
            s=b['files'][b['top']+'.sv']
            self.assertIn('EPOCH_SEED=0',s)
            self.assertIn('completed_squares!=job_count',s)
            self.assertIn('job_epoch<=EPOCH_SEED;next_cold_epoch<=EPOCH_SEED',s)
            self.assertIn('next_cold_epoch<=job_epoch+16\'(job_count)',s)

    def test_seed_is_passed_through_actual_paired_top(self):
        b=current.prepare(32,paired=True);s=b['files'][b['top']+'.sv']
        self.assertIn('.EPOCH_SEED(EPOCH_SEED)',s)
        self.assertIn('NTT_LANES(64)',s)
        self.assertEqual(b['parameters'],dict(AW=5,P=16,CONTEXTS=1))


if __name__=='__main__':unittest.main()
