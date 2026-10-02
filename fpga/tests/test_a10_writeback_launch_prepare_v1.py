import unittest
from fpga.reference import a10_writeback_launch_prepare_v1 as prep


class WritebackRoles(unittest.TestCase):
    def test_all_nine_source_closed_roles_exact_math_parent(self):
        for aw in (5,8,16):
            for field in (0,1,2):
                m,files=prep.role(aw,field,allow_full_constants=True)
                parent,_=prep.parent.role(aw,field,allow_full_constants=True)
                self.assertEqual(m['build']['parameters'],parent['build']['parameters'])
                self.assertEqual(m['build']['cflags'],parent['build']['cflags'])
                self.assertEqual(m['build']['top'],parent['build']['top'])
                self.assertIn(prep.gen.TARGET,m['build']['sv_sources'])
                self.assertIn(prep.gen.NATIVE_HOST,m['build']['sv_sources'])
                self.assertNotIn(prep.gen.PARENT,m['build']['sv_sources'])
                self.assertIn('pending_cancels=4 recovery_operations=4',m['steps'][0]['expected_stdout'])
                self.assertEqual(m['steps'][1]['expected_returncode'],1)
                self.assertEqual(m['steps'][1]['expected_stderr'],'A10_WRITEBACK_COUNTER_NEGATIVE_REJECT\n')
                self.assertFalse(m['writeback_launch']['hold_repair_claim'])
                self.assertEqual(files[prep.gen.TARGET],(prep.ROOT/prep.gen.TARGET).read_bytes())

    def test_bad_geometry_or_implicit_fullN_fails(self):
        for aw,field in ((4,0),(17,0),(5,3),(5,True)):
            with self.assertRaisesRegex(ValueError,'FINITE_ROLE'):prep.role(aw,field)
        with self.assertRaisesRegex(ValueError,'CONSTANTS_EXPLICIT'):prep.role(16,0)


if __name__=='__main__':unittest.main()
