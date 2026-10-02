import unittest
from fpga.reference import a10_point_launch_prepare_v4 as prep


class FullPointGeometry(unittest.TestCase):
    def test_cpp_changes_only_geometry_admission(self):
        text = prep.cpp_source()
        self.assertEqual((prep.ROOT/prep.CPP).read_text(), text)
        self.assertIn('AW==16', text)
        self.assertIn('if constexpr(AW<=8)', text)
        self.assertIn('else return conventional(a,false)', text)
        self.assertIn('A10_POINT_COUNTER_NEGATIVE_REJECT', text)

    def test_three_fullN_source_roles_unchanged_engine_and_math(self):
        for field in range(3):
            m, files = prep.role(16, field, allow_full_constants=True)
            self.assertEqual(m['build']['parameters']['AW'], 16)
            self.assertEqual(files[prep.parent.gen.TARGET], (prep.ROOT/prep.parent.gen.TARGET).read_bytes())
            self.assertEqual(m['sources'][prep.LOOKUP], prep.LOOKUP_SHA)
            self.assertIn('residues=983040 cycles=88520', m['steps'][0]['expected_stdout'])
            self.assertEqual(m['steps'][1]['expected_stderr'], 'A10_POINT_COUNTER_NEGATIVE_REJECT\n')
            self.assertEqual(m['point_launch']['source_only_ledger']['point_cycles'], 1032)
            self.assertEqual(m['point_launch']['source_only_ledger']['whole_controller_ntt_cycles'], 17710)
            self.assertFalse(m['point_launch']['full_N_numeric_locally_performed'])

    def test_explicit_source_generation_gate(self):
        with self.assertRaisesRegex(ValueError, 'CONSTANTS_EXPLICIT'):
            prep.role(16, 0)
        for aw, field in ((8,0), (17,0), (16,3), (16,True)):
            with self.assertRaisesRegex(ValueError, 'FULL_ROLE'):
                prep.role(aw, field, allow_full_constants=True)


if __name__ == '__main__':
    unittest.main()
