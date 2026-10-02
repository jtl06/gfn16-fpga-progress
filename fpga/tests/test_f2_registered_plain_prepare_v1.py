"""Matched plain-flow source checks; no vendor or worker invocation."""
import json
from pathlib import Path
import tempfile
import unittest

from fpga.reference import f2_registered_plain_prepare_v1 as plain


class PlainPrepare(unittest.TestCase):
    def test_only_run_tcl_and_metadata_change_both_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory).resolve()/'plain'
            result = plain.prepare(output)
            for role, receipt in result['projects'].items():
                root, source = output/role, plain.PARENT/role
                old, new = json.loads((source/'manifest.json').read_text()), json.loads((root/'manifest.json').read_text())
                self.assertEqual(new['source_sha256'], old['source_sha256'])
                for name in ('probe.qsf','probe.sdc','probe.qpf'):
                    self.assertEqual((root/name).read_bytes(), (source/name).read_bytes())
                self.assertEqual((root/'run.tcl').read_text(), plain.plain.FULL_TCL)
                self.assertEqual(new['control_sha256']['run.tcl'], plain.sha(root/'run.tcl'))
                self.assertNotEqual(new['control_sha256']['run.tcl'], old['control_sha256']['run.tcl'])
                self.assertEqual(new['native_small_independent_receipt_sha256'], plain.NATIVE)
                self.assertFalse(new['native_small_gate_pending'])
                self.assertTrue(new['actual_AW16_integration_pending'])
                self.assertFalse(new['physical_timing_proven'])
                spec = json.loads((root/'structural-spec.json').read_text())
                self.assertEqual(plain.structural.source_inventory(root, spec)['findings'], [])
                self.assertEqual(receipt['manifest_sha256'], plain.sha(root/'manifest.json'))
            self.assertTrue(result['normal_dispatch_checks_required'])
            self.assertFalse(result['promotion_allowed'])
            with self.assertRaisesRegex(ValueError, 'fresh canonical'):
                plain.prepare(output)

    def test_relative_or_existing_output_rejected(self):
        with self.assertRaisesRegex(ValueError, 'fresh canonical'):
            plain.prepare(Path('relative'))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'fresh canonical'):
                plain.prepare(Path(directory).resolve())


if __name__ == '__main__':
    unittest.main()
