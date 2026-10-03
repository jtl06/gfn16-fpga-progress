"""Scope-correct successor is distinct from preserved v2 native failure."""
import unittest
from fpga.reference import stream27_context_storage_combo_transport11_control_v3 as v3
from fpga.reference import stream27_context_storage_combo_transport11_control as v2


class Transport11ControlV3Tests(unittest.TestCase):
    def test_reset_flush_and_watch_public_mask_distinction(self):
        old,oldfiles=v2.role()
        new,files=v3.role()
        self.assertEqual(old['build']['parameters'],new['build']['parameters'])
        self.assertEqual(old['build']['sv_sources'],new['build']['sv_sources'])
        for name in new['build']['sv_sources']:
            self.assertEqual(oldfiles[name],files[name])
        cpp=files[v3.CPP].decode()
        reset=cpp[cpp.index('static void reset_seam'):cpp.index('static void watchdog_expiry')]
        watch=cpp[cpp.index('static void watchdog_expiry'):cpp.index('int main')]
        self.assertIn('!d.probe_slots&&!d.probe_starts',reset)
        self.assertNotIn('!d.probe_slots',watch)
        self.assertNotIn('!d.probe_starts',watch)
        self.assertIn('!d.command_accept',watch)
        self.assertIn('!d.busy&&!d.done&&!d.canonical_ready&&!d.read_valid',watch)
        self.assertIn('WATCHDOG_AGE=64*N+4096-1',watch)
        self.assertNotIn('probe_stop=',cpp)
        self.assertNotIn('lean_watchdog_error=',cpp)
        self.assertLess(cpp.index('gfn16_runtime::configure(context,argc,argv)'),cpp.index('DUT d{&context}'))
        self.assertIn('raw_tails_allowed=1',new['steps'][0]['expected_stdout'])
        self.assertTrue(new['transport11_control']['predecessor_v2_failure_preserved'])
        self.assertFalse(new['transport11_control']['host_watch_intrinsic_raw_tail_flush_claim'])
        self.assertFalse(new['transport11_control']['protected_fault_rollback_claim'])


if __name__=='__main__':unittest.main()
