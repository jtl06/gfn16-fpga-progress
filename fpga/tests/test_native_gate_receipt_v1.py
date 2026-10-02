import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from fpga.tools import native_gate_receipt_v1 as g

ROOT=Path(__file__).resolve().parents[1]


class GateTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name).resolve()/'native'
        source=ROOT/'queue/evidence/t5b-e2e1-q1-v1/attempt-0/collected/output/native'
        shutil.copytree(source,self.root)
        self.path=self.root/'report.json';self.report=json.loads(self.path.read_text())
        self.contract=g.make_contract('T5b-E2E1',self.root/'approved-manifest.json')
    def validate(self):return g.validate_result(self.contract,self.path,id='logical-e2e')
    def write_report(self,value):self.path.write_text(json.dumps(value))
    def test_actual_typed_normal_and_nonzero_mutants(self):
        value=self.validate();self.assertEqual(value['status'],'PASS_expected_contracts')
        self.assertEqual([s['expected_returncode'] for s in value['steps']],[0,1,1])
        self.assertTrue(all(s['typed_validator_sha256'] for s in value['steps']))
        self.assertFalse(value['promotion_allowed'])
    def test_zero_exit_cannot_replace_expected_negative(self):
        report=copy.deepcopy(self.report);report['steps'][-1]['returncode']=0;self.write_report(report)
        with self.assertRaises(ValueError):self.validate()
    def test_failed_worker_or_missing_validator_rejects(self):
        for kind in ('status','validator','probe','manifest'):
            report=copy.deepcopy(self.report)
            if kind=='status':report['status']='failed_native_commands'
            elif kind=='validator':report['validations'].pop(next(iter(report['validations'])))
            elif kind=='probe':report['probe']['model_threads']=True
            else:report['manifest_sha256']='f'*64
            self.write_report(report)
            with self.assertRaises(ValueError):self.validate()
    def test_artifact_or_case_drift_rejects(self):
        name=self.report['steps'][-1]['log'];(self.root/name).write_text('altered')
        with self.assertRaises(ValueError):self.validate()
    def test_wrong_selector_even_with_expected_exit_rejects(self):
        report=copy.deepcopy(self.report);report['steps'][-1]['command'].append('--different-case');self.write_report(report)
        with self.assertRaises(ValueError):self.validate()
    def test_contract_mutation_and_raw_lint_success_are_not_gate(self):
        self.contract['candidate_id']='changed'
        with self.assertRaises(ValueError):self.validate()
        m=json.loads((self.root/'approved-manifest.json').read_text());m['phase']='lint'
        path=self.root/'lint-manifest.json';path.write_text(json.dumps(m))
        with self.assertRaises(ValueError):g.make_contract('not-native',path)


if __name__=='__main__':unittest.main()
