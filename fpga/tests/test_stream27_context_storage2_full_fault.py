import unittest
from fpga.reference import stream27_context_storage2_full_fault as m


class FullFaultSource(unittest.TestCase):
    def test_real_original_source_and_negative_contracts(self):
        role, files = m.role('contracts')
        self.assertEqual(len(role['build']['sv_sources']), 54)
        self.assertEqual(role['build']['parameters']['AW'], 16)
        self.assertEqual(role['test_role'], 'deliberate_fault')
        self.assertTrue(role['storage2_full_fault']['production_rtl_unchanged'])
        self.assertEqual(len(role['steps']), 5)
        self.assertEqual(role['steps'][-1]['expected_returncode'], 1)
        self.assertEqual(role['steps'][-1]['expected_stderr'], 'R84_FULL_SIGNED96_REFERENCE ctx=0 address=0\n')
        self.assertIn(b'C2_FULL_ORDINAL_SAME_EDGE_FAULT', files[m.CPP])

    def test_cache_probe_only_declared_delta(self):
        role, files = m.role('early-cache')
        delta = role['storage2_full_fault']['diagnostic_rtl_delta']
        self.assertEqual(len(delta), 1)
        self.assertFalse(role['storage2_full_fault']['production_rtl_unchanged'])
        probe = next(n for n in role['build']['sv_sources'] if n.endswith('_earlycache_full_probe.sv'))
        self.assertIn(b'(seed_slot && seed_start && !stop)', files[probe])
        self.assertIn('rtl/genefer_stream27_term_context_param_v1_contexts_v1_storage2_v1.sv', role['build']['sv_sources'])
        self.assertEqual(len(role['build']['sv_sources']), 55)
        self.assertEqual(role['steps'][0]['expected_returncode'], 0)
