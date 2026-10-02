import json,tempfile,unittest
from pathlib import Path
from fpga.reference.anext_soak_prepare_v1 import prepare,sha,ROOT,BASE,BASE_SHA

class SoakPreparation(unittest.TestCase):
    def test_closed_candidate_and_isolated_donor(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'capture';result=prepare(out)
            self.assertFalse(result['promotion_allowed']);self.assertEqual(result['operations'],2)
            m=json.loads((out/'manifest.json').read_text());parent=json.loads((ROOT/BASE/'manifest.json').read_text())
            self.assertEqual(sha((ROOT/BASE/'manifest.json').read_bytes()),BASE_SHA)
            self.assertEqual(m['build']['sv_sources'],parent['build']['sv_sources'])
            for name in m['build']['sv_sources']:self.assertEqual(m['sources'][name],parent['sources'][name])
            for name,pin in m['sources'].items():self.assertEqual(sha((out/'source/fpga'/name).read_bytes()),pin)
            self.assertEqual([s['expected_returncode'] for s in m['steps']],[0,1,1])
            self.assertTrue(all(s['validator']['assets']['runtime'].startswith('donor/fpga/') for s in m['steps']))
            with self.assertRaises(ValueError):prepare(out)

if __name__=='__main__':unittest.main()
