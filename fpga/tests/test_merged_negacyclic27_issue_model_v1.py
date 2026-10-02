"""Bounded arithmetic + full-size symbolic geometry, never local AW16 NTT."""
from random import Random
import unittest
from unittest.mock import patch

from fpga.reference import merged_negacyclic27_issue_model_v1 as issue
from fpga.reference import merged_negacyclic27_model as math


class MergedIssueTests(unittest.TestCase):
    def test_frozen_geometry_source_pin_and_orientation_split(self):
        guard = issue.source_guard()
        self.assertTrue(guard['frozen_engine_still_couples_stage_direction_and_arithmetic'])

    def test_physical_bank_pairs_cover_every_stage_once_independent_index_oracle(self):
        for n in (2, 4, 32, 256):
            for lanes in (1, 4, 16, 64):
                aw, kw, active, groups = issue.geometry(n, lanes)
                for stage in range(aw):
                    actual = []
                    for number in range(groups):
                        requests = issue.issue(n, lanes, stage, number)
                        self.assertEqual(len(requests), active)
                        for r in requests:
                            self.assertEqual(r.v_index, r.u_index + (1 << stage))
                            self.assertEqual(r.exponent, math.bit_reverse((n >> (stage + 1)) + r.root_group, aw))
                            # Independent bitwise bank fold, not the model's chunk-XOR helper.
                            bank = 0
                            for bit in range(aw):
                                bank ^= ((r.u_index >> bit) & 1) << (bit % kw)
                            self.assertEqual(bank, r.u_bank)
                            self.assertEqual(r.u_index >> kw, r.u_row)
                            actual.append((r.u_index, r.v_index))
                    expected = [(start + j, start + j + (1 << stage))
                                for start in range(0, n, 1 << (stage + 1)) for j in range(1 << stage)]
                    self.assertEqual(sorted(actual), expected)

    def test_compact_basis_roots_exact_direct_power_all_fields_and_directions(self):
        n = 32
        for field in math.FIELDS:
            psi = math.psi_for(n, field)
            for inverse in (False, True):
                for stage in range(5):
                    for number in range(4):
                        for r in issue.issue(n, 4, stage, number):
                            root = issue.factored_root(n, field, r, inverse)
                            self.assertEqual(root, field.encode(pow(psi, (-1 if inverse else 1) * r.exponent, field.p), 1))

    def test_banked_forward_is_exact_spectrum_not_only_roundtrip(self):
        rng = Random(101001)
        for n in (2, 8, 32):
            for field in math.FIELDS:
                digits = [rng.randrange(field.p) for _ in range(n)]
                expected = math.direct_spectrum(digits, field)
                for domain in (-1, 0, 1, 2):
                    values = [field.encode(v, domain) for v in digits]
                    actual = issue.banked_transform(values, field, lanes=4)
                    self.assertEqual(actual, [field.encode(v, domain) for v in expected])
                    self.assertEqual(issue.banked_transform(actual, field, inverse=True, lanes=4),
                                     [field.encode(v * n, domain) for v in digits])

    def test_banked_normalization_all_fields_domains_and_lane_geometries(self):
        for n in (32, 256):
            digits = [(j * 65537 + 29) % 1000000000 for j in range(n)]
            coefficients = math.direct_coefficients(digits)
            for field in math.FIELDS:
                expected = [v % field.p for v in coefficients]
                for domain in (-1, 0, 1, 2):
                    for lanes in (1, 4, 64):
                        self.assertEqual(issue.banked_square(digits, field, lanes=lanes, input_exponent=domain), expected)

    def test_typed_root_lane_sign_domain_and_upper_scale_faults(self):
        digits = [(j * 7919 + 37) % 104857601 for j in range(32)]
        expected = math.direct_coefficients(digits)
        for field in math.FIELDS:
            residues = [v % field.p for v in expected]
            for fault in ('lane-root-swap', 'within-group-cyclic-root', 'inverse-forward-root', 'ordinary-root', 'upper-unscaled'):
                math.compare(issue.banked_square(digits, field, lanes=4), residues, 'fresh-physical-control')
                with self.assertRaises(math.Mismatch) as caught:
                    math.compare(issue.banked_square(digits, field, lanes=4, mutant=fault), residues, fault)
                self.assertEqual(caught.exception.kind, fault)

    def test_batch_field_direction_stage_issue_mask_and_lane_tags(self):
        from copy import deepcopy
        field = math.FIELDS[0]
        control = issue.root_batch(32, 4, 0, 1, field)
        self.assertTrue(issue.check_root_batch(control, 32, 4, 0, 1, field))
        for tag_index in (0, 1, 2, 3, 4, 5):
            mutant = deepcopy(control)
            mutant['tag'][tag_index] += 1
            with self.assertRaises(math.Mismatch) as caught:
                issue.check_root_batch(mutant, 32, 4, 0, 1, field)
            self.assertEqual(caught.exception.kind, 'physical-root-tag')
        for key in ('mask', 'roots', 'coordinates'):
            mutant = deepcopy(control)
            if key == 'mask':
                mutant[key][0] = False
            else:
                mutant[key].reverse()
            with self.assertRaises(math.Mismatch) as caught:
                issue.check_root_batch(mutant, 32, 4, 0, 1, field)
            self.assertEqual(caught.exception.kind, 'physical-root-' + key)

    def test_aw16_geometry_and_storage_ledger_no_numeric_field_work(self):
        with patch.object(math.Field, 'mont', side_effect=AssertionError('no fullsize numeric root work')):
            ledger = issue.ledger()
            self.assertEqual(ledger['issues_per_stage'], 512)
            self.assertEqual(ledger['compact_basis_words_all_three_fields_both_directions'], 96)
            self.assertEqual(ledger['compact_basis_raw_bits'], 2592)
            self.assertEqual(ledger['distinct_merged_roots_per_issue_by_ascending_stage'], [64, 32, 16, 8, 4, 2] + [1] * 10)
            self.assertEqual(ledger['distinct_root_deliveries_per_direction'], 69632)
            self.assertEqual(ledger['mandatory_final_upper_normalizations_per_field'], 32768)
            for stage in range(16):
                for number in (0, 1, 127, 255, 511):
                    requests = issue.issue(65536, 64, stage, number)
                    self.assertEqual(len({r.exponent for r in requests}), ledger['distinct_merged_roots_per_issue_by_ascending_stage'][stage])
                    for r in requests:
                        self.assertEqual(r.exponent, math.bit_reverse((65536 >> (stage + 1)) + r.root_group, 16))
        with patch.object(math.platform, 'system', return_value='Darwin'):
            with self.assertRaisesRegex(RuntimeError, 'requires aethia'):
                issue.banked_transform([0] * 65536, math.FIELDS[0])

    def test_aw16_exhaustive_symbolic_pairs_rows_roots_no_numeric_transform(self):
        n = 65536
        with patch.object(math.Field, 'mont', side_effect=AssertionError('symbolic only')):
            for stage in range(16):
                upper = set()
                per_bank_rows = [set() for _ in range(128)]
                for number in range(512):
                    requests = issue.issue(n, 64, stage, number)
                    self.assertEqual(len({r.exponent for r in requests}), 1 << max(0, 6 - stage))
                    for r in requests:
                        self.assertNotIn(r.u_index, upper)
                        upper.add(r.u_index)
                        self.assertEqual(r.exponent, math.bit_reverse((n >> (stage + 1)) + r.root_group, 16))
                        for bank, row in ((r.u_bank, r.u_row), (r.v_bank, r.v_row)):
                            self.assertNotIn(row, per_bank_rows[bank])
                            per_bank_rows[bank].add(row)
                self.assertEqual(upper, {i for i in range(n) if not i & (1 << stage)})
                self.assertTrue(all(rows == set(range(512)) for rows in per_bank_rows))


if __name__ == '__main__':
    unittest.main()
