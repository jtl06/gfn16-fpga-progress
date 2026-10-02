"""r4 local preparation/controls only; never run Quartus/cloud."""
import hashlib
import json
from pathlib import Path
import tempfile
import tarfile
import unittest
from unittest.mock import patch
from fpga.synthesis import prepare_core27_rootfused_crtmont_fit as p
from fpga.cloud import aws_fit_v6 as worker

ROOT=Path(__file__).resolve().parents[1]


class DirectWhole64FitTests(unittest.TestCase):
    def test_full_project_exact_parent_controls_and_v6(self):
        before=p.inputs.checked_inputs(ROOT)
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp).resolve()/'stage';receipt=p.prepare(directory);project=directory/'project'
            c=worker.verify_project(project);m=json.loads((project/'manifest.json').read_bytes())
            self.assertEqual(c['qsf_parameters'],{'AW':16,'NTT_LANES':64});self.assertEqual(len(c['source_sha256']),16)
            self.assertEqual(m['allowed_stages'],['syn','fit','sta']);self.assertTrue(m['G4_AW16_normal_qualified'])
            self.assertFalse(m['physical_fit_qualified']);self.assertEqual(m['clock_period_ns'],10);self.assertEqual(m['seed'],1)
            for n in ('probe.qpf','probe.sdc','run.tcl'):self.assertEqual((project/n).read_bytes(),before[2][n])
            for n in before[1]:
                if n not in (p.inputs.OLD_TOP+'.sv',p.inputs.OLD_CRT+'.sv'):
                    self.assertEqual((project/'rtl'/n).read_bytes(),before[1][n])
            top=(project/'rtl'/(p.inputs.NEW_TOP+'.sv')).read_bytes()
            self.assertEqual(top.replace(p.inputs.NEW_TOP.encode(),p.inputs.OLD_TOP.encode()).replace(
                (p.inputs.NEW_CRT+' crt (').encode(),(p.inputs.OLD_CRT+' crt (').encode()),before[1][p.inputs.OLD_TOP+'.sv'])
            self.assertNotIn('aws_syn_v1.py',[x.name for x in (directory/'tools').iterdir()])
            self.assertEqual(receipt['status'],'fullfit_r4_prepared_not_dispatched')
            self.assertFalse((project/'output_files').exists())
        self.assertEqual(before,p.inputs.checked_inputs(ROOT))

    def test_closed_archive_and_fresh_only(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp).resolve()/'stage';receipt=p.prepare(directory)
            with tarfile.open(directory/'source.tar.gz') as tar:
                self.assertEqual(set(tar.getnames()),set(receipt['input_sha256'])|{'manifest.json'})
                self.assertEqual(len(tar.getmembers()),32)
                self.assertTrue(all(x.isfile() for x in tar))
                for name,pin in receipt['input_sha256'].items():self.assertEqual(hashlib.sha256(tar.extractfile(name).read()).hexdigest(),pin)
            with self.assertRaises(FileExistsError):p.prepare(directory)

    def test_required_r4_and_independent_receipt_pin_fail_before_output(self):
        for key in ('R4_SHA','G4_REVIEW_SHA','V6_SHA'):
            with tempfile.TemporaryDirectory() as temp,patch.object(p,key,'0'*64):
                directory=Path(temp).resolve()/'stage'
                with self.assertRaises(ValueError):p.prepare(directory)
                self.assertFalse(directory.exists())

    def test_preserved_syn_frozen_pins(self):
        stage=ROOT/'results/throughput-20260929/core27-rootfused-crtmont64-syn-pair-v1'
        self.assertEqual(p.digest((stage/'manifest.json').read_bytes()) if (stage/'manifest.json').exists() else
                         p.digest((stage/'pair.json').read_bytes()),'084409a808684d5afc64d47b670abdd24e5cd058d1ff33955751bba9f19af7c8')
        self.assertEqual(p.digest((stage/'source.tar.gz').read_bytes()),'c70e1f68238a2ebc4d0ea018efd553272f53370f9ba30bb87ee62d4ed24ecd3b')
        self.assertEqual(p.digest((ROOT/'cloud/aws_syn_v1.py').read_bytes()),'60549face0b6f17ef8e39b25ab78c2862c3cbf96b52b6202636a99e73f5b6ceb')


if __name__=='__main__':unittest.main()
