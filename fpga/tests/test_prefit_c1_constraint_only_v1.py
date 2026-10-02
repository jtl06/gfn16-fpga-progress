import json
from pathlib import Path
import shutil
import tempfile
import unittest
from fpga.tools.prefit_c1_constraint_only_v1 import assess

FPGA = Path(__file__).resolve().parents[1]
BASE = FPGA/'results/throughput-20260929/core27-crtmont-c1-8ns-stage-v1/core27-crtmont-c1-seed1-cpu6-125-v1'


class ExactC1Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)/'project'
        shutil.copytree(BASE, self.project)
        shutil.copyfile(self.project/'evidence/parent-probe.qsf', self.project/'probe.qsf')
        shutil.copyfile(FPGA/'results/throughput-20260929/core27-crtmont-c1-8ns-aws-fit-v1/independent-review-v1.json', self.project/'evidence/prior-c1-review.json')
        manifest = json.loads((self.project/'manifest.json').read_text())
        manifest['compile_processors'] = 4
        (self.project/'manifest.json').write_text(json.dumps(manifest))

    def test_exact_justification_is_not_fit_permission(self):
        result = assess(self.project)
        self.assertTrue(result['synthesis_allowed'])
        self.assertTrue(result['crossing_requirement_satisfied_by_explicit_justification'])
        for flag in ('fit_allowed','native_design_assistant_pass','native_crossing_coverage_complete','promotion_allowed','physical_timing_proven'):
            self.assertFalse(result[flag])

    def test_changed_rtl_and_extra_file_fail(self):
        path = next((self.project/'rtl').glob('*.sv'))
        original = path.read_bytes()
        path.write_bytes(original+b'\n')
        with self.assertRaises(ValueError): assess(self.project)
        path.write_bytes(original)
        (self.project/'rtl/extra.sv').write_text('module extra; endmodule\n')
        with self.assertRaises(ValueError): assess(self.project)

    def test_settings_and_ancestry_fail(self):
        for name in ('probe.qsf','probe.qpf','probe.sdc','evidence/parent-manifest.json','evidence/parent-sta-review.json','evidence/prior-c1-review.json'):
            with self.subTest(name=name):
                path = self.project/name
                old = path.read_bytes()
                path.write_bytes(old+b'\n')
                with self.assertRaises(ValueError): assess(self.project)
                path.write_bytes(old)

    def test_manifest_identity_fail(self):
        path = self.project/'manifest.json'
        original = json.loads(path.read_text())
        for key, value in (('clock_period_ns',7.9),('compile_processors',6),('address_width',5),('seed',2),('core_parameters',{'NTT_LANES':32}),('source_sha256',{})):
            with self.subTest(key=key):
                changed = dict(original); changed[key] = value
                path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError): assess(self.project)
        path.write_text(json.dumps(original))


if __name__ == '__main__': unittest.main()
