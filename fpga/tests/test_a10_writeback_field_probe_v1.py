from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from fpga.reference import a10_writeback_field_probe_v1 as fit


class WritebackFieldSource(unittest.TestCase):
    def test_exact_raw_engine_and_rename_shell_only(self):
        files,_=fit.source_inputs();old,_=fit.parent.source_inputs()
        self.assertEqual(len(files),9)
        for name in files.keys() & old.keys():self.assertEqual(files[name],old[name])
        self.assertEqual(files[Path(fit.candidate.gen.TARGET).name],(fit.ROOT/fit.candidate.gen.TARGET).read_bytes())
        old_wrapper=old[fit.parent.TOP+'.sv'].decode().replace(fit.parent.TOP,fit.TOP)
        self.assertEqual(files[fit.TOP+'.sv'].decode(),old_wrapper)
        self.assertNotIn(Path(fit.candidate.gen.NATIVE_HOST).name,files)

    def test_pending_native_never_creates_project_or_claims_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            project=Path(directory)/'fresh'
            with patch.object(fit,'actual_native',side_effect=ValueError('actual native gate required')):
                with self.assertRaisesRegex(ValueError,'actual native gate required'):fit.prepare(project,6)
            self.assertFalse(project.exists())

    def test_workers_invalid_before_native_or_writes(self):
        with self.assertRaisesRegex(ValueError,'FIT_WORKERS'):fit.prepare('/unused',5)

    def test_actual_native_closed_plain_fit_project_four_and_six(self):
        plain=fit.base.load_exact(fit.base.PLAIN,fit.base.PLAIN_SHA,'_f3_plain_test')
        for workers in (4,6):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory).resolve();project=root/'project';result=fit.prepare(project,workers)
                (root/'run-aws-fit-v6.sh').write_text('# pure source descriptor fixture\n')
                runner=plain.runner(dict(root=str(root),workers=workers,memory=20<<30,slots={'a':list(range(workers))}),
                                    'gfn16-aws-m8i',False)
                self.assertEqual(runner.verify_project(project)['manifest_sha256'],result['manifest_sha256'])
                manifest=json.loads((project/'manifest.json').read_text())
                self.assertEqual(len(manifest['native_connected_reports']),9)
                self.assertTrue(manifest['native_full_N_child_verified'])
                self.assertFalse(manifest['hold_repair_claim'])
                self.assertEqual(manifest['source_only_ledger']['whole_controller_ntt_cycles'],17743)
                qsf=(project/'probe.qsf').read_text()
                (project/'probe.qsf').write_text(qsf.replace('-name AW 16','-name AW 8'))
                with self.assertRaisesRegex(ValueError,'parameter mismatch'):runner.verify_project(project)


if __name__=='__main__':unittest.main()
