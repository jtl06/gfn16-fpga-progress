import copy
from datetime import datetime,timezone
from pathlib import Path
import tempfile
import unittest
from fpga.synthesis import prepare_crt27_mont_hostbench_v1 as p


class HostBenchmarkPreparationTests(unittest.TestCase):
    def test_proven_exact_parent_and_raw_runtime(self):
        manifest,raw=p.baseline()
        self.assertEqual(raw['wall_seconds'],289.05)
        self.assertEqual(raw['maximum_resident_kib'],6327536)
        self.assertEqual(manifest['seed'],1)
        self.assertEqual(manifest['compile_processors'],4)
        self.assertEqual(len(manifest['source_sha256']),5)

    def test_fresh_instance_neutral_clone_has_no_execution_or_db(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'stage';result=p.prepare(out)
            self.assertEqual(result['chosen_instance_type'],'m8azn.3xlarge')
            self.assertEqual(result['fit_slot'],'bench')
            self.assertEqual(result['workers'],4)
            self.assertEqual(result['per_fit_memory_bytes'],24<<30)
            for key in ('dispatch_authorized','copied_database_or_checkpoint','native_execution','promotion_allowed'):
                self.assertFalse(result[key])
            self.assertEqual(len([k for k in result['inventory'] if k.startswith('project/')]),10)
            self.assertEqual(p.sha(out/'project/manifest.json'),p.PINS['manifest.json'])
            with self.assertRaisesRegex(ValueError,'fresh benchmark'):
                p.prepare(out)

    def test_settings_seed_or_existing_state_drift_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            out=(Path(folder)/'stage').resolve();p.prepare(out);project=out/'project';manifest,_=p.baseline()
            original=(project/'probe.qsf').read_text()
            (project/'probe.qsf').write_text(original.replace('SEED 1','SEED 2'))
            with self.assertRaisesRegex(ValueError,'byte-identical'):
                p.verify_fresh_project(project,manifest)
            (project/'probe.qsf').write_text(original);(project/'output_files').mkdir()
            with self.assertRaisesRegex(ValueError,'empty execution state'):
                p.verify_fresh_project(project,manifest)

    def test_frozen_v6_does_not_admit_new_physical_profiles(self):
        from fpga.cloud import aws_fit_v6 as v6
        now=datetime(2026,10,1,tzinfo=timezone.utc)
        for count in (12,16,24):
            rows=[dict(cpu=i,package_id=0,core_id=i) for i in range(count)]
            document=dict(hostname=v6.HOST,observed_at=now.isoformat(),cpus=rows,
                          slots=dict(a=[0,1,2,3],b=[4,5,6,7]))
            with self.subTest(count=count),self.assertRaisesRegex(ValueError,'requires approved'):
                v6.validate_topology(document,'a',[0,1,2,3],rows,v6.HOST,now)


if __name__=='__main__':unittest.main()
