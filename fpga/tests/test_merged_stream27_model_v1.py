"""Small bit-exact S-M2 checks + scalar full-N layout, no native/HDL command."""
from random import Random
import unittest

from fpga.reference import merged_stream27_model_v1 as stream
from fpga.reference import merged_negacyclic27_model as math
from fpga.reference import stream_ntt_schedule as schedule
from fpga.reference import stream_ntt_blockcarry_model as block


class MergedStreamTests(unittest.TestCase):
    def test_source_pins_and_pass_geometry(self):
        self.assertEqual(len(stream.source_guard()), 2)
        for n in (32, 256):
            for p in (8, 16):
                for inverse in (False, True):
                    plan = stream.topology(n, p, inverse=inverse)
                    reference = schedule.transform(n, p, inverse=inverse, values=None)
                    self.assertEqual(plan['direction'], 'GS' if inverse else 'CT')
                    for a, b in zip(plan['stages'], reference['stages']):
                        for key in ('lane_bits', 'time_bits', 'target_index_bit', 'shuffle_depth_per_buffer'):
                            self.assertEqual(a[key], b[key])

    def test_group_roots_direct_exponent_per_physical_row_lane(self):
        for n in (32, 256):
            for p in (8, 16):
                for inverse in (False, True):
                    plan = stream.topology(n, p, inverse=inverse)
                    for spec in plan['stages']:
                        stage, bit = spec['stage'], spec['target_index_bit']
                        for row in range(n // p):
                            address = stream.root_address(plan, stage, row)
                            for port, (upper, lower) in enumerate(spec['pairs']):
                                index = schedule.index_of(row, upper, spec['lane_bits'], spec['time_bits'])
                                self.assertEqual(index ^ (1 << bit), schedule.index_of(row, lower, spec['lane_bits'], spec['time_bits']))
                                expected = math.bit_reverse((n >> (bit + 1)) + (index >> (bit + 1)), plan['aw'])
                                self.assertEqual(stream.root_exponent(plan, stage, spec['root_stream_for_pair'][port], address), expected)

    def test_forward_exact_spectrum_and_inverse_order_all_fields_domains(self):
        rng = Random(101019)
        for n in (32, 64):
            for p in (8, 16):
                digits = [rng.randrange(1000000000) for _ in range(n)]
                for field, f in enumerate(math.FIELDS):
                    expected = math.direct_spectrum(digits, f)
                    for domain in (-1, 0, 1, 2):
                        encoded = [f.encode(d, domain) for d in digits]
                        values = stream.transform(encoded, p, field, input_domain=domain)
                        self.assertEqual(values, [f.encode(x, domain) for x in expected])
                        self.assertEqual(stream.transform(values, p, field, inverse=True), [f.encode(n * d, domain) for d in digits])

    def test_last_GS_upper_and_lower_normalization_schoolbook_all_domains(self):
        for n in (32, 256):
            digits = [(i * 65537 + 19) % 1000000000 for i in range(n)]
            expected = math.direct_coefficients(digits)
            for p in (8, 16):
                for field, f in enumerate(math.FIELDS):
                    for domain in (-1, 0, 1, 2):
                        self.assertEqual(stream.square(digits, p, field, input_domain=domain), [x % f.p for x in expected])
                        self.assertEqual(stream.square(digits, p, field, input_domain=domain, fold_double=1), [2 * x % f.p for x in expected])

    def test_typed_wrong_parent_roots_address_sign_and_missing_upper_scale(self):
        digits = [(i * 7919 + 37) % 104857601 for i in range(256)]
        expected = math.direct_coefficients(digits)
        for p in (8, 16):
            for field, f in enumerate(math.FIELDS):
                residues = [x % f.p for x in expected]
                for fault in ('old-cyclic-roots', 'physical-row-address', 'inverse-forward-root', 'upper-unscaled'):
                    math.compare(stream.square(digits, p, field), residues, 'fresh-S-M2-control')
                    with self.assertRaises(math.Mismatch) as caught:
                        math.compare(stream.square(digits, p, field, mutant=fault), residues, fault)
                    self.assertEqual(caught.exception.kind, fault)

    def test_sparse_corrections_and_explicit_folded_doubling_bound(self):
        for n in (32, 256):
            for p in (8, 16):
                proof = block.proof(n, p, 1000000000)
                state = block.proposal.BlockState(tuple((i * 8191 + 17) % 1000000000 for i in range(n)),
                    1000000000, tuple(((-1) ** i) * 997 for i in range(p)),
                    tuple(((-1) ** (i + 1)) * min(123, proof['c1_abs_max']) for i in range(p)))
                expected = math.direct_coefficients(state.effective())
                for double in (0, 1):
                    ordinary = stream.block_state_square(state, double_bit=double)
                    folded = stream.block_state_square(state, double_bit=double, doubling='normalization')
                    self.assertEqual(ordinary, [x * (1 << double) for x in expected])
                    self.assertEqual(folded, ordinary)
        # A valid undoubled centered coefficient need not remain centered when doubled.
        coefficient = math.HALF // 2 + 1
        planes = [[coefficient % f.p] for f in math.FIELDS]
        doubled_planes = [[2 * coefficient % f.p] for f in math.FIELDS]
        integer_double = stream.centered_recover(planes, double_bit=1)
        with self.assertRaisesRegex(ValueError, 'NEEDS_CENTERED_BOUND'):
            stream.centered_recover(doubled_planes, double_bit=1, doubling='normalization')
        unsafe_fold = stream.centered_recover(doubled_planes, double_bit=0, doubling='normalization')
        self.assertNotEqual(unsafe_fold, integer_double)

    def test_scalar_fullN_layout_and_no_numeric_transform_admission(self):
        for p in (8, 16):
            layout = stream.root_layout(65536, p, 0)
            self.assertEqual(layout['IO_twist_untwist_root_tables'], 0)
            self.assertEqual(layout['normalization_upper_multipliers'], p // 2)
            self.assertEqual(layout['net_removed_twist_untwist_multiplier_lanes'], 3 * p // 2)
            self.assertEqual(layout['files'], {})
            self.assertFalse(layout['full_N_numeric_NTT_performed'])
        with self.assertRaisesRegex(ValueError, 'SMALL_NUMERIC_ONLY'):
            stream.transform([0] * 65536)
        with self.assertRaisesRegex(ValueError, 'EXPLICIT_ONLY'):
            stream.root_layout(65536, 8, 0, emit_words=True)


if __name__ == '__main__':
    unittest.main()
