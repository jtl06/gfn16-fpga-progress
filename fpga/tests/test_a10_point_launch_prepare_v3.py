"""Source-only finite point-launch component packages; no HDL execution."""
import unittest
from fpga.reference import a10_point_launch_prepare_v3 as prep


class Preparation(unittest.TestCase):
    def test_four_ready_roles_exact_compiled_delta(self):
        for aw,field in ((5,0),(5,1),(5,2),(8,0)):
            m,files=prep.role(aw,field)
            self.assertIn(prep.gen.TARGET,m['build']['sv_sources'])
            self.assertNotIn(prep.batch.repair.ENGINE_V2,m['build']['sv_sources'])
            self.assertEqual(m['build']['cpp_source'],prep.CPP)
            self.assertEqual([x['expected_returncode'] for x in m['steps']],[0,1])
            self.assertIn(f'cycles={545 if aw==5 else 940}',m['steps'][0]['expected_stdout'])
            self.assertEqual(m['steps'][1]['expected_stderr'],'A10_POINT_COUNTER_NEGATIVE_REJECT\n')
            self.assertTrue(set(m['build']['sv_sources']+[prep.CPP])<=files.keys())

    def test_large_or_invalid_roles_fail_closed(self):
        for aw,field in ((16,0),(4,0),(5,3),(5.0,0)):
            with self.assertRaisesRegex(ValueError,'FINITE_ROLE'):prep.role(aw,field)


if __name__=='__main__':unittest.main()
