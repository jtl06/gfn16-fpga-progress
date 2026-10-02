"""Read-only preflight plus isolated copied-project mutation rejection."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from fpga.cloud import aws_fit_a4_provisional_v1 as adapter

PROJECT=Path(__file__).resolve().parents[1]/'results/throughput-20260929/track-a4-p4-provisional-fit-stage-v1/project'


class A4ProjectGuardTests(unittest.TestCase):
    def test_frozen_stage_preflight(self):
        self.assertEqual(adapter.verify_project(PROJECT)['qsf_parameters'],{'AW':16})

    def test_promotion_workers_geometry_mutations(self):
        for key,value in (('promotion_allowed',True),('A4_correctness_complete',True),('compile_processors',4),
                          ('clock_period_ns',9.6),('host_changed_from_parent',False),('concurrent_fit_admitted',True)):
            with tempfile.TemporaryDirectory(prefix='a4-fit-guard-') as temporary:
                copy=Path(temporary)/'project';shutil.copytree(PROJECT,copy)
                path=copy/'manifest.json';manifest=json.loads(path.read_text());manifest[key]=value
                path.write_text(json.dumps(manifest))
                with self.assertRaises(ValueError,msg=key):adapter.verify_project(copy)


if __name__=='__main__':unittest.main()
