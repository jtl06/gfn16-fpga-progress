import importlib.util
from pathlib import Path
import tarfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('r9_scoped_physical', ROOT/'results/throughput-20260929/r9-seed2-clock-replay-independent-v1.py')
review = importlib.util.module_from_spec(spec); spec.loader.exec_module(review)
hspec = importlib.util.spec_from_file_location('r9_pure_sta', ROOT/'tools/audit_plain_fit_timing_noexceptions_v1.py')
helper = importlib.util.module_from_spec(hspec); hspec.loader.exec_module(helper)


class PhysicalTamperControls(unittest.TestCase):
    def test_regular_closed_archive_paths_and_types(self):
        good = tarfile.TarInfo('audit/timing/selected-0-setup-summary.rpt')
        good.size = 10
        review.safe_member(good)
        for name in ('../outside', '/outside', 'audit/../../outside', './audit/a'):
            bad = tarfile.TarInfo(name)
            with self.assertRaises(ValueError): review.safe_member(bad)
        for kind in (tarfile.SYMTYPE,tarfile.LNKTYPE,tarfile.DIRTYPE):
            bad = tarfile.TarInfo('audit/alias'); bad.type = kind
            with self.assertRaises(ValueError): review.safe_member(bad)

    def test_source_pinned_period_finite_consistency_and_exception_controls(self):
        self.assertEqual(review.sha(ROOT/'tools/audit_plain_fit_timing_noexceptions_v1.py'),review.HELPER)
        self.assertEqual(helper.period('13.070'),13.070)
        self.assertEqual(helper.period('13.068'),13.068)
        for wrong in ('13.069','13.0701','nan','1e1'):
            with self.assertRaises(ValueError): helper.period(wrong)
        self.assertTrue(helper.summary('; kernel_clk ; .001 ; 0 ; 0 ;\n','setup')['closes'])
        self.assertFalse(helper.summary('; kernel_clk ; -.001 ; -.001 ; 1 ;\n','setup')['closes'])
        for wrong in ('; kernel_clk ; nan ; 0 ; 0 ;\n', '; kernel_clk ; -.001 ; 0 ; 0 ;\n',
                      '; kernel_clk ; .001 ; -.001 ; 1 ;\n'):
            with self.assertRaises(ValueError): helper.summary(wrong,'setup')
        sdc='create_clock -name kernel_clk -period 12.0 [get_ports {clk}]\nderive_clock_uncertainty\n'
        helper.source_sdc(sdc,'12.0')
        for wrong in (sdc+'set_false_path -to [all_registers]\n',sdc+'set_false_path -from [get_ports {rst_n}]\n',sdc.replace('12.0','13.0')):
            with self.assertRaises(ValueError): helper.source_sdc(wrong,'12.0')


if __name__ == '__main__': unittest.main()
