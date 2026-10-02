import copy
import unittest

from fpga.reference import stream27_c2_state_analysis as m


class StateAnalysisTests(unittest.TestCase):
    def test_actual_report_source_binding_and_disjoint_total(self):
        result = m.analyze()
        self.assertEqual(result['validated_source_files'], 53)
        self.assertEqual(result['total_own_FF_delta'], 42506)
        for field in result['disjoint_field_delta_ALUT_FF'].values():
            self.assertEqual(sum(v[1] for v in field.values()), 12803)
            self.assertEqual(field['CT/GS stage tag pipes'][1], 3808)
            self.assertEqual(field['shuffle tag/control'][1], 1700)
        self.assertEqual(result['hypothesis']['payload_bits_per_field'], 5184)
        self.assertEqual(result['hypothesis']['minimum_conservative_reuse_gap'], 4254)
        self.assertIsNone(result['hypothesis']['ALM_or_LAB_credit'])
        self.assertEqual(result['synthesized_unit_counts'], {
            'correction transforms': 3, 'term product pools': 3, 'CRT lanes': 16,
            'carry lanes': 16, 'shared setup': 1, 'canonical scratch': 1, 'descriptor queues': 2})
        self.assertEqual(result['separate_RAM_bit_delta']['shadows'], 2097152)
        self.assertEqual(result['separate_RAM_bit_delta']['field delay/tag RAM'], 834768)
        self.assertEqual(result['separate_AUTO_or_M20K_bit_delta']['field delay/tag RAM'], 822528)
        self.assertEqual(result['separate_MLAB_bit_delta']['field delay/tag RAM'], 12240)
        self.assertEqual(result['disjoint_whole_delta_ALUT_FF']['carry'][1], 0)

    def test_two_banks_both_anchor_orders(self):
        for anchor in (0, 1):
            self.assertEqual(m.check_windows(m.windows((16, 16), anchor=anchor)), 4254)
        leases = m.logical_peak(m.windows((3, 3)))
        self.assertEqual(leases['peak'], 3)
        self.assertEqual(leases['witness']['tick'], 8459)
        self.assertEqual(len(leases['witness']['logical_banks']), 3)
        for frame in m.windows((3, 3)):
            self.assertEqual(frame['last_E4_product_write'], frame['last_coefficient_read'])
            self.assertEqual(frame['last_E4_product_write'] - frame['last_update_issue'], 4)

    def test_single_bank_initial_overlap_is_real(self):
        with self.assertRaisesRegex(ValueError, 'overwritten'):
            m.check_windows(m.windows((2, 2)), banks=1)

    def test_same_edge_tail_reuse_rejected(self):
        items = m.windows((2, 2))
        previous = next(v for v in items if v['context'] == 0 and v['ordinal'] == 0)
        later = next(v for v in items if v['context'] == 0 and v['ordinal'] == 1)
        later['begin'] = previous['end']
        with self.assertRaisesRegex(ValueError, 'overwritten'):
            m.check_windows(items)

    def test_wrong_context_storage_selector_rejected(self):
        items = copy.deepcopy(m.windows((2, 2)))
        for item in items:
            item['physical'] = 0
        with self.assertRaisesRegex(ValueError, 'overwritten'):
            m.check_windows(items)

    def test_bool_unbounded_or_inactive_anchor_rejected(self):
        for counts, anchor in (((True, 1), 0), ((17, 1), 0), ((0, 1), 0)):
            with self.assertRaises(ValueError):
                m.windows(counts, anchor=anchor)


if __name__ == '__main__':
    unittest.main()
