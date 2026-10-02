import unittest

from fpga.reference import stream27_context_storage_timing_fault as f
from fpga.reference import stream27_context_storage_timing_external as external


class TimingStorageFaultTests(unittest.TestCase):
    def test_three_exact_production_roles_preserve_58(self):
        normal, original, _ = f.native.role('aw8')
        for mode in ('reset', 'owner', 'oracle'):
            manifest, files = f.role(mode)
            self.assertEqual(manifest['build']['sv_sources'], normal['build']['sv_sources'])
            for name in normal['build']['sv_sources']:
                self.assertEqual(files[name], original[name])
        self.assertEqual(f.role('oracle')[0]['steps'][0]['expected_returncode'], 1)

    def test_early_cache_retains_other_field_term_and_checks_actual_pre_token(self):
        manifest, files = f.role('early-cache')
        term = f.native.binder.TERM + '_storage2_v1'
        self.assertIn('rtl/' + term + '.sv', manifest['build']['sv_sources'])
        self.assertEqual(len(manifest['build']['sv_sources']), 59)
        cpp = files[f.CPP].decode()
        self.assertIn('need(observed&&failed', cpp)
        self.assertIn('C2_STORAGE_EARLY_CACHE_ACTUAL_PREMATURE_TOKEN', cpp)
        self.assertIn('premature_cache_rejected=1', manifest['steps'][0]['expected_stdout'])

    def test_external_actual_ingress_and_normal_recovery(self):
        manifest, files = external.role()
        self.assertEqual(len(manifest['build']['sv_sources']), 58)
        cpp = files[external.CPP].decode()
        self.assertIn('d.feed_mode=3', cpp)
        self.assertIn('C2_STORAGE_EXTERNAL_DENIED_PRE', cpp)
        self.assertIn('recovered_reads=1024', manifest['steps'][0]['expected_stdout'])

    def test_reset_actual_product_tail_and_full_owner_flips(self):
        _, files = f.role('reset')
        cpp = files[f.CPP].decode()
        self.assertIn('STORAGE(protocol_pw_row)==T-1&&STORAGE(term_producer__DOT__product_slot)', cpp)
        self.assertIn('const unsigned bits[4]={25,24,23,7}', cpp)
        self.assertIn('C2_STORAGE_RESET_ACTUAL_VALIDITY', cpp)
        self.assertIn('run(d); // Every reset recovers', cpp)


if __name__ == '__main__':
    unittest.main()
