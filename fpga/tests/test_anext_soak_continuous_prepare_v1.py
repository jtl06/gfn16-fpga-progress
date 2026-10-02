import json,tempfile,unittest
from pathlib import Path
from fpga.reference.anext_soak_continuous_prepare_v1 import prepare,ROOT

class ContinuousSource(unittest.TestCase):
    def test_retained_1000_role_not_chunk_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'capture';r=prepare(out);m=json.loads((out/'manifest.json').read_text())
            p=json.loads((out/'source/fpga/donor/reference/plan.json').read_text())
            self.assertEqual((r['operations'],r['expected_prefill_cold'],r['expected_cache_hits']),(1000,10,999))
            self.assertEqual(p['checkpoints'],list(range(0,1001,100)))
            self.assertEqual(len(m['steps']),1);self.assertEqual(m['steps'][0]['validator']['config'],{'negative':'none'})
            self.assertFalse(any(n.startswith('donor/reference/chunk-') for n in m['sources']))
            short=json.loads((ROOT/'artifacts/anext-soak-short-aw16-role-v1/manifest.json').read_text())
            for n in m['build']['sv_sources']+['rtl/tb/anext_soak_v1.cpp','reference/anext_soak_output_v1.py']:
                self.assertEqual(m['sources'][n],short['sources'][n])
            self.assertEqual(m['build'],short['build'])

if __name__=='__main__':unittest.main()
