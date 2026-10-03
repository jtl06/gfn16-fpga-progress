"""R6 fault cohorts: own graph, exact source closure, truthful footer scopes."""
import unittest
from fpga.reference import stream27_context_storage_combo_oneshot_full_fault as f
from fpga.reference import stream27_context_storage_combo_oneshot_full_early_cache as e


class OneShotFaultTests(unittest.TestCase):
    def test_full_contracts_graph_and_reset_precision(self):
        m,files=f.role('contracts')
        self.assertEqual(len(m['build']['sv_sources']),56)
        self.assertTrue(m['storage2_full_fault']['production_rtl_unchanged'])
        self.assertTrue(m['storage2_full_fault']['full_count2_reset_does_not_epoch_wrap'])
        self.assertIn('epoch_wrap=0',m['steps'][2]['expected_stdout'])
        self.assertIn(b'epoch_wrap=0',files[f.CPP])
        self.assertEqual(m['steps'][-1]['expected_returncode'],1)
        self.assertEqual(m['build']['parameters']['COLD_SECOND_ONESHOT'],1)

    def test_full_cache_keeps_shared_f1f2_term_and_exact_diagnostic_delta(self):
        m,files=e.role()
        old='rtl/'+e.TERM+'.sv'
        self.assertIn(old,m['build']['sv_sources'])
        self.assertEqual(len(m['build']['sv_sources']),57)
        self.assertEqual(len(m['storage2_full_fault']['diagnostic_rtl_delta']),2)
        self.assertEqual(m['storage2_full_fault']['cache_latency'],78)
        self.assertIn(b'C2_FULL_EARLY_CACHE_ACTUAL_PREMATURE_TOKEN',files[f.CPP])
        self.assertIn(b'need(observed&&failed',files[f.CPP])
        self.assertTrue(all(m['sources'][n]==pin for n,pin in m['rtl_readiness']['source_snapshot'].items()))


if __name__=='__main__':unittest.main()
