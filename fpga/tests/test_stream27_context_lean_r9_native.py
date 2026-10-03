import unittest
from fpga.reference import stream27_context_lean_r9_native as own
from fpga.reference import stream27_context_lean_r9_output as output


class LeanR9NativeTests(unittest.TestCase):
    def test_own_roles_keep_r9_numeric_and_runtime_inputs(self):
        for stage in ('aw8', 'full'):
            m, files, production = own.role(stage)
            self.assertEqual(len(production['files']), 55)
            self.assertEqual(len(m['build']['sv_sources']), 55 if stage == 'aw8' else 56)
            self.assertEqual(m['build']['parameters']['LEAN_PRODUCTION'], 1)
            self.assertTrue(m['lean_production']['r9_safety_and_publication_preserved'])
            self.assertFalse(m['lean_production']['fault_immunity_inherited'])
            self.assertNotIn('context_registered_error', m)
            self.assertIn('context_registered_error', m['lean_production']['protected_twin_source_provenance'])
            cpp = files[m['build']['cpp_source']].decode()
            self.assertEqual(cpp.count(own.LABEL), 1)
            self.assertIn('return gfn16_runtime::probe(context,d);std::cout', cpp)
            if stage == 'full':
                self.assertEqual(m['steps'][0]['validator']['source'], own.OUTPUT)
                self.assertEqual(m['steps'][0]['validator']['config']['parent_config']['publication_fence_edges'], 1)

    def test_no_unlabeled_success(self):
        with self.assertRaisesRegex(ValueError, 'EXPLICIT_LEAN_LABEL'):
            output.validate('R84_C2_FULL_PASS {}\n', '', 0,
                            dict(parent_config={}, parent_source_sha256='0'*64), {})


if __name__ == '__main__':
    unittest.main()
