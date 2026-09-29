import json
from pathlib import Path
import unittest
from plot_progress import load_progress, seconds


class ProgressTests(unittest.TestCase):
    def test_candidate_and_evidence(self):
        data=load_progress(Path(__file__).parents[1]/"progress.json")
        self.assertEqual(data["candidate"]["exponent_bits"],1911814)
        self.assertEqual(data["reference_clock_mhz"],100)
        for row in data["milestones"][1:]:
            self.assertEqual(row["evidence_class"],"integrated_rtl_simulation")
            self.assertEqual(len(row["rtl_core_sha256"]),64)
            self.assertEqual(len(row["private_regression_report_sha256"]),64)
            self.assertEqual(row["full_size_recurrent_squares"],5)

    def test_units_and_publication_boundary(self):
        path=Path(__file__).parents[1]/"progress.json"
        data=load_progress(path)
        self.assertAlmostEqual(seconds(data,data["milestones"][0])/86400,7.091051554685417)
        self.assertGreater(seconds(data,data["milestones"][-1]),600)
        for forbidden in ("/Users/","/home/","ssh://","BEGIN PRIVATE KEY","github_pat_"):
            self.assertNotIn(forbidden,path.read_text())
