import json
import tempfile
import unittest
from pathlib import Path
from synthesis.summarize import read_probe


class SummaryTests(unittest.TestCase):
    def test_missing_fit_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "manifest.json").write_text(json.dumps({"target": "ntt"}))
            report = read_probe(path)
            self.assertFalse(report["fit_success"])
            self.assertFalse(report["internal_timing_met"])
            self.assertNotIn("alms", report)

    def test_raw_dsp_usage_is_not_packing_adjusted_need(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            (path/"manifest.json").write_text("{}")
            out=path/"output_files";out.mkdir()
            (out/"probe.fit.summary").write_text("Fitter Status : Successful\nTotal DSP Blocks : 152 / 1,518\n")
            table=("; Fitter Resource Usage Summary ;\n"
                   "; [A] ALMs used in final placement [=a+b+c+d] ; 14,864 / 427,200 ; 3 % ;\n"
                   "; [A] Total Fixed Point DSP Blocks ; 222 ; ;\n"
                   "; [B] Total Floating Point DSP Blocks ; 0 ; ;\n"
                   "; [C] Total DSP_PRIME Blocks ; 0 ; ;\n"
                   "; [D] Estimate of DSP Blocks recoverable by dense merging ; 70 ; ;\n\n")
            (out/"probe.fit.rpt").write_text(table)
            report=read_probe(path)
            self.assertEqual(report["dsp_blocks"],152)
            self.assertEqual(report["dsp_blocks_needed"],152)
            self.assertEqual(report["dsp_blocks_placed"],222)
            self.assertEqual(report["dsp_blocks_recoverable"],70)
            self.assertEqual(report["alms_placed"],14864)
            (out/"probe.fit.rpt").write_text(table.replace("; 70 ;", "; 69 ;"))
            with self.assertRaises(ValueError): read_probe(path)

    def test_missing_detail_does_not_invent_raw_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            (path/"manifest.json").write_text("{}")
            out=path/"output_files";out.mkdir()
            (out/"probe.fit.summary").write_text("Fitter Status : Successful\nTotal DSP Blocks : 16 / 1,518\n")
            report=read_probe(path)
            self.assertEqual(report["dsp_blocks_needed"],16)
            self.assertNotIn("dsp_blocks_placed",report)
            self.assertNotIn("alms", report)

    def test_fitted_resources_and_negative_slack(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "manifest.json").write_text("{}")
            out = path / "output_files"; out.mkdir()
            (out / "probe.fit.summary").write_text("Fitter Status : Successful\nLogic utilization (in ALMs) : 1,234 / 427,200\nTotal RAM Blocks : 256 / 2,713\n")
            (out / "probe.sta.rpt").write_text("; Fmax Summary ;\n; 95.0 MHz ; 95.0 MHz ; kernel_clk ;\nDelay Models:\n; Setup Summary ;\n; kernel_clk ; -0.5 ; 1 ;\nDelay Models:\n; Hold Summary ;\n; kernel_clk ; 0.05 ; 0 ;\nDelay Models:\n")
            report = read_probe(path)
            self.assertTrue(report["fit_success"])
            self.assertEqual(report["alms"], 1234)
            self.assertEqual(report["ram_blocks"], 256)
            self.assertEqual(report["restricted_fmax_mhz"], 95)
            self.assertFalse(report["internal_timing_met"])
