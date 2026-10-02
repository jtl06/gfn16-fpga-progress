import random
import unittest

from fpga.reference import track_a4_blockcarry_model as m


class A4BlockcarryTests(unittest.TestCase):
    def test_all_geometries_all_addresses_and_ports(self):
        for aw in range(5, 17):
            n = 1 << aw
            s = m.schedule(n)
            self.assertEqual(s["issue_stalls"], 0)
            self.assertEqual(s["post_ntt_clocks"], n//16+58)
            self.assertEqual(s["same_address_collisions"], 0)
            self.assertLess(s["boundary_pair_ready_edge"], s["patch_launch_edge"])
            self.assertTrue(s["eligible"])
            self.assertEqual([e["read_offset"] for e in s["events"] if e["read_offset"] is not None], list(range(n//16)))
            self.assertEqual([e["write_offset"] for e in s["events"] if e["write_offset"] is not None], list(range(n//16)))

    def test_bank_counterexample_to_legacy_carry_and_vector_routes(self):
        addresses = m.address_row(65536, 0)
        self.assertEqual(len({a % 16 for a in addresses}), 1)
        self.assertEqual(len({m.bank_of(a) for a in addresses}), 16)
        self.assertGreater(m.schedule(independent_ports=False)["issue_stalls"], 0)
        # Block lane bits 0..3 become bank bits 5,6,0,1 at AW16.
        self.assertEqual([m.bank_of(4096 << bit) for bit in range(4)], [32, 64, 1, 2])

    def test_scalar_bounds_and_patch_range(self):
        for n in (32, 64, 256, 65536):
            for base in (m.arithmetic.minimum_base(n, 16), 10**9):
                m.bounds(n, base)
        self.assertEqual(m.arithmetic.minimum_base(32, 16), 300)
        with self.assertRaises(ValueError):
            m.bounds(32, 299)
        # d+c0 cannot be passed to either existing digit/correction guard.
        self.assertEqual((10**9-1)*2, 1999999998)

    def test_chains_direct_integer_and_patched_residue(self):
        rng = random.Random(20261001)
        for n in (32, 64, 128):
            for base in (m.arithmetic.minimum_base(n, 16), 10**9):
                digits = [rng.randrange(base) for _ in range(n)]
                state = m.arithmetic.load(digits, base, 16)
                modulus = base**n+1
                value = sum(d*base**i for i, d in enumerate(digits))
                for bit in (0, 1, 1, 0):
                    coefficients = m.direct_square(state, bit)
                    nxt, stats = m.arithmetic.proposal.carry_split(coefficients, base, 16)
                    serial, ends = m.arithmetic.proposal.carry_serial(coefficients, base, 16)
                    self.assertEqual(nxt, serial)
                    self.assertEqual(ends, stats["block_carries"])
                    value = value*value*(1 << bit) % modulus
                    canonical = nxt.canonical()
                    self.assertEqual(sum(d*base**i for i, d in enumerate(canonical)) % modulus, value)
                    for row, (p, _) in zip(m.patch_residues(nxt), m.arithmetic.core.FIELDS):
                        self.assertEqual(row, [d % p for d in nxt.effective()])
                    state = nxt

    def test_canonical_minus_one_and_mutation_controls(self):
        state = m.arithmetic.load([-1]+[0]*31, 300, 16)
        self.assertEqual(state.canonical(), [-1]+[0]*31)
        p = m.bounds(32, 300)
        coefficients = [p["doubled_coefficient_bound"]] * 32
        state, _ = m.arithmetic.proposal.carry_split(coefficients, 300, 16)
        good = m.patch_residues(state)
        for mutation in ("drop-boundary", "drop-c1", "wrong-wrap-sign"):
            self.assertNotEqual(m.patch_residues(state, mutation), good)

    def test_extreme_coefficients_boundary_split_and_cell_admission(self):
        for n in (32, 64, 256):
            for base in (m.arithmetic.minimum_base(n, 16), 10**9):
                proof = m.bounds(n, base)
                bound = proof["doubled_coefficient_bound"]
                for pattern in ((bound,), (-bound,), (bound, -bound), (-bound, bound)):
                    values = (list(pattern)*(n//len(pattern)))
                    state, stats = m.arithmetic.proposal.carry_split(values, base, 16)
                    serial, ends = m.arithmetic.proposal.carry_serial(values, base, 16)
                    self.assertEqual(state, serial)
                    self.assertEqual(ends, stats["block_carries"])
                    q_cell = 2*n+23*16
                    for k, (raw0, raw1) in enumerate(stats["raw_boundary_pairs"]):
                        self.assertGreaterEqual(raw0, -q_cell)
                        self.assertLessEqual(raw0, 2*(base-1)+q_cell)
                        adjust, low = divmod(raw0, base)
                        self.assertIn(adjust, range(-2, 4))
                        dest, sign = (k+1)%16, (-1 if k==15 else 1)
                        self.assertEqual(state.c0[dest], sign*low)
                        self.assertEqual(state.c1[dest], sign*(raw1+adjust))

    def test_cancellation_removes_future_commits(self):
        for n in (32, 65536):
            clean = m.schedule(n)
            for edge in (0, 1, clean["last_read_edge"], clean["last_normal_write_edge"],
                         clean["patch_launch_edge"], clean["patch_write_edges"][0], clean["check_edge"]):
                cancelled = m.schedule(n, cancel_edge=edge)
                self.assertFalse(cancelled["eligible"])
                self.assertTrue(all(e["edge"] < edge for e in cancelled["events"]))
                restart = m.schedule(n, epoch=2)
                self.assertTrue(restart["eligible"])
                self.assertTrue(all(e["epoch"] == 2 for e in restart["events"]))

    def test_no_full_size_numeric_work(self):
        state = m.arithmetic.load([0]*65536, 10**9, 16)
        with self.assertRaisesRegex(ValueError, "N<=256"):
            m.direct_square(state)
        with self.assertRaisesRegex(ValueError, "N<=256"):
            m.patch_residues(state)


if __name__ == "__main__":
    unittest.main()
