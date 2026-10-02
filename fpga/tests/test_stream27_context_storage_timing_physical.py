import json
import unittest

from fpga.reference import stream27_context_storage_timing_physical as p


class TimingStoragePhysicalTests(unittest.TestCase):
    def test_synthesis_exact_controls_and_source_match(self):
        manifest, files = p.build()
        self.assertEqual(manifest['allowed_stages'], ['syn'])
        self.assertEqual(files['run.tcl'], (p.PARENT / 'run.tcl').read_bytes())
        self.assertEqual(len(manifest['source_sha256']), 58)
        normal = json.loads((p.NORMAL / 'manifest.json').read_text())
        for name, digest in manifest['source_sha256'].items():
            self.assertEqual(normal['sources']['rtl/' + name], digest)

    def test_field_matched_seed_clock_worker_controls(self):
        manifest, files = p.build_field()
        for key, value in (('scope', 'component_probe'), ('clock_period_ns', 10), ('seed', 1), ('compile_processors', 4)):
            self.assertEqual(manifest[key], value)
        for name in ('run.tcl', 'probe.qpf', 'probe.sdc'):
            self.assertEqual(files[name], (p.FIELD_PARENT / name).read_bytes())
        self.assertEqual(manifest['storage2']['matched_parent_id'], 's4-p16-c2-timing-field-f0-v1')
        self.assertFalse(manifest['storage2']['wholefit_released'])


if __name__ == '__main__':
    unittest.main()
