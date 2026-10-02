"""Pure retained-source/structure/settings checks; no vendor/native work."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fpga.reference import radix22_aa_whole_fit_prepare_v1 as a


class WholeFitPreparationTests(unittest.TestCase):
    def test_unique_delta_same_settings_and_source_structure(self):
        with tempfile.TemporaryDirectory(prefix='aa-whole-source-') as temp:
            out=Path(temp)/'candidate';r=a.prepare(out)
            self.assertEqual(r['compiled_sv'],31);self.assertEqual(r['compile_processors'],6)
            self.assertEqual(r['clock_period_ns'],9.668);self.assertEqual(r['source_structural']['findings'],[])
            self.assertFalse(r['fit_launched']);self.assertTrue(r['whole_fit_budget_required'])
            m=json.loads((out/'project/manifest.json').read_text());self.assertEqual(m['required_native_gates'],a.REQUIRED)
            self.assertFalse(m['area_or_clock_saving_claim']);self.assertTrue(m['no_F3_upper_cancel_merge'])
            self.assertNotIn('parent_native_report_sha256',m)
            with self.assertRaises(ValueError):a.prepare(out)

    def test_retained_context_and_exact_reverse_all_sources(self):
        old,spec,m,files=a.input_context()
        self.assertEqual(len(old['source_sha256']),30);self.assertEqual(len(m['build']['sv_sources']),31)
        self.assertEqual(spec['identity']['clock_period_ns'],9.668)
        self.assertEqual(old['top'],'genefer_anext_point_core_v1')

    def test_source_context_inventory_and_checker_pin_drift_reject(self):
        original=a.s.sha
        targets=[a.ROOT/a.BASE/'project/manifest.json',a.ROOT/a.BASE/'project-context.json',
                 a.ROOT/a.BASE/'inventory.json',Path(a.parent.__file__),a.ROOT/'tools/prefit_structural_guard_v1.py']
        for target in targets:
            with self.subTest(target=target),patch.object(a.s,'sha',lambda p:'0'*64 if Path(p)==target else original(p)):
                with self.assertRaises(ValueError):a.input_context()


if __name__=='__main__':unittest.main()
