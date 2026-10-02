import tempfile,json,unittest
from pathlib import Path
from fpga.reference import anext_hostcut_fit_prepare_v1 as m
class HostcutFit(unittest.TestCase):
    def test_only_bound_cell_and_names_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            for workers in (4,6):
                out=Path(tmp)/str(workers);r=m.prepare(out,workers);p=out/'project';base=m.ROOT/m.PARENTS[workers][0]/'project'
                for n in ('probe.sdc','run.tcl','probe.qpf'):self.assertEqual((p/n).read_bytes(),(base/n).read_bytes())
                self.assertEqual((p/'probe.qsf').read_text(),m.rename((base/'probe.qsf').read_text()))
                role=json.loads((m.ROOT/m.ROLE/'manifest.json').read_text());manifest=json.loads((p/'manifest.json').read_text())
                self.assertEqual(manifest['source_sha256'],{Path(n).name:role['sources'][n] for n in role['build']['sv_sources']})
                self.assertEqual(manifest['required_native_gate'],m.REQUIRED);self.assertFalse(r['fit_launched'])
                self.assertEqual(r['structural_result']['findings'],[])
            with self.assertRaises(ValueError):m.prepare(Path(tmp)/'bad',8)
if __name__=='__main__':unittest.main()
