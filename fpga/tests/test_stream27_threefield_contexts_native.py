import unittest
from fpga.reference import stream27_threefield_contexts_native as native

class ThreefieldNativeTests(unittest.TestCase):
    def test_normal_source_calendar_and_profile_contract(self):
        m,files=native.role();plan=m['threefield_contexts']['calendar']
        self.assertEqual(m['build']['parameters'],dict(AW=5,P=8,CONTEXTS=2))
        self.assertEqual(plan['context_frame_counts'],[3,5]);self.assertTrue(plan['carry_active_nonoverlap'])
        self.assertEqual(plan['setup_latency'],98);self.assertEqual([p['bits'] for p in plan['setup_profiles']],[213,213])
        self.assertEqual([p['base'] for p in plan['setup_profiles']],[1009,2017])
        self.assertEqual(len(m['steps']),1);self.assertFalse(m['threefield_contexts']['full_N_numeric_locally_performed'])
        self.assertIn(b'S4_THREE_CTX_ACTUAL_FEEDBACK_ROW_READY',files[native.CPP])
        self.assertIn(b'S4_THREE_CTX_ACTUAL_FEEDBACK_CORRECTION_READY',files[native.CPP])
        self.assertIn(b'S4_THREE_CTX_DIGIT_FULL_TAG',files[native.CPP])
        self.assertIn(b'S4_THREE_CTX_BOUNDARY_FULL_TAG',files[native.CPP])
    def test_four_metadata_banks_not_epoch_parity(self):
        m,files=native.role();top=files['rtl/'+m['build']['top']+'.sv']
        self.assertIn(b'wire [1:0] bank=field_sink_bank[0]',top)
        self.assertIn(b'logic [3:0] bank_live',top)
        self.assertNotIn(b'wire bank=field_epoch[0][0]',top)
        self.assertIn(b'actual_feedback_starts=6 intermediate_external_driver=1',m['steps'][0]['expected_stdout'].encode())
    def test_successor_intrinsic_profile_gate_and_cancel_distinction(self):
        m,files=native.role();top=files['rtl/'+m['build']['top']+'.sv']
        self.assertTrue(m['build']['top'].endswith('_profile_qualified_v2'))
        self.assertNotIn(b'in_slot_valid && !fault_pending',top)
        fault=(native.ROOT/'rtl/tb/stream27_threefield_contexts_fault.cpp').read_bytes()
        self.assertIn(b'S4_THREE_CTX_CANCEL_NO_GLOBAL_FAULT',fault)
        self.assertIn(b'S4_THREE_CTX_CANCEL_NO_DIGIT_PUBLICATION',fault)
        self.assertIn(b'S4_THREE_CTX_DUPLICATE_SECOND',fault)
if __name__=='__main__':unittest.main()
