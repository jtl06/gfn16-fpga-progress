"""Own source/ABI contract checks only; no native or numerical execution."""
import unittest
from fpga.reference import stream27_context_storage_combo_readlocal_fault as fault


class FaultRoles(unittest.TestCase):
    def test_actual_aw8_gate_and_closed_rtl(self):
        import json
        original=json.loads((fault.NORMAL/'manifest.json').read_bytes())
        normal={name:(fault.NORMAL/'source/fpga'/name).read_bytes() for name in original['build']['sv_sources']}
        for mode in fault.MODES:
            m,f=fault.role(mode)
            if mode=='early-cache':
                delta=m['storage2_fault']['diagnostic_rtl_delta']
                self.assertEqual(len(delta),2)
                # Keep the original term for F1/F2 while F0 selects its sole probe.
                self.assertEqual(f[delta[0]],normal[delta[0]])
                self.assertIn(delta[0],m['build']['sv_sources'])
                self.assertEqual(len(m['build']['sv_sources']),56)
                self.assertIn('premature_cache_rejected=1',m['steps'][0]['expected_stdout'])
            else:
                self.assertEqual(len(m['build']['sv_sources']),55)
                self.assertTrue(all(f[n]==raw for n,raw in normal.items()))
                self.assertTrue(m['storage2_fault']['production_rtl_unchanged'])
            step=m['steps'][0]
            self.assertEqual(step['expected_returncode'],1 if mode=='oracle' else 0)
            self.assertTrue((step['expected_stderr'] if mode=='oracle' else step['expected_stdout']).endswith('\n'))
            self.assertFalse(m['storage2_fault']['shared_fault_peer_recovery'])
            self.assertEqual(m['storage2_fault']['full_owner_bits'],27)

    def test_unknown_mode_fails(self):
        with self.assertRaises(ValueError):fault.role('arbitrary-faults')


if __name__=='__main__':unittest.main()
