"""N1 symbolic and bounded bit-exact tests; never HDL or full-N numeric NTT."""
import unittest

from fpga.reference import merged_negacyclic27_model as arith
from fpga.reference import radix22_track_a_model_v1 as model


class Radix22Tests(unittest.TestCase):
    def test_source_calibration_pins_and_counts(self):
        ledger = model.fit_calibration()
        self.assertEqual(ledger['butterflies']['nodes'], 192)
        self.assertEqual(ledger['butterflies']['ALMs_needed'], 73517.3)
        self.assertEqual(ledger['multiplier_children']['ALMs_needed'], 20875.3)
        self.assertEqual(ledger['root_recurrences']['ALMs_needed'], 39414.0)

    def test_all_runtime_fold_boundaries_symbolically(self):
        for n in (4, 8, 16, 32, 64, 128, 256, 1024):
            for lanes in (2, 4, 16, 64):
                for high in range(1, n.bit_length()-1):
                    self.assertTrue(model.banking_gate(n, lanes, high)['all_data_banks_distinct'])

    def test_full_N_frozen_schedule_counterexamples_and_repair(self):
        for high in range(1, 16, 2):
            receipt = model.banking_gate(high=high)
            self.assertEqual(receipt['addresses_checked'], 65536)
            self.assertEqual(receipt['frozen_single_stage_batch_pair_closed'], high < 9)
            if high >= 9:
                witness = receipt['frozen_schedule_counterexample']
                self.assertEqual(witness['missing_partner'], witness['index'] ^ (1 << (high-1)))

    def test_wrong_pair_coordinates_fail(self):
        bad = model.paired_issue(65536, 64, 15, 0, mutant='keep-low-representative')
        banks = [model.physical.bank_of(a, 7) for a in bad.addresses]
        self.assertLess(len(set(banks)), len(banks))

    def test_packed_root_route_all_full_N_pairs(self):
        for high in range(1, 16, 2):
            for number in range(512):
                beat = model.paired_issue(65536, 64, high, number)
                h, l = model.beat_roots(65536, beat)
                self.assertEqual(model.packed_root_exponents(65536, 64, high, number),
                                 [(eh,) + el for eh, el in zip(h, l)])

    def test_bounded_bit_exact_CT_GS_vs_independent_oracles(self):
        self.assertTrue(model.small_numeric_gate()['passed'])

    def test_arithmetic_negative_controls(self):
        for field in arith.FIELDS:
            for n in (16, 32):
                digits = [(7*i*i+5*i+3) % field.p for i in range(n)]
                expected = [v % field.p for v in arith.direct_coefficients(digits)]
                self.assertNotEqual(model.fused_transform(digits, field, mutant='swap-low-roots'),
                                    arith.direct_spectrum(digits, field))
                self.assertNotEqual(model.fused_square(digits, field, mutant='omit-upper-normalization'),
                                    expected)

    def test_full_numeric_is_blocked_even_on_compute_host(self):
        with self.assertRaisesRegex(ValueError, 'limited to N256'):
            model.fused_transform([0]*512, arith.FIELDS[0])

    def test_calendar_drain_root_delay_and_bubbles(self):
        regular = model.spatial_schedule()
        self.assertEqual(regular['cycles'], 527)
        self.assertEqual(regular['outstanding_root_frames'], 7)
        self.assertEqual(regular['last']['commit']-regular['last']['read'], 14)
        delayed = model.spatial_schedule(gaps=((0, 2), (511, 3)))
        self.assertEqual(delayed['cycles']-regular['cycles'], 5)
        self.assertEqual(model.spatial_schedule(issue_interval=2)['cycles'], 1038)

    def test_cycles_and_NO_GO_resources_count_upper_normalizers(self):
        cycles = model.cycle_ledger()
        self.assertEqual(cycles['parent_ntt_cycles'], 20558)
        self.assertEqual(cycles['ntt_cycles_for_declared_calendar'], 9469)
        self.assertEqual(cycles['A4_warm_conditional'], 13631)
        area = model.resource_ledger()
        self.assertGreater(area['packed_ROM']['ALMs_needed_planning'], 320000)
        self.assertEqual(area['packed_ROM']['DSP_needed_proxy'], 930)
        self.assertEqual(area['duplicated_recurrence']['DSP_needed_proxy'], 1314)
        self.assertEqual(area['packed_ROM']['M20K_proxy'], 1293)
        self.assertEqual(area['packed_ROM']['decision'], 'NO_GO_canonical_conservative_selector_plan')


if __name__ == '__main__':
    unittest.main()
