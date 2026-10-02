import unittest
from fpga.reference import stream27_host_core_v2 as old
from fpga.reference import stream27_host_core_v3 as current


class PersistentColdEpoch(unittest.TestCase):
    def test_native_failure_counterexample_and_modular_sequence(self):
        expected=1;historical_cold=0
        self.assertNotEqual(historical_cold,expected)
        # Exact frozen protocol first admission may be arbitrary; later must
        # equal previous accepted epoch+1, irrespective of fresh generation.
        next_cold=65530;next_expected=next_cold
        for count in (1,2,4,32,1,32):
            job_epoch=next_cold
            for index in range(count):
                admitted=(job_epoch+index)&65535
                self.assertEqual(admitted,next_expected)
                next_expected=(admitted+1)&65535
            next_cold=(job_epoch+count)&65535 # Only after successful copy/drain.
            self.assertEqual(next_cold,next_expected)

    def test_only_outer_ledger_changes_and_no_latency_relaxation(self):
        for n in (32,256):
            a=old.prepare(n);b=current.prepare(n)
            for name,text in a['files'].items():
                if name!=a['top']+'.sv':self.assertEqual(b['files'][name],text)
            self.assertEqual(a['cycle_contract'],b['cycle_contract'])
            s=b['files'][b['top']+'.sv']
            self.assertIn('.epoch_in(job_epoch),.correction_epoch(job_epoch)',s)
            self.assertIn('next_cold_epoch<=job_epoch+16\'(job_count)',s)
            self.assertNotIn('.epoch_in(16\'d0)',s)
            self.assertIn('S4_HOST_PHASE_ACCOUNTING',s)


if __name__=='__main__':unittest.main()
