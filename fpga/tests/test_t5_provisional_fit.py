"""Offline admission and negative controls; no HDL or vendor tools invoked."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

FPGA = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('t5_fit',FPGA/'cloud/aws_fit_t5_provisional_v1.py')
fit = importlib.util.module_from_spec(spec); spec.loader.exec_module(fit)
PACKAGE = FPGA/'results/throughput-20260929/core27-t5-provisional-fit-stage-v1/project'


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name).resolve()/'project'
        shutil.copytree(PACKAGE,self.project)

    def update_manifest(self, **fields):
        path = self.project/'manifest.json'
        m = json.loads(path.read_text()); m.update(fields)
        path.write_text(json.dumps(m))

    def test_exact_package(self):
        result = fit.verify_project(self.project)
        self.assertTrue(result['provisional'])
        self.assertFalse(result['promotion_allowed'])
        self.assertEqual(len(result['source_sha256']),16)

    def test_promotion_unlock_rejected(self):
        self.update_manifest(promotion_allowed=True)
        with self.assertRaisesRegex(ValueError,'promotion lock'): fit.verify_project(self.project)

    def test_source_drift_rejected(self):
        path = self.project/'rtl'/(fit.TOP+'.sv')
        path.write_text(path.read_text()+'\n// drift\n')
        with self.assertRaisesRegex(ValueError,'source SHA'): fit.verify_project(self.project)

    def test_control_drift_rejected(self):
        path = self.project/'probe.sdc'
        path.write_text(path.read_text().replace('-period 10','-period 8'))
        with self.assertRaisesRegex(ValueError,'control SHA'): fit.verify_project(self.project)

    def test_evidence_drift_rejected(self):
        path = self.project/'evidence/T5-normal-report.json'
        path.write_text(path.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'evidence identity'): fit.verify_project(self.project)

    def test_false_gate_completion_rejected(self):
        self.update_manifest(T5_correctness_complete=True)
        with self.assertRaisesRegex(ValueError,'promotion lock'): fit.verify_project(self.project)

    def test_extra_source_rejected(self):
        (self.project/'rtl/extra.sv').write_text('// extra\n')
        with self.assertRaisesRegex(ValueError,'closure mismatch'): fit.verify_project(self.project)

    def test_previous_execution_rejected(self):
        (self.project/'execution-context.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'existing execution'): fit.verify_project(self.project)

    def test_noncompute_stage_rejected(self):
        self.update_manifest(allowed_stages=['syn','fit','sta','asm'])
        with self.assertRaisesRegex(ValueError,'compute-only'): fit.verify_project(self.project)

    def test_source_self_repin_rejected(self):
        path = self.project/'rtl'/(fit.TOP+'.sv')
        path.write_text(path.read_text()+'\n// substituted\n')
        m = json.loads((self.project/'manifest.json').read_text())
        m['source_sha256'][path.name] = fit.digest(path.read_bytes())
        self.update_manifest(source_sha256=m['source_sha256'])
        with self.assertRaisesRegex(ValueError,'two-file T5 source closure'): fit.verify_project(self.project)


if __name__ == '__main__': unittest.main()
