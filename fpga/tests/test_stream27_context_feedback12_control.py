"""Own R12 source-only control fixture checks, not native fault qualification."""
import unittest
from fpga.reference import stream27_context_feedback12_control as own


class Feedback12ControlTests(unittest.TestCase):
    def test_literal_production_stateless_observation_and_both_new_queues(self):
        m,files=own.role()
        self.assertEqual(len(m['build']['sv_sources']),59)
        self.assertTrue(m['feedback12_control']['production58_unchanged'])
        self.assertFalse(m['feedback12_control']['protected_fault_rollback_claim'])
        self.assertTrue(m['feedback12_control']['numeric_payload_zero_not_assumed'])
        observer=files['rtl/'+m['build']['top']+'.sv'].decode()
        for name in ('candidate.engine.feedback_slot_q','candidate.engine.feedback_start_q',
                     'candidate.engine.auto_correction_q','candidate.engine.arithmetic.crt_transport_slot'):
            self.assertIn(name,observer)
        self.assertNotIn('always_ff',observer)
        cpp=files[own.CPP].decode()
        self.assertIn('mode==2?6:mode==3?7:8',cpp)
        self.assertIn('if(mode<5)reset_seam',cpp)
        self.assertIn('reads==24*N',cpp)
        self.assertIn('WATCHDOG_AGE=64*N+4096-1',cpp)
        self.assertNotIn('probe_stop=',cpp)
        self.assertNotIn('lean_watchdog_error=',cpp)
        self.assertEqual(cpp.count('DUT d{&context}'),1)
        self.assertLess(cpp.index('gfn16_runtime::configure(context,argc,argv)'),cpp.index('DUT d{&context}'))
        watch=cpp[cpp.index('static void watchdog_expiry'):cpp.index('int main')]
        self.assertNotIn('!d.probe_slots',watch)
        self.assertIn('!d.command_accept',watch)
        self.assertIn('!d.done&&!d.canonical_ready&&!d.read_valid',watch)
        self.assertEqual(m['steps'][0]['expected_stdout'],own.FOOTER)
        self.assertIn('raw_tails_allowed=1',own.FOOTER)
        self.assertEqual(m['steps'][1]['expected_returncode'],1)


if __name__=='__main__':unittest.main()
