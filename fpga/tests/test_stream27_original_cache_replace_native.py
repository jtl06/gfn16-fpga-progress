"""Scalar/source-only checks for the ORIGINAL53 replacement query."""
import unittest
from fpga.reference import stream27_original_cache_replace_native as n


class CacheReplacementTests(unittest.TestCase):
    def test_matching_early_then_duplicate_predicate(self):
        self.assertFalse(n.cache_model(True, False, True))
        self.assertTrue(n.cache_model(True, True, True))
        self.assertTrue(n.cache_model(False, False, True))

    def test_only_cold0_token_and_actual_production_closure(self):
        m, files = n.role()
        term = 'rtl/' + n.TERM + '.sv'
        probe = term.removesuffix('.sv') + '_cold0_cache_replace_probe_v1.sv'
        self.assertEqual(len(m['build']['sv_sources']), 54)
        self.assertIn(term, m['build']['sv_sources'])
        self.assertIn(probe, m['build']['sv_sources'])
        text = files[probe].decode()
        self.assertIn("seed_owner[24:0]==25'd16776705", text)
        self.assertIn("product_owner[24:0]!=25'd16776705", text)
        self.assertEqual((65534 << 8) | 1, 16776705)
        self.assertTrue(m['cache_replacement_query']['original53'])
        self.assertFalse(m['cache_replacement_query']['promotion_allowed'])

    def test_harness_retains_oracle_and_actual_seed_witness(self):
        m, files = n.role()
        text = files[n.CPP].decode()
        for marker in ('S4_HOST_CONTEXT_SIGNED96_VALUE', 'S4_HOST_CONTEXT_READ_FULL_OWNER',
                       'CACHE_REPLACE_EARLY_READY_WITH_ZERO_SEED_PRODUCTS',
                       'CACHE_REPLACE_GENUINE_LAST_SEED_TOKEN_SUPPRESSED',
                       'CACHE_REPLACE_MATCHING_FULL27_OWNER'):
            self.assertIn(marker, text)
        self.assertTrue(m['steps'][0]['expected_stdout'].endswith(n.FOOTER))
        self.assertEqual(m['test_role'], 'deliberate_fault')


if __name__ == '__main__':
    unittest.main()
