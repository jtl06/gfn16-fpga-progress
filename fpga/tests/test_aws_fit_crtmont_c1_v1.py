import json
from pathlib import Path
import tempfile
import unittest
from fpga.cloud import aws_fit_crtmont_c1_v1 as c


class C1Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.output=Path(self.temp.name).resolve()/'stage'
        self.ticket=c.prepare(self.output)
        self.project=self.output/c.PROBE

    def tearDown(self): self.temp.cleanup()

    def test_exact_delta(self):
        context=c.verify_project(self.project)
        self.assertEqual(len(context['source_sha256']),16)
        self.assertEqual(c.worker.final_inputs(self.project,context),[])
        self.assertIn('-period 8 ',(self.project/'probe.sdc').read_text())
        self.assertIn('SEED 1\n',(self.project/'probe.qsf').read_text())
        self.assertEqual(len(self.ticket['files']),31)

    def test_reject_rtl_drift(self):
        path=next((self.project/'rtl').iterdir());path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaises(ValueError): c.verify_project(self.project)

    def test_reject_exception(self):
        path=self.project/'probe.sdc';path.write_text(path.read_text()+'set_false_path -to [all_registers]\n')
        with self.assertRaises(ValueError): c.verify_project(self.project)

    def test_reject_manifest_promotion(self):
        path=self.project/'manifest.json';value=json.loads(path.read_text());value['promotion_allowed']=True
        path.write_text(json.dumps(value))
        with self.assertRaises(ValueError): c.verify_project(self.project)

    def test_reject_existing_execution(self):
        (self.project/'execution-context.json').write_text('{}')
        with self.assertRaises(ValueError): c.verify_project(self.project)

    def test_reject_worker_or_seed_change(self):
        path=self.project/'probe.qsf';path.write_text(path.read_text().replace('SEED 1','SEED 2'))
        with self.assertRaises(ValueError): c.verify_project(self.project)


if __name__=='__main__':unittest.main()
