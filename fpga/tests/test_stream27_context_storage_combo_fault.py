"""Bounded source/header proof for the combination's separate diagnostics."""
import unittest
from fpga.reference import stream27_context_storage_combo_fault as f


class ComboFaultTests(unittest.TestCase):
    def test_actual_combo_graph_not_inherited_fault_pass(self):
        normal, old, bundle = f.native.role('aw8')
        for mode in ('external', 'reset', 'owner', 'oracle'):
            m, files = f.role(mode)
            self.assertEqual(m['build']['sv_sources'], normal['build']['sv_sources'])
            self.assertTrue(all(files[n] == old[n] for n in m['build']['sv_sources']))
            self.assertTrue(m['storage2_fault']['production_rtl_unchanged'])
            self.assertFalse(m['storage2_fault']['shared_fault_peer_recovery'])
            self.assertEqual(m['test_role'], 'deliberate_fault')

    def test_external_reaches_real_feed_ingress(self):
        m, files = f.role('external')
        cpp = files[m['build']['cpp_source']].decode()
        self.assertIn('d.start_contexts=d.batch_mode=d.feed_mode=3', cpp)
        self.assertIn('d.command_ready&&!d.command_accept&&!d.error', cpp)
        self.assertEqual(m['steps'][0]['expected_returncode'], 0)
        self.assertIn('recovered_reads=1024', m['steps'][0]['expected_stdout'])
        self.assertTrue(m['steps'][0]['expected_stdout'].endswith('\n'))
        self.assertNotIn('\\n', m['steps'][0]['expected_stdout'])

    def test_reset_owner_real_generated_members(self):
        m, files = f.role('reset')
        self.assertIn('storage_combo_v1__DOT__engine', files[f.HEADER].decode())
        self.assertIn('STORAGE(protocol_pw_row)==T-1', files[f.CPP].decode())
        self.assertIn('run(d); // Every reset recovers', files[f.CPP].decode())
        self.assertIn('recovered_reads=3072', m['steps'][0]['expected_stdout'])
        m, files = f.role('owner')
        self.assertIn('const unsigned bits[4]={25,24,23,7}', files[f.CPP].decode())

    def test_early_cache_retains_peer_parent_and_observes_pre(self):
        m, files = f.role('early-cache')
        self.assertEqual(len(m['build']['sv_sources']), 54)
        parent='rtl/genefer_stream27_term_context_param_v1_contexts_v1_storage2_v1_payload_lookahead_v1.sv'
        self.assertIn(parent, m['build']['sv_sources'])
        self.assertIn('observed&&failed', files[f.CPP].decode())
        self.assertEqual(len(m['storage2_fault']['diagnostic_rtl_delta']), 2)
        for field in ('f1', 'f2'):
            source=next(data.decode() for n,data in files.items() if '_'+field+'_' in n and n.endswith('_storage_combo_v1.sv'))
            self.assertNotIn('_earlycache_probe #', source)

    def test_strict_oracle_negative_and_modes(self):
        m, _ = f.role('oracle')
        self.assertEqual(m['steps'][0]['expected_returncode'], 1)
        self.assertEqual(m['steps'][0]['expected_stdout'], '')
        self.assertEqual(m['steps'][0]['expected_stderr'], 'S4_HOST_CONTEXT_SIGNED96_VALUE ctx=0 address=0\n')
        with self.assertRaises(ValueError): f.role('normal')


if __name__ == '__main__': unittest.main()
