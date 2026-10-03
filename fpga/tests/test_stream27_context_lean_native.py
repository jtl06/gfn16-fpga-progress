import unittest
from fpga.reference import stream27_context_lean_native as native
from fpga.reference import stream27_context_lean_output as output


class LeanNativeTests(unittest.TestCase):
    def test_own_normal_roles_and_label_probe(self):
        for stage in ('aw8', 'full'):
            manifest, files, production = native.role(stage)
            self.assertEqual(len(production['files']), 55)
            self.assertEqual(len(manifest['build']['sv_sources']), 55 if stage == 'aw8' else 56)
            self.assertEqual(manifest['build']['parameters']['LEAN_PRODUCTION'], 1)
            cpp = files[manifest['build']['cpp_source']].decode()
            self.assertEqual(cpp.count(output.LABEL), 1)
            self.assertIn('return gfn16_runtime::probe(context,d);std::cout', cpp)
            self.assertFalse(manifest['lean_production']['fault_immunity_inherited'])
            self.assertFalse(manifest['lean_production']['host_gl_implemented'])
            self.assertIn('R6_ONESHOT', (native.ROOT/native.BINDER).read_text())
            if stage == 'aw8':
                self.assertTrue(manifest['steps'][0]['expected_stdout'].startswith(output.LABEL+'\n'))
            else:
                self.assertEqual(manifest['steps'][0]['validator']['source'], native.OUTPUT)

    def test_no_unlabeled_full_success(self):
        with self.assertRaisesRegex(ValueError, 'EXPLICIT_LEAN'):
            output.validate('R84_C2_FULL_PASS {}\n', '', 0,
                dict(parent_config={}, parent_source_sha256='0'*64), {})


if __name__ == '__main__':
    unittest.main()
