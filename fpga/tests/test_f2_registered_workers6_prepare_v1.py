"""Six-worker source-only delta checks; never invoke a worker or Quartus."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from fpga.reference import f2_registered_workers6_prepare_v1 as six


class WorkersSix(unittest.TestCase):
    def test_both_exact_qsf_worker_delta_and_v6_contexts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory).resolve()/'workers6'
            result = six.prepare(output)
            for role, receipt in result['projects'].items():
                source, project = six.SOURCE/role, output/role
                old = json.loads((source/'manifest.json').read_text())
                new = json.loads((project/'manifest.json').read_text())
                self.assertEqual(new['source_sha256'], old['source_sha256'])
                for name in old['source_sha256']:
                    self.assertEqual((source/'rtl'/name).read_bytes(), (project/'rtl'/name).read_bytes())
                for name in ('probe.qpf', 'probe.sdc', 'run.tcl'):
                    self.assertEqual((source/name).read_bytes(), (project/name).read_bytes())
                self.assertEqual((source/'probe.qsf').read_bytes(),
                    (project/'probe.qsf').read_bytes().replace(six.WORKER_NEW, six.WORKER_OLD))
                self.assertEqual(new['compile_processors'], 6)
                self.assertEqual(new['clock_period_ns'], 8.0)
                self.assertEqual(new['seed'], 1)
                self.assertFalse(new['actual_AW16_integration_pending'])
                self.assertFalse(new['physical_timing_proven'])
                self.assertEqual(six.six_worker_verifier().verify_project(project),
                                 json.loads((output/(role+'-context.json')).read_text()))
                self.assertEqual(receipt['manifest_sha256'], six.sha(project/'manifest.json'))
                self.assertEqual(receipt['context_sha256'], six.sha(output/(role+'-context.json')))
            self.assertEqual(result['workers'], 6)
            self.assertFalse(result['launch_attempted'])
            self.assertFalse(result['transfer_attempted'])
            self.assertFalse(result['promotion_allowed'])

    def test_relative_existing_output_rejected(self):
        with self.assertRaisesRegex(ValueError, 'fresh canonical'):
            six.prepare(Path('relative'))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'fresh canonical'):
                six.prepare(Path(directory).resolve())

    def test_parent_control_tamper_rejected_before_any_output(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            source = base/'source'
            shutil.copytree(six.SOURCE, source)
            path = source/'candidate/probe.qsf'
            path.write_bytes(path.read_bytes()+b'# unpinned change\n')
            output = base/'workers6'
            with patch.object(six, 'SOURCE', source):
                with self.assertRaisesRegex(ValueError, 'immutable source/control parent'):
                    six.prepare(output)
            self.assertFalse(output.exists())

    def test_v6_worker_manifest_qsf_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory).resolve()/'workers6'
            six.prepare(output)
            path = output/'parent/probe.qsf'
            path.write_bytes(path.read_bytes().replace(six.WORKER_NEW, six.WORKER_OLD))
            with self.assertRaisesRegex(ValueError, 'QSF workers mismatch'):
                six.six_worker_verifier().verify_project(output/'parent')


if __name__ == '__main__':
    unittest.main()
