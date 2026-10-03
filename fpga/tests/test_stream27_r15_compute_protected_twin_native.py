import unittest
from fpga.reference import stream27_r15_compute_protected_twin_native as t


class Twin(unittest.TestCase):
    def test_both_own_geometries(self):
        for s in t.IDS:
            m,f,b=t.role(s)
            self.assertEqual(m['build']['parameters']['LEAN_BUILD'],0)
            self.assertEqual(m['build']['parameters']['FIXED_SCHEDULE'],1)
            self.assertEqual(m['build']['parameters']['STORAGE_TO_RAM'],1)
            self.assertEqual(m['build']['parameters']['PROGRESS_WATCHDOG'],1)
            self.assertTrue(m['r15_protected_twin']['separate_compilation'])
            self.assertEqual(b['geometry']['warm_interval'],215 if s=='aw8' else 8461)
            if s=='full':
                self.assertIn('LEAN_BUILD=0',f['rtl/'+m['build']['top']+'.sv'].decode())


if __name__=='__main__':unittest.main()
