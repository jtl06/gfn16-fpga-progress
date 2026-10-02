import unittest
from fpga.reference import a10_upper_sum_engine_prepare_v2 as prep


class ConnectedUpperSource(unittest.TestCase):
    def test_all_nine_roles_only_cell_binding_and_exact_oracle(self):
        for aw in (5,8,16):
            for field in range(3):
                m, files = prep.role(aw,field,allow_full_constants=True)
                original,_ = prep.full.role(16,field,allow_full_constants=True) if aw == 16 else prep.small.role(aw,field)
                self.assertEqual(m['steps'],original['steps'])
                self.assertEqual(m['build']['parameters'],original['build']['parameters'])
                self.assertEqual(m['build']['cflags'],original['build']['cflags'])
                self.assertEqual(m['build']['cpp_source'],original['build']['cpp_source'])
                self.assertIn(prep.gen.TARGET,m['build']['sv_sources'])
                self.assertIn(prep.gen.ENGINE,m['build']['sv_sources'])
                self.assertNotIn(prep.gen.PARENT,m['build']['sv_sources'])
                self.assertNotIn(prep.gen.POINT,m['build']['sv_sources'])
                self.assertEqual(files[prep.gen.ENGINE],(prep.ROOT/prep.gen.ENGINE).read_bytes())
                self.assertTrue(m['upper_sum_launch']['no_engine_cycle_or_control_delta'])

    def test_bad_geometry_and_implicit_fullN_fail_closed(self):
        for aw,field in ((4,0),(17,0),(5,3),(5,True)):
            with self.assertRaisesRegex(ValueError,'GEOMETRY'):
                prep.role(aw,field)
        with self.assertRaisesRegex(ValueError,'CONSTANTS_EXPLICIT'):
            prep.role(16,0)


if __name__ == '__main__':
    unittest.main()
