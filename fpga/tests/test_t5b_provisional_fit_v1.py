"""Pure admission tests; never invokes native HDL, Quartus or cloud APIs."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

FPGA=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('prepare_t5b',FPGA/'synthesis/prepare_t5b_provisional_v1.py')
prep=importlib.util.module_from_spec(spec);spec.loader.exec_module(prep)
fit=prep.adapter


class Admission(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.output=Path(self.temp.name).resolve()/'packet';prep.prepare(self.output)
        self.project=self.output/'project'

    def change(self,**values):
        p=self.project/'manifest.json';m=json.loads(p.read_text());m.update(values);p.write_text(json.dumps(m))

    def test_exact_one_rtl_delta_and_six_workers(self):
        result=fit.verify_project(self.project)
        self.assertEqual(len(result['source_sha256']),16)
        self.assertEqual(result['qsf_parameters'],dict(AW=16,NTT_LANES=64))
        self.assertFalse(result['promotion_allowed'])
        self.assertEqual(json.loads((self.project/'manifest.json').read_text())['compile_processors'],6)

    def test_promotion_refused(self):
        self.change(promotion_allowed=True)
        with self.assertRaisesRegex(ValueError,'promotion lock'):fit.verify_project(self.project)

    def test_false_completeness_refused(self):
        self.change(T5b_correctness_complete=True)
        with self.assertRaisesRegex(ValueError,'promotion lock'):fit.verify_project(self.project)

    def test_runtime_comparison_mislabel_refused(self):
        self.change(runtime_single_variable_comparison=True)
        with self.assertRaisesRegex(ValueError,'comparison disclosure'):fit.verify_project(self.project)

    def test_old_worker_count_refused(self):
        self.change(compile_processors=4)
        with self.assertRaisesRegex(ValueError,'mode-matched Quartus workers'):fit.verify_project(self.project)

    def test_repin_cannot_change_rtl(self):
        p=self.project/'rtl'/(fit.TOP+'.sv');p.write_text(p.read_text()+'\n// arbitrary change\n')
        m=json.loads((self.project/'manifest.json').read_text());m['source_sha256'][p.name]=fit.digest(p.read_bytes())
        self.change(source_sha256=m['source_sha256'])
        with self.assertRaisesRegex(ValueError,'one-file T5b source closure'):fit.verify_project(self.project)

    def test_repin_cannot_change_qsf_seed(self):
        p=self.project/'probe.qsf';p.write_text(p.read_text().replace('SEED 1','SEED 2'))
        m=json.loads((self.project/'manifest.json').read_text());m['control_sha256']['probe.qsf']=fit.digest(p.read_bytes())
        self.change(control_sha256=m['control_sha256'])
        with self.assertRaisesRegex(ValueError,'exact top/workers-only QSF'):fit.verify_project(self.project)

    def test_unchanged_sdc_required(self):
        p=self.project/'probe.sdc';p.write_text(p.read_text().replace('-period 10','-period 8'))
        with self.assertRaisesRegex(ValueError,'unchanged parent probe.sdc'):fit.verify_project(self.project)

    def test_assembler_disallowed(self):
        self.change(allowed_stages=['syn','fit','sta','asm'])
        with self.assertRaisesRegex(ValueError,'compute-only'):fit.verify_project(self.project)

    def test_existing_execution_refused(self):
        (self.project/'execution-context.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'existing execution'):fit.verify_project(self.project)

    def test_evidence_drift_refused(self):
        p=self.project/'evidence/aw16-normal-review.json';p.write_text(p.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'evidence identity'):fit.verify_project(self.project)

    def test_extra_evidence_refused(self):
        (self.project/'evidence/unbound.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'evidence directory closure'):fit.verify_project(self.project)

    def test_outer_policy_is_not_bypassed(self):
        with mock.patch.object(fit.policy,'launch',return_value=19) as outer:
            self.assertEqual(fit.launch('fresh-t5b','a',Path('/not/executed.json')),19)
            outer.assert_called_once_with('fresh-t5b','a',Path('/not/executed.json'))
            self.assertIs(fit.base.launch,fit.launch_inner)
        with self.assertRaisesRegex(ValueError,'benchmark mode excluded'):
            fit.launch('fresh-t5b','bench',Path('/not/executed.json'))


if __name__=='__main__':unittest.main()
