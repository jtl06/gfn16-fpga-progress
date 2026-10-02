import json,tempfile,unittest
from pathlib import Path
from fpga.reference.anext_soak_chunk00_prepare_v1 import prepare,ROOT
class ChunkPilot(unittest.TestCase):
    def test_exact_known_data_not_continuous_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'capture';r=prepare(out);m=json.loads((out/'manifest.json').read_text())
            short=json.loads((ROOT/'artifacts/anext-soak-short-aw16-role-v1/manifest.json').read_text())
            self.assertEqual((r['operations'],r['expected_prefill_cold'],r['expected_cache_hits']),(100,1,99))
            self.assertFalse(r['uninterrupted_1000_gate']);self.assertEqual(len(m['steps']),1)
            self.assertEqual(m['steps'][0]['validator']['assets']['oracle'],'donor/reference/chunk-00.json')
            self.assertEqual(m['build'],short['build'])
            for name in m['build']['sv_sources']+[m['build']['cpp_source'],'reference/anext_soak_output_v1.py']:
                self.assertEqual(m['sources'][name],short['sources'][name])
if __name__=='__main__':unittest.main()
