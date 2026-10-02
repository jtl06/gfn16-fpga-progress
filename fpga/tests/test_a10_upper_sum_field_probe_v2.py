import json
import tempfile
from pathlib import Path
import unittest
from fpga.reference import a10_upper_sum_field_probe_v2 as prep


class UpperFieldPacket(unittest.TestCase):
    def test_only_cell_engine_shell_differ_from_point(self):
        files,_=prep.source_inputs();old,_=prep.parent.source_inputs()
        for name in files.keys() & old.keys():self.assertEqual(files[name],old[name])
        self.assertEqual(len(files),9)
        self.assertIn(Path(prep.candidate.gen.TARGET).name,files)
        self.assertIn(Path(prep.candidate.gen.ENGINE).name,files)

    def test_exact_plain_project_admission_four_and_six(self):
        plain=prep.base.load_exact(prep.base.PLAIN,prep.base.PLAIN_SHA,'_upper_test_plain')
        for workers in (4,6):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory).resolve();project=root/'project';result=prep.prepare(project,workers)
                (root/'run-aws-fit-v6.sh').write_text('# pure source descriptor fixture\n')
                runner=plain.runner(dict(root=str(root),workers=workers,memory=20<<30,slots={'a':list(range(workers))}),
                                    'gfn16-aws-m8i',False)
                self.assertEqual(runner.verify_project(project)['manifest_sha256'],result['manifest_sha256'])
                manifest=json.loads((project/'manifest.json').read_text())
                self.assertEqual(manifest['seed'],1)
                self.assertEqual(manifest['clock_period_ns'],8.0)
                self.assertTrue(manifest['native_full_N_child_verified'])
                qsf=(project/'probe.qsf').read_text()
                (project/'probe.qsf').write_text(qsf.replace('-name AW 16','-name AW 8'))
                with self.assertRaisesRegex(ValueError,'parameter mismatch'):
                    runner.verify_project(project)


if __name__=='__main__':unittest.main()
