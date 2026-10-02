import json,tempfile,unittest
from pathlib import Path
from fpga.reference.anext_plain_fit_prepare_v1 import ROOT,ROLE,prepare,FULL_TCL
from fpga.tools.prefit_structural_guard_v1 import source_inventory

class CompositeFit(unittest.TestCase):
    def test_exact_native_sources_and_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            for period in ('9.668','8.0'):
                out=(Path(tmp)/period).resolve();r=prepare(out,period);p=out/'project';m=json.loads((p/'manifest.json').read_text())
                native=json.loads((ROOT/ROLE/'manifest.json').read_text())
                self.assertEqual(m['source_sha256'],{Path(n).name:native['sources'][n] for n in native['build']['sv_sources']})
                self.assertEqual(len(m['source_sha256']),30);self.assertEqual(m['compile_processors'],4)
                self.assertEqual((p/'run.tcl').read_text(),FULL_TCL)
                self.assertEqual(r['structural_result']['findings'],[])
                spec=json.loads((out/'inventory.json').read_text());spec['identity']['parameters']['AW']=8
                with self.assertRaises(ValueError):source_inventory(p,spec)
            with self.assertRaises(ValueError):prepare(Path(tmp)/'bad','7.0')

if __name__=='__main__':unittest.main()
