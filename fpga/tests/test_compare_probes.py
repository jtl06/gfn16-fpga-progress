import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from synthesis.prepare import prepare
from synthesis.compare_probes import compare


class CompareProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.paths=[Path(self.temp.name)/name for name in ("baseline","candidate")]
        self.reports=[]
        for path,target in zip(self.paths,("multiplier27","multiplier27_sparse")):
            m=prepare(path,target,period=5)
            self.reports.append({"status":"passed","source_sha256":{
                "rtl/kernel/"+name:value for name,value in m["source_sha256"].items()}})
            (path/"output_files").mkdir()
            (path/"output_files/probe.fit.summary").write_text("Quartus Prime Version : synthetic-unit-fixture\n")
        self.probes=[dict(fit_success=True,hold_slack_ns=.01,restricted_fmax_mhz=f,
            internal_timing_met=f>=200,dsp_blocks_placed=d,alms_placed=100)
            for f,d in ((180,3),(245,1))]

    def run_compare(self):
        with patch("synthesis.compare_probes.read_probe",side_effect=self.probes):
            return compare(*self.paths,*self.reports)

    def test_matched_results_separate_raw_resources_from_clock_ratio(self):
        r=self.run_compare()
        self.assertEqual(r["resources"]["dsp_blocks_placed"]["delta"],-2)
        self.assertAlmostEqual(r["fmax_ratio_not_throughput"],245/180)
        self.assertFalse(r["baseline_target_clock_met"])
        self.assertTrue(r["candidate_target_clock_met"])
        self.assertNotIn("speedup",r)

    def test_clock_seed_processors_and_pin_changes_rejected(self):
        path=self.paths[1]/"probe.qsf";original=path.read_text()
        for old,new in (("SEED 1","SEED 2"),("NUM_PARALLEL_PROCESSORS 8","NUM_PARALLEL_PROCESSORS 4"),
                        ("VIRTUAL_PIN ON","VIRTUAL_PIN OFF")):
            path.write_text(original.replace(old,new))
            with self.assertRaisesRegex(ValueError,"unmatched physical control"):self.run_compare()
        path.write_text(original)
        (self.paths[1]/"probe.sdc").write_text("different constraints")
        with self.assertRaisesRegex(ValueError,"unmatched physical control"):self.run_compare()

    def test_tool_version_and_manifest_mismatch_rejected(self):
        version=self.paths[1]/"output_files/probe.fit.summary"
        version.write_text("Quartus Prime Version : other-fixture\n")
        with self.assertRaisesRegex(ValueError,"quartus_version"):self.run_compare()
        version.write_text("Quartus Prime Version : synthetic-unit-fixture\n")
        path=self.paths[1]/"manifest.json";m=json.loads(path.read_text());m["field_parameters"]["P"]+=2
        path.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError,"field_parameters"):self.run_compare()

    def test_stale_sources_failed_sim_and_missing_timing_rejected(self):
        good=copy.deepcopy(self.reports[1])
        self.reports[1]["status"]="running"
        with self.assertRaisesRegex(ValueError,"passed simulation"):self.run_compare()
        self.reports[1]=copy.deepcopy(good)
        key=next(iter(good["source_sha256"]))
        self.reports[1]["source_sha256"][key]="wrong"
        with self.assertRaisesRegex(ValueError,"simulation source mismatch"):self.run_compare()
        self.reports[1]=good
        self.probes[1]["fit_success"]=False
        with self.assertRaisesRegex(ValueError,"completed fits"):self.run_compare()
        self.probes[1]["fit_success"]=True;self.probes[1]["restricted_fmax_mhz"]=0
        with self.assertRaisesRegex(ValueError,"Fmax"):self.run_compare()

    def test_tampered_snapshot_and_extra_qsf_source_rejected(self):
        path=self.paths[1]/"probe.qsf"
        path.write_text(path.read_text()+"set_global_assignment -name SYSTEMVERILOG_FILE rtl/extra.sv\n")
        with self.assertRaisesRegex(ValueError,"closure mismatch"):self.run_compare()
        source=next((self.paths[1]/"rtl").glob("*.sv"));source.write_text("tampered")
        with self.assertRaisesRegex(ValueError,"snapshot source mismatch"):self.run_compare()
