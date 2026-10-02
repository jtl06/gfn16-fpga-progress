import copy
import unittest
from synthesis.integrated_performance import estimate


class IntegratedPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.probe = {"fit_success": True, "hold_slack_ns": .02, "restricted_fmax_mhz": 101,
                      "manifest": {"target": "square_core", "address_width": 16,
                                   "source_sha256": {"core.sv": "abc"}},
                      **{k: 1 for k in ("alms", "registers", "ram_bits", "ram_blocks", "dsp_blocks")}}
        self.regression = {"status": "passed", "sources": {"rtl/kernel/core.sv": "abc"}}
        self.samples = [{"case":"full-random-s0-d0", "n": 65536, "base": 604832956, "cycles": 2424980,
                         "conversion": 65541, "roots": 262152, "ntt": 1441753,
                         "crt": 65598, "carry": 589936}]
        self.regression["metrics"]=copy.deepcopy(self.samples)

    def test_integrated_cycles_not_component_sum(self):
        result = estimate(self.probe, self.regression, self.samples, 100)
        self.assertEqual(result["exponent_bits"], 1911814)
        self.assertAlmostEqual(result["seconds_per_square_sample_max"], .0242498)
        self.assertGreater(result["speedup_vs_old_serial_100mhz"], 13)
        self.assertLess(result["approx_prp_hours_sample_max"], 13)

    def test_rejects_unverified_clock_or_sources(self):
        for clock in (102, 0, float("nan")):
            with self.assertRaises(ValueError): estimate(self.probe, self.regression, self.samples, clock)
        bad = copy.deepcopy(self.regression); bad["sources"]["rtl/kernel/core.sv"] = "stale"
        with self.assertRaises(ValueError): estimate(self.probe, bad, self.samples, 100)
        self.probe["hold_slack_ns"] = -.01
        with self.assertRaises(ValueError): estimate(self.probe, self.regression, self.samples, 100)

    def test_rejects_partial_or_inconsistent_samples(self):
        with self.assertRaises(ValueError): estimate(self.probe, self.regression, [], 100)
        self.samples[0]["ntt"] += 1
        with self.assertRaises(ValueError): estimate(self.probe, self.regression, self.samples, 100)

    def test_rejects_unmeasured_samples_or_mode_mismatch(self):
        self.samples[0]["ntt"]-=100
        self.samples[0]["cycles"]-=100
        with self.assertRaises(ValueError): estimate(self.probe, self.regression, self.samples, 100)
        self.samples=copy.deepcopy(self.regression["metrics"])
        self.regression["configuration"]={"difdit":True,"ntt_lanes":1}
        with self.assertRaises(ValueError): estimate(self.probe, self.regression, self.samples, 100)

    def cached_fixture(self):
        self.probe["manifest"]["target"] = "square_core_cached4_prefix"
        self.regression["configuration"] = {"difdit": True, "ntt_lanes": 4, "prefix_carry": True, "root_cache": True}
        cold = dict(self.samples[0], cycles=836026, ntt=311545, carry=131190,
                    cache_before=0, root_cache_warm=False, root_loads=4, root_hits=0)
        warm = dict(cold, case="full-random-s1-d1", cycles=573874, roots=0,
                    cache_before=15, root_cache_warm=True, root_loads=0, root_hits=4)
        self.samples = [cold, warm]
        self.regression["metrics"] = copy.deepcopy(self.samples)

    def test_cached_chain_uses_one_cold_start(self):
        self.cached_fixture()
        result = estimate(self.probe, self.regression, self.samples, 100)
        cached = result["cached_chain_projection"]
        self.assertEqual(cached["total_cycles"], 836026 + 1911813 * 573874)
        self.assertLess(cached["approx_prp_hours"], result["approx_prp_hours_sample_max"])

    def test_cache_metadata_cannot_be_spoofed(self):
        self.cached_fixture()
        self.samples[0]["cache_before"] = 15
        with self.assertRaises(ValueError): estimate(self.probe, self.regression, self.samples, 100)
        self.cached_fixture()
        self.samples[1]["root_hits"] = self.regression["metrics"][1]["root_hits"] = 3
        with self.assertRaises(ValueError): estimate(self.probe, self.regression, self.samples, 100)

    def test_cached_projection_requires_both_measured_states(self):
        self.cached_fixture()
        result = estimate(self.probe, self.regression, self.samples[1:], 100)
        self.assertIsNone(result["cached_chain_projection"])

    def test_legacy_manifest_defaults_remain_explicitly_compatible(self):
        self.probe["manifest"]["core_parameters"] = {
            "DIFDIT": 0, "NTT_LANES": 1, "PREFIX_CARRY": 0, "ROOT_CACHE": 0,
        }
        estimate(self.probe, self.regression, self.samples, 100)
        self.probe["manifest"]["core_parameters"]["CARRY_LANES"] = 4
        with self.assertRaises(ValueError): estimate(self.probe, self.regression, self.samples, 100)

    def test_unknown_architecture_flag_cannot_silently_match_old_fit(self):
        self.regression["configuration"] = {"future_vector_mode": True}
        with self.assertRaises(ValueError): estimate(self.probe, self.regression, self.samples, 100)

    def test_vector_and_scalar_boundaries_cannot_share_fit_evidence(self):
        self.cached_fixture()
        self.probe["manifest"]["target"]="square_core_banked4_carry4"
        self.regression["configuration"].update(banked_ntt=True,carry_lanes=4,vector_io=True)
        with self.assertRaises(ValueError):estimate(self.probe,self.regression,self.samples,100)
        self.probe["manifest"]["target"]="square_core_vector4"
        estimate(self.probe,self.regression,self.samples,100)

    def test_retimed_and_baseline_cores_cannot_share_fit_evidence(self):
        self.cached_fixture()
        self.probe["manifest"]["target"]="square_core_vector4"
        self.regression["configuration"].update(banked_ntt=True,carry_lanes=4,
                                                vector_io=True,fast_arith=True)
        with self.assertRaises(ValueError):estimate(self.probe,self.regression,self.samples,100)
        self.probe["manifest"]["target"]="square_core_fast4"
        estimate(self.probe,self.regression,self.samples,100)
        self.regression["configuration"]["fast_arith"]=False
        with self.assertRaises(ValueError):estimate(self.probe,self.regression,self.samples,100)

    def test_banked_lane_configuration_cannot_be_inferred_from_target_only(self):
        self.cached_fixture()
        self.probe["manifest"]["target"] = "square_core_banked4_carry4"
        with self.assertRaises(ValueError): estimate(self.probe, self.regression, self.samples, 100)
        self.regression["configuration"].update(banked_ntt=True, carry_lanes=4)
        estimate(self.probe, self.regression, self.samples, 100)
        self.probe["manifest"]["core_parameters"] = {
            "DIFDIT": 1, "NTT_LANES": 4, "PREFIX_CARRY": 1, "ROOT_CACHE": 1,
        }
        with self.assertRaises(ValueError): estimate(self.probe, self.regression, self.samples, 100)

    def test_derived_adapter_metadata_is_checked_not_ignored(self):
        from synthesis.configuration import CORE_CONFIGS
        self.probe["manifest"]["target"]="square_core_fast64_carry16"
        self.regression["configuration"]={k.lower():v for k,v in CORE_CONFIGS["square_core_fast64_carry16"].items()}
        with self.assertRaises(ValueError):estimate(self.probe,self.regression,self.samples,100)
        config=self.regression["configuration"]
        config.update(io_lanes=16,host_adapter=True)
        estimate(self.probe,self.regression,self.samples,100)
        for key,value in (("io_lanes",64),("io_lanes",True),("host_adapter",False),("host_adapter",1)):
            bad=copy.deepcopy(self.regression);bad["configuration"][key]=value
            with self.assertRaises(ValueError):estimate(self.probe,bad,self.samples,100)
