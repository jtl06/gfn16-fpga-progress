import random
import unittest
from reference.stream27_root_outputreg_contract import WeightPair, fields_with_weight_register
from reference import stream27_root_outputreg_bind as binding
from reference import stream27_shared_field_flags as fields
from reference import stream27_root_outputreg_fault_native as negative
from reference import stream27_comm_packed_bind as packed


class ContractTests(unittest.TestCase):
    def test_dense_gaps_reset_and_permuted_addresses(self):
        rng = random.Random(0x27A81)
        for rows in (4, 16, 256):
            bits = rows.bit_length() - 1
            for positions in (tuple(range(bits)), tuple(reversed(range(bits))), (bits - 1,)):
                words = [rng.getrandbits(216) for _ in range(1 << len(positions))]
                pair = WeightPair(words, rng.getrandbits(216), positions, rows)
                checked = 0
                for frame in range(7):
                    for row in range(rows):
                        weight = pair.edge(valid=True, first=row == 0)
                        checked += weight is not None
                    for gap in range(frame % 4):
                        # Unaccepted stale FIRST/data must not alter output hold.
                        weight = pair.edge(valid=False, first=bool(gap & 1))
                        checked += weight is not None
                checked += pair.edge() is not None
                self.assertEqual(pair.checked_products, 7 * rows)
                self.assertEqual(checked, 7 * rows)
                for reset_at in range(1, min(rows, 16)):
                    for row in range(reset_at):
                        pair.edge(valid=True, first=row == 0)
                    retained = pair.prefetch
                    pair.edge(rst_n=False, valid=True, first=True)
                    self.assertEqual(pair.prefetch, retained)
                    pair.edge(valid=True, first=True)
                    self.assertEqual(pair.edge(valid=True), pair.first)

    def test_multiplier_token_only_not_invalid_payload_reset(self):
        pair = WeightPair([7, 11, 19, 23], 3, (0, 1), 4)
        pair.edge(valid=True, first=True)
        self.assertEqual(pair.edge(valid=True), 3)
        pair.edge(rst_n=False)
        self.assertIsNotNone(pair.output)
        self.assertEqual(pair.old_pre_w, 0)
        self.assertIsNone(pair.edge())
        pair.edge(valid=True, first=True)
        self.assertEqual(pair.edge(), 3)

    def test_no_total_latency_or_authority_change(self):
        contract = fields_with_weight_register()
        self.assertEqual(contract['total_butterfly_edges'], 5)
        self.assertEqual(contract['II'], 1)
        self.assertIn('reset_and_registered_fault_authority', contract['unchanged'])

    def test_source_bind_default_and_exact_cohorts(self):
        for field in range(3):
            old = fields.prepare(256, 16, field, mode='warm', corr_serial_bfs=2,
                                 comm_stage_shared_mlab=1, mont_factored=1)
            self.assertEqual(binding.bind(old, enabled=0), old)
            new = binding.bind(old)
            self.assertEqual(new['geometry'], old['geometry'])
            self.assertEqual(new['parameters'], old['parameters'])
            self.assertEqual(new['root_weight_outputreg']['root_modules'], 15)
            self.assertEqual(new['root_weight_outputreg']['lazy_butterfly_instances'], 120)
            for name, text in old['files'].items():
                if name.startswith(('merged_stream27_root_library_', 'genefer_stream28_merged_')) or name == binding.OLD_BF + '.sv':
                    continue
                self.assertEqual(new['files'][name], text)
            self.assertIn('.rhs(root_delayed)', new['files'][binding.NEW_BF + '.sv'])
            self.assertNotIn('pre_w', new['files'][binding.NEW_BF + '.sv'])

    def test_negative_accepts_only_real_independent_data_rejection(self):
        self.assertRegex(negative.STEP, r'^[a-z][a-z0-9-]*$')
        self.assertIn('rc==1 && captured_out.str().empty()', negative.SHIM)
        self.assertIn('S4_DATA case=1 ', negative.SHIM)
        self.assertIn('return 41;', negative.SHIM)
        self.assertIn('return 90;', negative.SHIM)

    def test_packed_and_root_source_changes_commute(self):
        for field in range(3):
            parent = fields.prepare(256, 16, field, mode='warm', corr_serial_bfs=2,
                                    comm_stage_shared_mlab=1, mont_factored=1)
            first = binding.bind(packed.bind(parent))
            second = packed.bind(binding.bind(parent))
            self.assertEqual(first['files'], second['files'])
            self.assertEqual(first['geometry'], parent['geometry'])
            self.assertEqual(first['parameters'], parent['parameters'])
            self.assertEqual(first['top'], parent['top'])


if __name__ == '__main__':
    unittest.main()
