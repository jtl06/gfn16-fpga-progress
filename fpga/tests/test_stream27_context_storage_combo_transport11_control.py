"""Source-only exact R11 observer/driver scope, not native qualification."""
import unittest
from fpga.reference import stream27_context_storage_combo_transport11_control as control


class Transport11ControlTests(unittest.TestCase):
    def test_source_literal_and_reset_payload_contract(self):
        m,files=control.role()
        self.assertEqual(len(m['build']['sv_sources']),59)
        self.assertTrue(m['transport11_control']['production58_unchanged'])
        self.assertFalse(m['transport11_control']['protected_fault_rollback_claim'])
        self.assertTrue(m['transport11_control']['numeric_payload_zero_not_assumed'])
        self.assertTrue(m['transport11_control']['no_public_cancel_port'])
        cpp=files[control.CPP].decode()
        self.assertIn('WATCHDOG_AGE=64*N+4096-1',cpp)
        self.assertNotIn('probe_stop=',cpp)
        self.assertNotIn('lean_watchdog_error=',cpp)
        self.assertEqual(cpp.count('DUT d{&context}'),1)
        self.assertLess(cpp.index('gfn16_runtime::configure(context,argc,argv)'),cpp.index('DUT d{&context}'))
        self.assertEqual(m['steps'][1]['expected_returncode'],1)
        for name,pin in m['rtl_readiness']['source_snapshot'].items():
            self.assertEqual(control.sha(files[name]),pin)
        observer=files['rtl/'+m['build']['top']+'.sv'].decode()
        self.assertIn('candidate.engine.arithmetic.crt_transport_slot',observer)
        self.assertIn('candidate.engine.arithmetic.field0.pair_slot_q',observer)
        self.assertIn('candidate.engine.arithmetic.field0.inverse_slot_q',observer)
        self.assertNotIn('always_ff',observer)


if __name__=='__main__':unittest.main()
