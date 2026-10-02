import json
from pathlib import Path
import tempfile
import unittest
from fpga.reference import a10_point_field_probe_v3 as probe


class PointFitProbe(unittest.TestCase):
    def test_matched_sources_only_point_and_shell_name(self):
        before,_=probe.parent.source_inputs();after,receipt=probe.source_inputs()
        self.assertEqual(len(after),9)
        for name,raw in before.items():
            if name not in (probe.parent.TOP+'.sv',Path(probe.candidate.batch.repair.ENGINE_V2).name):self.assertEqual(after[name],raw)
        self.assertEqual(receipt['child_sha256'],probe.parent.CHILD_SHA)
        self.assertEqual((receipt['request_added_edges'],receipt['response_added_edges']),(1,1))

    def test_plain_source_project_checks_both_worker_modes(self):
        plain=probe.parent.load_exact(probe.parent.PLAIN,probe.parent.PLAIN_SHA,'_point_fit_test')
        for workers in (4,6):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp).resolve();project=root/'project';result=probe.prepare(project,workers)
                (root/'run-aws-fit-v6.sh').write_text('# pure source fixture\n')
                runner=plain.runner(dict(root=str(root),workers=workers,memory=20<<30,slots={'a':list(range(workers))}),'gfn16-aws-m8i',False)
                self.assertEqual(runner.verify_project(project)['manifest_sha256'],result['manifest_sha256'])
                self.assertEqual((project/'probe.sdc').read_text(),probe.parent.SDC)
                self.assertEqual((project/'run.tcl').read_text(),plain.FULL_TCL)
                m=json.loads((project/'manifest.json').read_text())
                self.assertTrue(m['new_child_full_N_native_gate_pending'])
                self.assertFalse(m['vendor_executed'])
                self.assertEqual(m['source_only_point_ledger']['point_cycles'],1032)
                qsf=(project/'probe.qsf').read_text();(project/'probe.qsf').write_text(qsf.replace('-name AW 16','-name AW 8'))
                with self.assertRaisesRegex(Exception,'parameter mismatch'):runner.verify_project(project)


if __name__=='__main__':unittest.main()
