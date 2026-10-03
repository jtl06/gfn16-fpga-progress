import json
import unittest
from fpga.reference import stream27_context_storage_combo_full_early_cache as f


class FullEarlyCacheTests(unittest.TestCase):
    def test_actual_full_source_f0_only_and_shared_leaf_retained(self):
        manifest, files = f.role()
        old = json.loads((f.full.DONOR / 'manifest.json').read_text())
        self.assertEqual(len(manifest['build']['sv_sources']), 55)
        self.assertIn('rtl/' + f.TERM + '.sv', manifest['build']['sv_sources'])
        delta = manifest['storage2_full_fault']['diagnostic_rtl_delta']
        self.assertEqual(len(delta), 2)
        self.assertTrue(all(manifest['sources'][n] == old['sources'][n]
                            for n in old['build']['sv_sources'] if n not in delta))
        self.assertEqual(manifest['context_storage_combo']['geometry']['correction_cache_latency'], 77)
        self.assertEqual(manifest['build']['parameters']['AW'], 16)

    def test_real_premature_token_and_no_publication(self):
        manifest, files = f.role()
        cpp = files[f.full.CPP].decode()
        self.assertIn('STORAGE(term_cache_ready)', cpp)
        self.assertIn('need(!STORAGE(term_producer__DOT__product_slot)', cpp)
        self.assertIn('need(observed&&failed', cpp)
        self.assertIn('C2_FULL_EARLY_CACHE_NO_PUBLICATION', cpp)
        self.assertIn('C2_FULL_STICKY_NO_PUBLICATION', cpp)
        self.assertEqual(manifest['steps'][0]['expected_stdout'], f.FOOTER)
        self.assertEqual(manifest['steps'][0]['expected_returncode'], 0)
        self.assertTrue(manifest['storage2_full_fault']['early_cache_full_geometry'])

    def test_mutation_anchor_is_exact(self):
        with self.assertRaises(ValueError):
            f.once('duplicate duplicate', 'duplicate', 'changed')


if __name__ == '__main__':
    unittest.main()
