import json
import re
from pathlib import Path
import unittest
from plot_progress import load_progress, seconds


class ProgressTests(unittest.TestCase):
    def test_fit_backed_projection_remains_separate_from_common_clock_chart(self):
        root=Path(__file__).parents[1]
        data=load_progress(root/'progress.json')
        experiment=json.loads((root/'experiments.json').read_text())
        fit=experiment['fit_backed_planning']
        row=next(r for r in data['milestones'] if r['id']==fit['milestone_id'])
        cycles=fit['cold_cycles']+(data['candidate']['exponent_bits']-1)*fit['warm_cycles']
        self.assertAlmostEqual(cycles/(fit['assumed_clock_mhz']*1e6),fit['projected_candidate_seconds'])
        self.assertLess(fit['assumed_clock_mhz'],fit['reported_fmax_mhz'])
        self.assertFalse(fit['fit_target_met'])
        self.assertNotEqual(fit['projected_candidate_seconds'],seconds(data,row))

    def test_new_evidence_is_qualified_and_sanitized(self):
        root=Path(__file__).parents[1]
        data=json.loads((root/'experiments.json').read_text())
        self.assertFalse(data['new_integration']['physical_fit_complete'])
        self.assertLess(data['new_integration']['warm_cycles'],data['new_integration']['baseline_warm_cycles'])
        for component in data['component_fits']:
            self.assertRegex(component['private_summary_sha256'],r'^[0-9a-f]{64}$')
            self.assertEqual(component['target_met'],component['fmax_mhz']>=component['target_mhz'])
            self.assertGreater(component['raw_dsp_blocks'],0)
        for name in ('README.md','progress.json','experiments.json'):
            text=(root/name).read_text()
            for forbidden in ('/Users/','/home/','ssh://','BEGIN PRIVATE KEY','github_pat_',
                              'instance_id','account_id','project_id'):
                self.assertNotIn(forbidden,text)
            self.assertIsNone(re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b',text))
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

    def test_cached_point_includes_one_cold_start(self):
        data=load_progress(Path(__file__).parents[1]/"progress.json")
        row=next(r for r in data["milestones"] if r["id"]=="sixteen-cached-prefix")
        self.assertAlmostEqual(seconds(data,row),(479674+1911813*217522)/1e8)
        self.assertEqual(row["cold_samples"]+row["warm_samples"],5)
