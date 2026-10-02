import copy
import unittest
from synthesis.performance import estimate


class PerformanceTests(unittest.TestCase):
    def fixture(self):
        probes = {name: {"fit_success": True, "hold_slack_ns": 0.1,
            "restricted_fmax_mhz": 120, "manifest": {"source_sha256": {name + ".sv": "abc"}},
            "alms": 10, "registers": 20, "ram_bits": 30, "ram_blocks": 2, "dsp_blocks": 1}
            for name in ("ntt", "crt", "carry")}
        regression = {"status": "pass", "source_sha256": {"rtl/kernel/" + name + ".sv": "abc" for name in probes},
            "metrics": {"n": 4, "fields": {str(k): {"total_cycles": 100} for k in range(3)},
                "carry": {"0": "PASS crt_cycles=10 carry_cycles=20", "1": "PASS crt_cycles=10 carry_cycles=25"}}}
        return probes, regression

    def test_cycle_math_and_conservative_postprocess(self):
        probes, regression = self.fixture()
        result = estimate(probes, regression, 100, base=2)
        self.assertEqual(result["models"]["serial_fields"]["kernel_cycles_per_square_dup"], 335)
        self.assertEqual(result["models"]["three_parallel_fields"]["kernel_cycles_per_square_dup"], 135)
        self.assertEqual(result["three_field_resource_sum_not_integrated_fit"]["alms"], 50)
        self.assertEqual(result["exponent_bits"], 5)

    def test_rejects_unverified_clock_and_stale_rtl(self):
        probes, regression = self.fixture()
        for clock in (0, 121, float("nan")):
            with self.assertRaises(ValueError): estimate(probes, regression, clock, base=2)
        stale = copy.deepcopy(regression)
        stale["source_sha256"]["rtl/kernel/ntt.sv"] = "wrong"
        with self.assertRaises(ValueError): estimate(probes, stale, 100, base=2)
        probes["carry"]["hold_slack_ns"] = -0.01
        with self.assertRaises(ValueError): estimate(probes, regression, 100, base=2)
        probes["carry"]["hold_slack_ns"] = 0.1
        probes["carry"]["fit_success"] = False
        with self.assertRaises(ValueError): estimate(probes, regression, 100, base=2)
