"""Actual own full normal/ABI binding, source-only fault contract tests."""
import json
import unittest
from fpga.reference import stream27_context_storage_combo_readlocal_full_fault as fault


class FullFaultRoles(unittest.TestCase):
    def test_exact_production_contracts(self):
        donor=json.loads((fault.DONOR/'manifest.json').read_bytes())
        before={n:(fault.DONOR/'source/fpga'/n).read_bytes() for n in donor['build']['sv_sources']}
        m,f=fault.role('contracts')
        self.assertEqual(len(m['build']['sv_sources']),56)
        self.assertTrue(all(f[n]==raw for n,raw in before.items()))
        self.assertEqual(len(m['steps']),5)
        self.assertEqual([s['expected_returncode'] for s in m['steps']],[0,0,0,0,1])
        self.assertTrue(m['storage2_full_fault']['full56_ordinal_alias'])
        self.assertTrue(m['storage2_full_fault']['ordinal_origin_capture_bad_same_edge'])
        self.assertFalse(m['storage2_full_fault']['shared_fault_peer_recovery'])

    def test_early_cache_only_f0_preserves_original_term(self):
        m,f=fault.role('early-cache')
        self.assertEqual(len(m['build']['sv_sources']),57)
        self.assertEqual(len(m['storage2_full_fault']['diagnostic_rtl_delta']),1)
        term='rtl/genefer_stream27_term_context_param_v1_contexts_v1_storage2_v1_payload_lookahead_v1.sv'
        self.assertIn(term,m['build']['sv_sources'])
        self.assertEqual(f[term],(fault.DONOR/'source/fpga'/term).read_bytes())
        self.assertIn('premature_cache_rejected=1',m['steps'][0]['expected_stdout'])


if __name__=='__main__':unittest.main()
