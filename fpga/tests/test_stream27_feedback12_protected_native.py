"""Own protected mode source/normal metadata tests; no native/RTL replay."""
import json
from pathlib import Path
import unittest
from fpga.reference import stream27_feedback12_protected_native as own


class ProtectedModeTests(unittest.TestCase):
    def test_both_frozen_captures_have_own_protected_contract(self):
        root=own.ROOT/'results/throughput-20260929/trackS-c2-feedback12-protected-native-v1'
        for stage, interval, first in (('aw8',218,[204,313]), ('full',8464,[204,4436])):
            directory=root/(stage+'-normal')
            m=json.loads((directory/'manifest.json').read_bytes())
            b=json.loads((directory/'production-bundle.json').read_bytes())
            self.assertEqual(len(b['files']),58)
            self.assertEqual(len(m['build']['sv_sources']),58+(stage=='full'))
            self.assertNotIn('LEAN_PRODUCTION',m['build']['parameters'])
            self.assertEqual(m['build']['parameters']['LEAN_PROGRESS_WATCHDOG'],0)
            self.assertEqual(m['build']['parameters'],dict(b['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42))
            for flag in ('CRT_TRANSPORT_REG','INVERSE_INGRESS_REG','TERM_JOIN_TRANSPORT_REG',
                    'FEEDBACK_INGRESS_REG','AUTO_CORRECTION_INGRESS_REG','C0_ADMISSION_DIRECT'):
                self.assertEqual(m['build']['parameters'][flag],1)
            self.assertEqual(b['geometry']['warm_interval'],interval)
            self.assertEqual(b['context_feedback12']['source_declared_cold_first_edges'],first)
            self.assertFalse(b['context_feedback12']['lean_production'])
            self.assertEqual(m['rtl_readiness']['rtl_ready_at_utc'],own.READY)
            self.assertTrue(m['context_feedback12']['donor_results_not_inherited'])
            self.assertTrue(m['context_feedback12']['protected_mode_source_restored'])
            for name,body in b['files'].items():
                raw=(directory/'source/fpga/rtl'/name).read_bytes()
                self.assertEqual(raw,body.encode())
                self.assertEqual(m['sources']['rtl/'+name],own.sha(raw))
            cpp=(directory/'source/fpga'/m['build']['cpp_source']).read_text()
            own.runtime_before_model(cpp)
            if stage=='full':
                observer=(directory/'source/fpga/rtl'/(m['build']['top']+'.sv')).read_text()
                self.assertNotIn('LEAN_PRODUCTION',observer)
                self.assertIn('LEAN_PROGRESS_WATCHDOG=0,',observer)
                self.assertNotIn('always_ff',observer)
                self.assertFalse(m['steps'][0]['validator']['config']['lean_production'])


if __name__=='__main__': unittest.main()
