import json,tempfile,unittest
from pathlib import Path
from fpga.reference.track_a4b_plain_fit_prepare_v1 import ROOT,PARENT,SPEC,prepare,FULL_TCL
from fpga.tools.prefit_structural_guard_v1 import source_inventory

class PlainA4b(unittest.TestCase):
    def test_exact_source_settings_and_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            out=(Path(temp)/'fresh').resolve();r=prepare(out);p=out/'project'
            self.assertEqual(r['rtl_changes'],0);self.assertFalse(r['fit_launched'])
            old=json.loads((ROOT/PARENT/'manifest.json').read_text());new=json.loads((p/'manifest.json').read_text())
            self.assertEqual(old['source_sha256'],new['source_sha256'])
            self.assertEqual((p/'run.tcl').read_text(),FULL_TCL)
            self.assertEqual((p/'probe.qsf').read_text(),(ROOT/PARENT/'probe.qsf').read_text()+'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON\n')
            a=json.loads((ROOT/SPEC).read_text());b=json.loads((out/'inventory.json').read_text());a.pop('settings');b.pop('settings');self.assertEqual(a,b)
            spec=json.loads((out/'inventory.json').read_text())
            self.assertEqual(source_inventory(p,spec)['findings'],[])
            spec['identity']['seed']=2
            with self.assertRaises(ValueError):source_inventory(p,spec)
            with self.assertRaises(ValueError):prepare(out)

if __name__=='__main__':unittest.main()
