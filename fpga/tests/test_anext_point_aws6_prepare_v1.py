import json,tempfile,unittest
from pathlib import Path
from fpga.reference import anext_point_aws6_prepare_v1 as m
class AWS6(unittest.TestCase):
    def test_only_worker_setting_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'six';r=m.prepare(out);p=out/'project';base=m.ROOT/m.BASE/'project'
            a=json.loads((base/'manifest.json').read_text());b=json.loads((p/'manifest.json').read_text())
            self.assertEqual(a['source_sha256'],b['source_sha256']);self.assertEqual(len(b['source_sha256']),30)
            for name in ('probe.sdc','probe.qpf','run.tcl'):self.assertEqual((base/name).read_bytes(),(p/name).read_bytes())
            self.assertEqual((p/'probe.qsf').read_text().replace('NUM_PARALLEL_PROCESSORS 6','NUM_PARALLEL_PROCESSORS 4'),(base/'probe.qsf').read_text())
            self.assertEqual(a['required_native_gate'],b['required_native_gate']);self.assertFalse(r['fit_launched'])
            # Reusing four-worker controls under six-worker manifest must reject.
            (p/'probe.qsf').write_bytes((base/'probe.qsf').read_bytes())
            with self.assertRaises(ValueError):m.verify_project(p)
if __name__=='__main__':unittest.main()
