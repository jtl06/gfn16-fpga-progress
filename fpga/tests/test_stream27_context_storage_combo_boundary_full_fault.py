"""Actual full-normal generated ABI binds separate combination diagnostics."""
import json
import unittest
from fpga.reference import stream27_context_storage_combo_boundary_full_fault as f
from fpga.reference import stream27_context_storage_combo_boundary_crosstalk as c


class ComboFullFaultTests(unittest.TestCase):
    def test_complete_unchanged_rtl_and_typed_failures(self):
        m, files = f.role('contracts')
        original = json.loads((f.DONOR/'manifest.json').read_text())
        self.assertEqual(m['build']['sv_sources'], original['build']['sv_sources'])
        self.assertTrue(all(m['sources'][n]==original['sources'][n] for n in m['build']['sv_sources']))
        self.assertEqual(len(m['build']['sv_sources']), 55)
        self.assertEqual([s['expected_returncode'] for s in m['steps']], [0,0,0,0,1])
        self.assertTrue(m['storage2_full_fault']['full56_ordinal_alias'])
        self.assertTrue(m['storage2_full_fault']['ordinal_origin_capture_bad_same_edge'])
        self.assertFalse(m['storage2_full_fault']['shared_fault_peer_recovery'])

    def test_real_reset_edges_and_no_partial_publication(self):
        m, files = f.role('contracts'); cpp=files[f.CPP].decode()
        self.assertIn('STORAGE(protocol_pw_row)==T-1&&STORAGE(term_producer__DOT__product_slot)', cpp)
        self.assertIn('C2_FULL_ORDINAL_SAME_EDGE_FAULT', cpp)
        self.assertIn('reads+=recover(d,input,reference)', cpp)
        self.assertIn('C2_FULL_STICKY_NO_PUBLICATION', cpp)
        self.assertIn('___024root.h', files[f.HEADER].decode())
        with self.assertRaises(ValueError): f.role('early-cache')

    def test_crosstalk_is_zero_edge_native_observer_only(self):
        m, files = c.role()
        from fpga.reference import stream27_context_storage_combo_boundary_native as n
        old, before, bundle = n.role('full')
        self.assertTrue(all(m['sources'][name]==old['sources'][name] for name in old['build']['sv_sources'] if name!='rtl/'+old['build']['top']+'.sv'))
        observer=files['rtl/'+c.TOP+'.sv'].decode()
        self.assertIn('candidate (.read_data(native_read_data), .*);', observer)
        self.assertIn("host_addr==16'd17", observer)
        self.assertNotIn('always', observer)
        self.assertEqual(len(m['build']['sv_sources']), 55)

    def test_crosstalk_requires_exact_peer_and_single_mismatch(self):
        value=dict(aw=16,p=16,contexts=2,bases=c.BASES,squares=4,peer_verified_words=65536,
            mutated_context=0,mutated_address=17,typed_mismatches=1,signed96=True,peer_bit_identical=True,
            metadata_unchanged=True,native_output_word_only=True,model_threads=1,seconds=1.)
        def out(): return 'R84_C2_CROSSTALK_PASS '+json.dumps(value)+'\n'
        self.assertEqual(c.validate(out(),'',0,c.config(),{})['status'],'PASS_expected_contracts')
        for k,bad in [('peer_verified_words',65535),('typed_mismatches',0),('metadata_unchanged',False)]:
            good=value[k];value[k]=bad
            with self.assertRaises(ValueError): c.validate(out(),'',0,c.config(),{})
            value[k]=good


if __name__=='__main__':unittest.main()

