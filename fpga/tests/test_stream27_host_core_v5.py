import unittest
from fpga.reference import stream27_host_core_v4 as old
from fpga.reference import stream27_host_core_v5 as current


class GuardedEpochSeedWidth(unittest.TestCase):
    def test_width_boundary_only_and_explicit_guard(self):
        for n in (32,256):
            a=old.prepare(n);b=current.prepare(n)
            self.assertEqual(a['cycle_contract'],b['cycle_contract'])
            for name,text in a['files'].items():
                if name!=a['top']+'.sv':self.assertEqual(b['files'][name],text)
            s=b['files'][b['top']+'.sv']
            self.assertIn('parameter int unsigned EPOCH_SEED=0',s)
            self.assertIn("initial if(EPOCH_SEED>32'd65535",s)
            self.assertIn("job_epoch<=16'(EPOCH_SEED);next_cold_epoch<=16'(EPOCH_SEED)",s)
            self.assertNotIn('parameter logic [15:0] EPOCH_SEED',s)


if __name__=='__main__':unittest.main()
