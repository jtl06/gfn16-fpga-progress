import copy
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("preparation_metrics", Path(__file__).parents[1] / "tools/preparation_metrics.py")
metrics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(metrics)
START, END = "2026-10-01T10:00:00Z", "2026-10-01T11:00:00Z"


def run(job, start, end=None, after=(), source="source-a", candidate="A"):
    return dict(job_id=job, candidate_id=candidate, candidate_source_sha256=source,
                started_at_utc=start, finished_at_utc=end, passed_contract=True, after=list(after))


class PreparationMetricsTest(unittest.TestCase):
    def sample(self):
        return {"ready": [dict(candidate_id="A", candidate_source_sha256="source-a", rtl_ready_at_utc=START)],
                "runs": [run("small", "2026-10-01T10:05:00Z", "2026-10-01T10:06:00Z"),
                         run("full", "2026-10-01T10:07:00Z", after=["small"])]}

    def test_native_times_and_targets(self):
        result = metrics.summarize(self.sample(), START, END)
        self.assertEqual(result["rtl_ready_to_first_run_median_seconds"], 300)
        self.assertEqual(result["same_candidate_gap_median_seconds"], 60)
        self.assertLess(len(metrics.compact_table(result).encode()), 1000)

    def test_missing_readiness_not_invented(self):
        data = self.sample(); data["ready"] = []
        result = metrics.summarize(data, START, END)
        self.assertIsNone(result["rtl_ready_to_first_run_median_seconds"])
        self.assertEqual(result["coverage_missing"]["readiness"], 1)

    def test_different_source_not_joined(self):
        data = self.sample(); data["runs"][1]["candidate_source_sha256"] = "source-b"
        self.assertIsNone(metrics.summarize(data, START, END)["same_candidate_gap_median_seconds"])

    def test_parallel_peer_not_fabricated_as_gap(self):
        data = self.sample(); data["runs"][1]["after"] = []
        self.assertIsNone(metrics.summarize(data, START, END)["same_candidate_gap_median_seconds"])

    def test_other_dependency_wait_is_visible(self):
        data = self.sample()
        data["runs"].append(run("reference", "2026-10-01T10:01:00Z", "2026-10-01T10:06:50Z", candidate="B"))
        data["runs"][1]["after"].append("reference")
        result = metrics.summarize(data, START, END)
        self.assertEqual(result["same_candidate_gap_median_seconds"], 60)
        self.assertEqual(result["all_prerequisites_ready_to_start_median_seconds"], 10)

    def test_missing_or_failed_predecessor_not_a_sample(self):
        for field, value in (("finished_at_utc", None), ("passed_contract", False)):
            data = self.sample(); data["runs"][0][field] = value
            result = metrics.summarize(data, START, END)
            self.assertIsNone(result["same_candidate_gap_median_seconds"])
            self.assertEqual(result["coverage_missing"]["prerequisite_evidence"], 1)

    def test_duplicate_attempt_or_bad_time_rejected(self):
        data = self.sample(); data["runs"].append(copy.deepcopy(data["runs"][0]))
        with self.assertRaises(ValueError): metrics.summarize(data, START, END)
        data = self.sample(); data["ready"][0]["rtl_ready_at_utc"] = "2026-10-01T10:09:00Z"
        with self.assertRaises(ValueError): metrics.summarize(data, START, END)
        with self.assertRaises(ValueError): metrics.stamp("2026-10-01T10:00:00")

    def test_window_end_exclusive(self):
        result = metrics.summarize(self.sample(), "2026-10-01T10:05:00Z", "2026-10-01T10:07:00Z")
        self.assertEqual(result["samples"], {"preparation": 1, "same_candidate_edges": 0})

    def test_waiting_candidate_not_hidden_by_completed_only_median(self):
        data = self.sample(); data["runs"] = []
        result = metrics.summarize(data, START, END)
        self.assertEqual(result["awaiting_first_run"], {"count": 1, "at_or_over_target": 1, "oldest_seconds": 3600})
        data["ready"][0]["retired_at_utc"] = "2026-10-01T10:30:00Z"
        self.assertEqual(metrics.summarize(data, START, END)["awaiting_first_run"]["count"], 0)

    def ticket(self):
        return dict(id="native", rtl_readiness=self.sample()["ready"][0],
                    dispatch=dict(invocation="run-a", properties=dict(
                        InvocationID="run-a", ExecMainStartTimestamp="Thu 2026-10-01 10:05:00 UTC")),
                    result=dict(properties=dict(InvocationID="run-a", ExecMainExitTimestamp="Thu 2026-10-01 10:06:00 UTC")),
                    dependency_gate=dict(status="PASS_expected_contracts", candidate_source_sha256="harness-not-rtl"))

    def test_queue_adapter_uses_declared_identity_and_native_times(self):
        events = metrics.queue_events([self.ticket()])
        self.assertEqual(events["runs"][0]["candidate_source_sha256"], "source-a")
        self.assertEqual(metrics.summarize(events, START, END)["rtl_ready_to_first_run_median_seconds"], 300)

    def test_queue_legacy_identity_stays_unknown(self):
        ticket = self.ticket(); del ticket["rtl_readiness"]
        result = metrics.summarize(metrics.queue_events([ticket]), START, END)
        self.assertEqual(result["coverage_missing"]["identity"], 1)
        self.assertIsNone(result["rtl_ready_to_first_run_median_seconds"])

    def test_queue_wrong_invocation_rejected(self):
        ticket = self.ticket(); ticket["result"]["properties"]["InvocationID"] = "old-run"
        with self.assertRaises(ValueError): metrics.queue_events([ticket])

    def test_queue_dependency_dict_and_typed_failure(self):
        parent = self.ticket()
        child = copy.deepcopy(parent); child["id"] = "child"
        child["after"] = [dict(id="native", functional_sha256="other-contract")]
        child["dispatch"]["properties"]["ExecMainStartTimestamp"] = "Thu 2026-10-01 10:07:00 UTC"
        child["result"] = {}
        events = metrics.queue_events([parent, child])
        self.assertEqual(metrics.summarize(events, START, END)["same_candidate_gap_median_seconds"], 60)
        parent["dependency_gate"]["status"] = "FAIL"
        self.assertIsNone(metrics.summarize(metrics.queue_events([parent, child]), START, END)["same_candidate_gap_median_seconds"])

    def test_explicit_normal_submission_splits_preparation_from_queue(self):
        ticket = self.ticket()
        ticket.update(test_role="normal", normal_test_submitted_at_utc="2026-10-01T10:04:00Z")
        result = metrics.summarize(metrics.queue_events([ticket]), START, END)
        normal = result["operational_readiness"]
        self.assertEqual(normal["rtl_to_normal_submit_median_seconds"], 240)
        self.assertEqual(normal["normal_submit_to_native_start_median_seconds"], 60)
        self.assertEqual(result["rtl_ready_to_first_run_median_seconds"], 300)
        self.assertLess(len(metrics.compact_table(result).encode()), 1000)

    def test_legacy_submit_not_backfilled(self):
        ticket = self.ticket(); ticket["created"] = START
        normal = metrics.summarize(metrics.queue_events([ticket]), START, END)["operational_readiness"]
        self.assertEqual(normal["samples"], dict(preparation=0, queue_delay=0))

    def test_normal_job_delay_does_not_invent_missing_design_identity(self):
        ticket = self.ticket(); del ticket["rtl_readiness"]
        ticket.update(test_role="normal", normal_test_submitted_at_utc="2026-10-01T10:04:00Z")
        result = metrics.summarize(metrics.queue_events([ticket]), START, END)
        normal = result["operational_readiness"]
        self.assertEqual(normal["per_normal_job_submit_to_start_median_seconds"], 60)
        self.assertEqual(normal["normal_job_samples"], 1)
        self.assertEqual(normal["samples"]["preparation"], 0)
        self.assertEqual(result["coverage_missing"]["identity"], 1)

    def test_conflicting_readiness_is_unknown_not_an_invented_timestamp(self):
        data = self.sample()
        conflicting = copy.deepcopy(data["ready"][0])
        conflicting["rtl_ready_at_utc"] = "2026-10-01T10:01:00Z"
        data["ready"].append(conflicting)
        result = metrics.summarize(data, START, END)
        self.assertIsNone(result["rtl_ready_to_first_run_median_seconds"])
        self.assertEqual(result["coverage_missing"]["readiness_conflicts"], 1)
        self.assertEqual(result["same_candidate_gap_median_seconds"], 60)

    def test_first_normal_only_and_fault_cannot_supply_submission(self):
        first = self.ticket()
        first.update(test_role="normal", normal_test_submitted_at_utc="2026-10-01T10:04:00Z")
        later = copy.deepcopy(first); later["id"] = "later"
        later["normal_test_submitted_at_utc"] = "2026-10-01T10:04:30Z"
        result = metrics.summarize(metrics.queue_events([first, later]), START, END)
        self.assertEqual(result["operational_readiness"]["samples"], dict(preparation=1, queue_delay=1))
        first["test_role"] = "deliberate_fault"
        with self.assertRaises(ValueError): metrics.summarize(metrics.queue_events([first]), START, END)


if __name__ == "__main__":
    unittest.main()
