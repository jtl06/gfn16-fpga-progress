"""Atomic27 evidence checks. Every fitted probe below is SYNTHETIC TEST DATA.

Measured cycles come from archived simulation, but no test creates a real fit
result or writes a performance projection to the results directory.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from synthesis.integrated_performance import estimate
from synthesis.prepare import prepare


REPORTS=Path(__file__).resolve().parents[1]/"results/throughput-20260929/core27-final/normalized"
BASIS=[
    {"P":104857601,"Q":4190109697,"GENERATOR":3,"R2":45971250},
    {"P":69206017,"Q":4225761281,"GENERATOR":5,"R2":50081300},
    {"P":67239937,"Q":4227727361,"GENERATOR":10,"R2":63576045},
]
SOURCES={
    "genefer_montgomery_mul32_pipe.sv", "genefer_montgomery_mul27_sparse_pipe.sv",
    "genefer_digit_reduce27_pipe.sv", "genefer_sdp_ram32.sv",
    "genefer_ntt_banked27_engine.sv", "genefer_ntt_banked27_host_engine.sv",
    "genefer_mod64_pipe.sv", "genefer_crt3_27_pipe.sv",
    "genefer_carry_transfer_tree.sv", "genefer_sp_ram.sv", "genefer_div_recip_narrow.sv",
    "genefer_carry_prefix_vector_pipe_v2.sv", "genefer_square_core27.sv",
}


class Atomic27PerformanceTests(unittest.TestCase):
    def fixture(self,lanes=64):
        regression=json.loads((REPORTS/f"core27-{lanes}-16-report.json").read_text())
        samples=[copy.deepcopy(row) for row in regression["metrics"]
                 if row["n"]==65536 and row["base"]==604832956 and row["case"].startswith("full-random-")]
        probe={"fixture_kind":"SYNTHETIC TEST ONLY, NOT A FIT", "fit_success":True,
               "hold_slack_ns":0.02, "restricted_fmax_mhz":101,
               "manifest":{
                   "target":f"square_core27_ntt{lanes}_carry16", "top":"genefer_square_core27",
                   "address_width":16, "clock_period_ns":10,
                   "core_parameters":{"NTT_LANES":lanes},
                   "arithmetic_profile":"atomic27_cached_v1",
                   "core_field_basis":copy.deepcopy(BASIS), "core_montgomery_radix_bits":32,
                   "source_sha256":{name:regression["sources"]["rtl/kernel/"+name] for name in SOURCES},
               }}
        return probe,regression,samples

    def rejected(self,probe,regression,samples,clock=100):
        with self.assertRaises(ValueError):
            estimate(probe,regression,samples,clock)

    def test_both_complete_normalized_profiles_accept_synthetic_fit_only(self):
        for lanes,warm in ((16,94686),(64,36318)):
            with self.subTest(lanes=lanes):
                probe,regression,samples=self.fixture(lanes)
                self.assertTrue(samples)
                result=estimate(probe,regression,samples,100)
                self.assertEqual(result["status"],"integrated_simulation_and_fit_not_hardware")
                self.assertEqual(result["target"],probe["manifest"]["target"])
                self.assertEqual(result["arithmetic_profile"],"atomic27_cached_v1")
                cached=result["cached_chain_projection"]
                self.assertEqual(cached["warm_cycles_sample_max"],warm)
                self.assertEqual(cached["cold_cycles_sample_max"],warm+262152)
                self.assertEqual(cached["total_cycles"],262152+result["exponent_bits"]*warm)

    def test_synthetic_fixture_metadata_matches_actual_preparation_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            for lanes in (16,64):
                fixture=self.fixture(lanes)[0]["manifest"]
                prepared=prepare(Path(directory)/str(lanes),fixture["target"],aw=16,period=10)
                for key in ("target","top","address_width","clock_period_ns","core_parameters",
                            "arithmetic_profile","core_field_basis","core_montgomery_radix_bits"):
                    self.assertEqual(prepared[key],fixture[key])
                self.assertEqual(set(prepared["source_sha256"]),SOURCES)

    def test_every_basis_component_and_order_are_checked_on_both_sides(self):
        for lane in (16,64):
            for side in ("manifest","regression"):
                for index in range(3):
                    for key in ("P","Q","R2","GENERATOR"):
                        probe,regression,samples=self.fixture(lane)
                        basis=(probe["manifest"]["core_field_basis"] if side=="manifest"
                               else regression["atomic_profile"]["basis"])
                        basis[index][key if side=="manifest" else key.lower()]+=1
                        self.rejected(probe,regression,samples)
                probe,regression,samples=self.fixture(lane)
                basis=(probe["manifest"]["core_field_basis"] if side=="manifest"
                       else regression["atomic_profile"]["basis"])
                basis.reverse()
                self.rejected(probe,regression,samples)

    def test_profile_radix_bound_and_exposed_parameters_are_pinned(self):
        changes=[("manifest","arithmetic_profile","legacy"),
                 ("manifest","core_montgomery_radix_bits",27),
                 ("manifest","core_montgomery_radix_bits",32.0),
                 ("configuration","field_profile","sparse27-generated-v1"),
                 ("configuration","montgomery_radix_bits",27),
                 ("atomic_profile","radix_bits",27),
                 ("atomic_profile","crt_modulus",1),
                 ("atomic_profile","max_doubled_coefficient",1),
                 ("atomic_profile","exposed_parameters",["AW","NTT_LANES","FUSE_INPUT_MONT"])]
        for section,key,value in changes:
            probe,regression,samples=self.fixture()
            (probe[section] if section=="manifest" else regression[section])[key]=value
            self.rejected(probe,regression,samples)

    def test_architecture_flags_cannot_be_added_dropped_or_enabled(self):
        for lanes in (16,64):
            for flag in ("fuse_input_mont","stream_carry","generated_roots"):
                for mutation in (True,0,None):
                    probe,regression,samples=self.fixture(lanes)
                    if mutation is None: del regression["configuration"][flag]
                    else: regression["configuration"][flag]=mutation
                    self.rejected(probe,regression,samples)
            for key,value in (("future_flag",False),("ntt_lanes",4),("carry_lanes",4),
                              ("io_lanes",64),("host_adapter",lanes!=64),("root_cache",False)):
                probe,regression,samples=self.fixture(lanes)
                regression["configuration"][key]=value
                self.rejected(probe,regression,samples)
            probe,regression,samples=self.fixture(lanes)
            probe["manifest"]["core_parameters"]["FUSE_INPUT_MONT"]=0
            self.rejected(probe,regression,samples)

    def test_complete_source_closure_and_hash_match_required(self):
        for side in ("fit","simulation","both"):
            for mode in ("missing","extra","mismatch","invalid"):
                probe,regression,samples=self.fixture()
                dictionaries=[]
                if side in ("fit","both"): dictionaries.append((probe["manifest"]["source_sha256"],""))
                if side in ("simulation","both"): dictionaries.append((regression["sources"],"rtl/kernel/"))
                for hashes,prefix in dictionaries:
                    key=prefix+"genefer_square_core27.sv"
                    if mode=="missing": del hashes[key]
                    elif mode=="extra": hashes[prefix+"unvalidated.sv"]="0"*64
                    else: hashes[key]="bad" if mode=="invalid" else "0"*64
                if mode=="mismatch" and side=="both":
                    # Matching arbitrary valid hashes are not provenance authentication;
                    # the estimator checks source identity, not cryptographic signing.
                    continue
                self.rejected(probe,regression,samples)

    def test_sample_and_manifest_geometry_cannot_be_relabelled(self):
        for key,value in (("address_width",15),("top","genefer_square_core"),
                          ("target","square_core27_ntt32_carry16"),
                          ("core_parameters",{"NTT_LANES":16})):
            probe,regression,samples=self.fixture()
            probe["manifest"][key]=value
            self.rejected(probe,regression,samples)
        for key,value in (("n",32768),("base",97),("aw",15),("ntt_lanes",16),
                          ("io_lanes",64),("readback",False)):
            probe,regression,samples=self.fixture()
            samples[0][key]=value
            self.rejected(probe,regression,samples)
            probe,regression,samples=self.fixture()
            next(row for row in regression["metrics"] if row["case"]==samples[0]["case"] and row["n"]==65536)[key]=value
            self.rejected(probe,regression,samples)

    def test_unfitted_invalid_clock_or_failed_regression_stays_rejected(self):
        for key,value in (("fit_success",False),("hold_slack_ns",-.01),
                          ("hold_slack_ns",float("nan")),("restricted_fmax_mhz",99),
                          ("restricted_fmax_mhz",float("nan"))):
            probe,regression,samples=self.fixture()
            probe[key]=value
            self.rejected(probe,regression,samples)
        for clock in (0,102,float("nan"),float("inf")):
            self.rejected(*self.fixture(),clock)
        for period in (None,0,float("nan"),"5"):
            probe,regression,samples=self.fixture()
            probe["manifest"]["clock_period_ns"]=period
            self.rejected(probe,regression,samples)
        probe,regression,samples=self.fixture()
        regression["status"]="incomplete"
        self.rejected(probe,regression,samples)

    def test_atomic_metadata_cannot_relax_legacy_core_validation(self):
        probe,regression,samples=self.fixture()
        probe["manifest"]["target"]="square_core_fast64_carry16"
        self.rejected(probe,regression,samples)


if __name__=="__main__":
    unittest.main()
