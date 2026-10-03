import json
from pathlib import Path
import unittest
from fpga.reference.stream27_r15_direct_cold_bind import bind as previous
from fpga.reference.stream27_r15_direct_cold_bind_v2 import bind

ROOT=Path(__file__).resolve().parents[1]


class ContainmentTests(unittest.TestCase):
    def test_exact_reversal_and_public_authority(self):
        for role in ('aw8-normal','full-normal-v2'):
            b=json.loads((ROOT/'results/throughput-20260929/trackS-c2-protected-field100-native-v1'/role/'production-bundle.json').read_text())
            self.assertEqual(bind(b),b)
            out=bind(b,direct_cold=1);old=previous(b,direct_cold=1)
            text=out['files'][out['top']+'.sv']
            self.assertEqual(len(out['files']),63)
            self.assertTrue(all(out['files'][k]==v for k,v in b['files'].items()))
            for a,z in reversed(out['r15_direct_cold']['global_fault_containment']['edits']):
                self.assertEqual(text.count(z),1);text=text.replace(z,a,1)
            self.assertEqual(text,old['files'][old['top']+'.sv'])
            active=out['files'][out['top']+'.sv']
            for name in ('command_ready','command_accept','operation_accept','done','warm_done','busy','read_valid','canonical_ready'):
                assignment=next(s for s in active.split(';') if 'assign '+name+'=' in s)
                self.assertIn('host_authority',assignment)
            self.assertIn('.command_valid(command_valid && rst_n && dc_link_drained && !dc_error)',active)


if __name__=='__main__':unittest.main()
