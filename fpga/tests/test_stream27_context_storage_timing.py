import copy
import unittest

from fpga.reference import stream27_context_storage_timing_bind as b
from fpga.reference import stream27_context_storage_timing_native as n


class TimingStorageTests(unittest.TestCase):
    def test_disabled_exact_and_enabled_private_only(self):
        for stage in ('aw8', 'full'):
            _, _, parent = n.capture(stage)
            original = copy.deepcopy(parent)
            self.assertEqual(b.bind(parent), parent)
            source = b.bind(parent, enabled=1)
            self.assertEqual(parent, original)
            self.assertEqual(len(source['files']), 58)
            self.assertEqual(source['storage_contract']['unchanged'], 52)
            self.assertEqual(len(source['storage_contract']['changed']), 6)
            self.assertEqual(source['geometry'], parent['geometry'])

    def test_raw_selection_does_not_gain_write_or_cache_authority(self):
        _, _, source = n.role('aw8')
        text = source['files'][b.TERM + '_storage2_v1.sv']
        for anchor in ('if(bypass_data)current_term=product_data;',
                       "if(bypass)consumer_missing=1'b0;",
                       'assign cache_ready=product_slot &&',
                       'if(product_slot && bank_owner[prod_bank]==product_owner)begin',
                       'product_owner_bad=product_slot && bank_owner[prod_bank]!=product_owner;',
                       'bypass_data!=bypass'):
            self.assertIn(anchor, text)
        self.assertIn('context_data[0:1][0:3]', text)
        self.assertIn('prod_bank=product_owner[24]', text)
        self.assertIn('bank_owner[pw_bank]!=pointwise_owner', text)

    def test_all_bounded_closed_host_count_and_anchor_lifetimes(self):
        for stage, expected_gap, peak, last in (('aw8', 119, 2, 94), ('full', 4255, 3, 8302)):
            _, _, parent = n.capture(stage)
            for anchor in (0, 1):
                for active in range(1, 17):
                    for peer in range(17):
                        counts = (active, peer) if anchor == 0 else (peer, active)
                        proof = b.proof(parent['geometry'], counts, anchor)
                        if active > 1 or peer > 1:
                            self.assertEqual(proof['minimum_gap'], expected_gap)
                        self.assertLessEqual(proof['logical_peak'], peak)
                        self.assertEqual(proof['last_E4_product_write'], last)
                        self.assertEqual(proof['last_coefficient_read'], last)

    def test_full_tuple_wrap_cancel_reset_and_early_cache(self):
        owners = b.lifetime.PhysicalOwners()
        first, peer, following = (0, 0, 65535, 255), (1, 1, 9, 3), (2, 0, 0, 0)
        owners.reserve(first); owners.reserve(peer)
        self.assertFalse(owners.cache(first, physical_valid=False))
        with self.assertRaises(ValueError):
            owners.consume(first)
        self.assertTrue(owners.cache(first)); self.assertTrue(owners.cache(peer))
        self.assertFalse(owners.consume(first, enabled=False))
        self.assertTrue(owners.consume(peer))
        with self.assertRaises(ValueError):
            owners.reserve(following)
        owners.retire_raw(first); owners.reserve(following)
        self.assertFalse(owners.cache(first))
        self.assertFalse(owners.cache((0, 0, 0, 0)))
        owners.reset()
        self.assertFalse(owners.cache(following))

    def test_normal_cpp_oracle_steps_and_parameters_exact(self):
        for stage in ('aw8', 'full'):
            old, oldfiles, parent = n.capture(stage)
            manifest, files, source = n.role(stage)
            for name in (old['build']['cpp_source'],):
                self.assertEqual(files[name], oldfiles[name])
            self.assertEqual(manifest['steps'], old['steps'])
            self.assertEqual(manifest['probe'], old['probe'])
            self.assertEqual(manifest['build']['parameters'], old['build']['parameters'])
            self.assertEqual(manifest['context_timing']['production_generated_sha256'], source['generated_sha256'])
            for field in range(3):
                name = next(k for k in source['files'] if k.startswith('genefer_stream27_shared_warm_aw') and
                            f'_f{field}_' in k)
                text = source['files'][name]
                self.assertIn('.CONTEXTS(2),.BANKS(4)', text)
                self.assertIn('logic [3:0] tables_ready;', text)
                self.assertIn('payload_reserved[correction_context])admission_bad=1', text)
                self.assertIn('payload_owner[fwd_generation[24]]!={pointwise_bank,fwd_generation}', text)

    def test_reject_drift_and_composite(self):
        _, _, parent = n.capture('aw8')
        for key, value in (('warm_interval', 212), ('pointwise_accept', 78), ('next_correction_accept', 212)):
            mutant = copy.deepcopy(parent); mutant['geometry'][key] = value
            with self.assertRaises(ValueError):
                b.bind(mutant, enabled=1)
        for enabled in (True, 2):
            with self.assertRaises(ValueError):
                b.bind(parent, enabled=enabled)
        mutant = copy.deepcopy(parent); mutant['files'][parent['top'] + '.sv'] += '\n'
        with self.assertRaises(ValueError):
            b.bind(mutant, enabled=1)
        mutant = copy.deepcopy(parent); mutant['parameters']['COMM_TAG_COMPACT'] = 1
        with self.assertRaises(ValueError):
            b.bind(mutant, enabled=1)


if __name__ == '__main__':
    unittest.main()
