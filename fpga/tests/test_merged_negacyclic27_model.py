"""A10 bounded arithmetic/source tests; never execute full-N numeric NTT here."""
from pathlib import Path
from random import Random
from unittest.mock import patch
import unittest

from fpga.reference import merged_negacyclic27_model as m
from fpga.reference import stream_ntt_model as frozen
from fpga.tools import run_merged_negacyclic27_software_gate as gate

ROOT = Path(__file__).resolve().parents[1]
FAULTS = ("forward-inverse-root", "inverse-forward-root", "wrong-root-index",
          "natural-spectrum", "ordinary-root", "r2-first-stage",
          "missing-normalization", "normalization-r", "upper-unscaled")


class MergedNegacyclicTests(unittest.TestCase):
    def test_constants_and_scalar_fullsize_precision(self):
        self.assertEqual(m.PROFILE, "merged-negacyclic27-ctgs-ordinary-v1")
        self.assertEqual(m.MODULUS, 487945222748036195811329)
        self.assertLess(2 * 65536 * (10**9 - 1)**2, m.HALF)
        for field in m.FIELDS:
            self.assertEqual(field.p * field.q & m.MASK, 1)
            self.assertLess(field.p, 1 << 27)
            for aw in range(1, 17):
                self.assertEqual(pow(m.psi_for(1 << aw, field), 1 << aw, field.p), field.p - 1)

    def test_exact_positive_inverse_montgomery_all_domains(self):
        rng = Random(93010)
        for field in m.FIELDS:
            values = [0, 1, field.p-1, field.p, field.p+1, -1, 999999999]
            for e in (-1, 0, 1, 2):
                for f in (-1, 0, 1, 2):
                    for a, b in zip(values, reversed(values)):
                        actual = field.mont(field.encode(a, e), field.encode(b, f))
                        self.assertEqual(actual, field.encode(a*b, e+f-1))
            for _ in range(100):
                a, b = rng.randrange(field.p), rng.randrange(field.p)
                self.assertEqual(field.mont(a, b), a*b*pow(m.RADIX, -1, field.p) % field.p)
            with self.assertRaises(ValueError):
                field.mont(field.p, 1)

    def test_order_and_forward_not_just_roundtrip(self):
        rng = Random(1010)
        for n in (2, 4, 8, 32, 256):
            for field in m.FIELDS:
                values = [rng.randrange(field.p) for _ in range(n)]
                forward = m.merged_forward(values, field)
                self.assertEqual(forward, m.direct_spectrum(values, field))
                self.assertEqual(m.merged_inverse(forward, field), [x*n % field.p for x in values])
                # Parent spectrum is the SAME permutation, in exponent +1.
                self.assertEqual(m.current_parent_forward(values, field),
                                 [field.encode(x, 1) for x in forward])

    def test_coefficients_all_three_fields_and_montgomery_domains(self):
        rng = Random(1110)
        for n in (2, 4, 32, 256):
            digits = [rng.randrange(1_000_000_000) for _ in range(n)]
            expected = m.direct_coefficients(digits)
            for field in m.FIELDS:
                residues = [x % field.p for x in expected]
                self.assertEqual(m.current_parent_square(digits, field), residues)
                for e in (-1, 0, 1, 2):
                    self.assertEqual(m.field_square(digits, field, input_exponent=e), residues)
                self.assertEqual(m.field_square(digits, field, normalization="pre-crt"), residues)
            self.assertEqual(m.square_coefficients(digits), expected)

    def test_each_fault_fresh_positive_control_all_three_fields(self):
        digits = [(i*7919+37) % 104857601 for i in range(32)]
        expected = m.direct_coefficients(digits)
        for field in m.FIELDS:
            residues = [x % field.p for x in expected]
            for fault in FAULTS:
                m.compare(m.field_square(digits, field), residues, "fresh-control")
                with self.assertRaises(m.Mismatch) as caught:
                    m.compare(m.field_square(digits, field, mutant=fault), residues, fault)
                self.assertEqual(caught.exception.kind, fault)

    def test_archived_aw5_exact_output_vectors(self):
        path = ROOT / "results/throughput-20260929/core27-prefill-aw5-normal-v2/vectors.txt"
        count = 0
        for case in frozen.normal_cases(path):
            coefficients = [x*(1 << case["double_bit"]) for x in m.square_coefficients(case["digits"])]
            self.assertEqual(frozen.exact_carry(coefficients, case["base"]), list(case["expected"]))
            count += 1
        self.assertEqual(count, 568)

    def test_cycle_delta_is_conditional_and_counts_upper_scale(self):
        c = m.cycle_work()
        self.assertEqual(c["parent_ntt_cycles"], 20558)
        self.assertEqual(c["parent_transform_setup_cycles"], 295)
        self.assertEqual(c["two_pass_only_saving"], 2062)
        self.assertEqual(c["removed_point_setup_and_control"], 524)
        self.assertEqual(c["delta_at_inherited_root_setup_parallel"], 2586)
        self.assertEqual(c["delta_at_inherited_root_setup_pre_crt"], 2582)
        self.assertEqual(c["delta_at_inherited_root_setup_serialized"], 2074)
        self.assertEqual(c["montgomery_ops_per_field"],
                         dict(parent=1245184, folded=1146880, pre_crt=1179648))
        self.assertIn("Smerged", c["folded_parallel_delta_formula"])

    def test_source_orientation_domain_and_cycles_are_still_matched(self):
        butterfly = (ROOT / "rtl/kernel/genefer_ntt_banked27_engine.sv").read_text()
        self.assertIn("pre_v<=dif ? (u>=v ? u-v : u+P-v) : v;", butterfly)
        self.assertIn("y0<=dif_pipe[4] ? prefix_pipe[4] : post_sum_reduced;", butterfly)
        engine = (ROOT / "rtl/kernel/genefer_ntt_banked27_prefetch_r2_orient8_rootfused_engine.sv").read_text()
        self.assertIn("assign next_stage=active_dif ? stage_bit-5'd1 : stage_bit+5'd1;", engine)
        self.assertIn(".dif(bf_in_valid[lane] && active_dif)", engine)
        root = (ROOT / "rtl/kernel/genefer_root_profile27_r2_rom.sv").read_text()
        self.assertIn("factor=key==0 ? R2 : IN;", root)
        top = (ROOT / "rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill.sv").read_text()
        self.assertIn(".inverse(1'b0),.dif(step==1)", top)
        self.assertIn("ntt_op=step==0 || step==4 ? 2'd2 : step==2 ? 2'd1 : 2'd0;", top)

    def test_fullsize_numeric_execution_refuses_mac_before_work(self):
        with patch.object(m.platform, "system", return_value="Darwin"):
            with self.assertRaisesRegex(RuntimeError, "requires aethia"):
                m.merged_forward([0]*65536, m.FIELDS[0])
        # Scalar proof/cycle work can run locally, without any transform.
        self.assertEqual(m.cycle_work()["parent_ntt_cycles"], 20558)

    def test_fullsize_gate_preparation_pins_and_preexecution_host_guard(self):
        manifest = gate.prepare(ROOT)
        self.assertEqual(manifest["status"], "prepared_not_executed")
        self.assertEqual(manifest["vectors_sha256"], gate.VECTOR_SHA)
        self.assertEqual(manifest["sources"], gate.pins(ROOT))
        self.assertEqual((manifest["cases"], manifest["fields"]), (12, 3))
        with patch.object(gate.platform, "system", return_value="Darwin"):
            with self.assertRaisesRegex(ValueError, "aethia only"):
                gate.run(ROOT, None, None, None)


if __name__ == "__main__":
    unittest.main()
