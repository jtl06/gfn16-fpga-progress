import json,tempfile,unittest
from pathlib import Path
from fpga.reference import anext_point_fit_prepare_v1 as m
class PointFit(unittest.TestCase):
    def test_exact_role_and_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'fit';r=m.prepare(out);p=out/'project';a=m.ROOT/m.PARENT/'project'
            manifest=json.loads((p/'manifest.json').read_text());role=json.loads((m.ROOT/m.ROLE/'manifest.json').read_text())
            self.assertEqual(manifest['source_sha256'],{Path(n).name:role['sources'][n] for n in role['build']['sv_sources']})
            for name in ('probe.sdc','run.tcl','probe.qpf'):self.assertEqual((p/name).read_bytes(),(a/name).read_bytes())
            self.assertEqual((p/'probe.qsf').read_text(),m.rename((a/'probe.qsf').read_text()))
            self.assertEqual(r['structural_result']['findings'],[]);self.assertFalse(r['fit_launched'])
            self.assertNotIn('native_report_sha256',manifest)
            self.assertEqual(manifest['required_native_gate'],m.REQUIRED)
            spec=json.loads((out/'inventory.json').read_text());spec['identity']['parameters']['AW']=8
            with self.assertRaises(ValueError):m.source_inventory(p,spec)
if __name__=='__main__':unittest.main()
