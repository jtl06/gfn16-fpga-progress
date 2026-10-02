import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from fpga.cloud import gcp_postfit_p2_100_v1 as p


class P2AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.out=Path(self.temp.name).resolve()/'tools'
        self.receipt=p.prepare(self.out)

    def tearDown(self):self.temp.cleanup()

    def test_proposal_replay(self):
        # Model the immutable staged helper location without executing a tool.
        with patch.object(p,'HERE',self.out),patch.object(p,'__file__',str(self.out/Path(p.__file__).name)):
            data=p.verify_proposal(self.out/'proposal.json',self.receipt['proposal_sha256'])
        self.assertEqual(data['period_ns'],'10');self.assertEqual(len(data['pinned_files']),22)
        self.assertEqual(len(data['source_sha256']),10)
        self.assertEqual(data['baseline100']['setup']['slack_ns'],0.559)

    def test_only_sta_final_snapshot(self):
        text=(self.out/'postfit_p2_100_v1.tcl').read_text()
        self.assertIn('create_timing_netlist -model slow -snapshot final',text)
        self.assertIn('$a1_mode ne "diagnosis" || $a1_period != 10',text)
        self.assertNotIn('execute_module',text)
        self.assertIn('set path_count 1000',text)
        self.assertIn('project_close -dont_export_assignments',text)

    def test_reject_sdc_mutation(self):
        with self.assertRaises(ValueError):p.script((self.out/'postfit_rootfused85_audit_v1.tcl').read_bytes(),b'set_false_path -to *')

    def test_reject_script_mutation(self):
        path=self.out/'postfit_p2_100_v1.tcl';path.write_bytes(path.read_bytes()+b'\n')
        with patch.object(p,'HERE',self.out),patch.object(p,'__file__',str(self.out/Path(p.__file__).name)):
            with self.assertRaises(ValueError):p.verify_proposal(self.out/'proposal.json',self.receipt['proposal_sha256'])

    def test_reject_promotion_even_rehashed(self):
        path=self.out/'proposal.json';value=json.loads(path.read_text());value['promotion_allowed']=True
        path.write_text(json.dumps(value))
        with patch.object(p,'HERE',self.out),patch.object(p,'__file__',str(self.out/Path(p.__file__).name)):
            with self.assertRaises(ValueError):p.verify_proposal(path,p.digest(path.read_bytes()))


if __name__=='__main__':unittest.main()
