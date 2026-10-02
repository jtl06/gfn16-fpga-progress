import unittest

from fpga.tools import azure_owner_iteration_metrics_v1 as m


class MetadataMetricsTests(unittest.TestCase):
    def base(self, records):
        return {"captured_at_utc": "1970-01-01T00:20:00Z", "evidence_sha256": {},
                "facts": {"valid_from_utc": 0, "hosts": {"h": {"physical_cores": 2, "capacity_basis": "fixture",
                                            "unavailable_intervals": [{"start": 400, "end": 600}],
                                            "unknown_availability_intervals": [{"start": 600, "end": 900}]}}},
                "records": records}

    def record(self, **kw):
        value = {"id": "a", "host": "h", "kind": "sim", "category": "expected_native_gate_positive_only",
                 "start_epoch": 100, "exit_epoch": 200, "physical_cores": [[0, 0], [0, 1]]}
        value.update(kw)
        return value

    def test_recovered_exit_not_collection(self):
        r = self.record(collected_epoch=1100)
        result = m.summarize(self.base([r]), 0, 1000)["windows"][0]
        self.assertEqual(result["terminal_counts_by_actual_exit"]["expected_native_gate_positive_only"], 1)
        self.assertEqual(result["hosts"]["h"]["observed_assigned_affinity_core_seconds_union"], 200)

    def test_running_not_extrapolated(self):
        r = self.record(exit_epoch=None, observed_running=True, last_observed_epoch=200)
        result = m.summarize(self.base([r]), 0, 1000)["windows"][0]
        self.assertEqual(result["hosts"]["h"]["observed_assigned_affinity_core_seconds_union"], 200)
        self.assertEqual(len(result["hosts"]["h"]["unresolved_intervals"]), 1)

    def test_affinity_union_and_downtime(self):
        r = self.record()
        other = self.record(id="b", start_epoch=150, exit_epoch=250)
        result = m.summarize(self.base([r, other]), 0, 1000)["windows"][0]["hosts"]["h"]
        self.assertEqual(result["observed_assigned_affinity_core_seconds_union"], 300)
        self.assertEqual(result["available_capacity_core_seconds_bounds"], [1000, 1600])
        self.assertEqual(result["known_unavailable_seconds"], 200)
        self.assertEqual(len(result["unit_affinity_overlap_union_not_double_counted"]), 2)

    def test_reference_never_native_gate(self):
        ticket = {"kind": "reference", "result": {"status": "needs_reference_import_validation"},
                  "dependency_gate": {"status": "PASS_expected_contracts"}}
        self.assertEqual(m.classify(ticket, {"status": "completed_native_commands_unreviewed"}, {}), "reference_generation")

    def test_intentional_negative_and_mixed_contracts(self):
        ticket = {"kind": "sim", "dependency_gate": {"status": "PASS_expected_contracts"}}
        report = {"status": "completed_native_commands_unreviewed"}
        self.assertEqual(m.classify(ticket, report, {"steps": [{"expected_returncode": 1}]}),
                         "expected_native_gate_intentional_negative_only")
        self.assertEqual(m.classify(ticket, report, {"steps": [{"expected_returncode": 0}, {"expected_returncode": 1}]}),
                         "expected_native_gate_mixed_positive_negative")

    def test_historical_import_no_native_count(self):
        self.assertEqual(m.classify({"result": {"status": "imported_existing_independent_PASS"}}, None, None),
                         "historical_import_no_new_execution")

    def test_cpu_counter_not_prorated_cross_window(self):
        r = self.record(start_epoch=3500, exit_epoch=3700, CPUUsageNSec=123000000000, cpu_counter_basis="terminal")
        snapshot = self.base([r])
        snapshot["captured_at_utc"] = "1970-01-01T01:10:00Z"
        windows = m.summarize(snapshot, 3000, 4000)["windows"]
        self.assertEqual(sum(w["hosts"]["h"]["whole_counter_cpu_seconds_known_in_window"] for w in windows), 0)

    def test_partial_cpu_is_separate(self):
        r = self.record(exit_epoch=None, observed_running=True, last_observed_epoch=200,
                        CPUUsageNSec=33000000000, cpu_counter_basis="partial")
        result = m.summarize(self.base([r]), 0, 1000)["windows"][0]["hosts"]["h"]
        self.assertEqual(result["partial_counter_cpu_seconds_known_in_window"], 33)
        self.assertEqual(result["whole_counter_cpu_seconds_known_in_window"], 0)

    def test_explicit_edge_not_name_or_owner_inference(self):
        a = self.record(owner="same", candidate_source_sha256="aaa")
        b = self.record(id="b", start_epoch=250, exit_epoch=300, owner="same", after=[{"id":"a"}], candidate_source_sha256="bbb")
        result = m.summarize(self.base([a, b]), 0, 1000)["windows"][0]
        self.assertEqual(result["median_explicit_dependency_gap_seconds"], 50)
        self.assertIsNone(result["median_exact_same_candidate_source_gap_seconds"])

    def test_second_precision_systemd_parse(self):
        self.assertEqual(m.iso(m.stamp("Thu 2026-10-01 09:58:03 UTC")), "2026-10-01T09:58:03Z")

    def test_refuse_old_topology_and_future_window(self):
        snapshot = self.base([])
        with self.assertRaises(ValueError):
            m.summarize(snapshot, -1, 1000)
        with self.assertRaises(ValueError):
            m.summarize(snapshot, 0, 1300)


if __name__ == "__main__":
    unittest.main()
