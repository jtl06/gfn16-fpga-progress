import copy
import hashlib
import unittest

from fpga.reference import stream27_context_storage_banks_native as native
from fpga.reference import stream27_context_storage_banks_bind_v2 as binder
from fpga.reference import stream27_c2_state_analysis as model


class StorageNativeTests(unittest.TestCase):
    def test_both_captured_default_off_maps_exact(self):
        for stage in ('aw8', 'full'):
            manifest, files, bundle = native.capture(stage)
            self.assertEqual(len(bundle['files']), 53)
            self.assertEqual(binder.bind(bundle), bundle)
            self.assertEqual(len(manifest['build']['sv_sources']), 53 if stage == 'aw8' else 54)

    def test_native_contracts_not_weakened_or_recomputed(self):
        for stage in ('aw8', 'full'):
            parent, oldfiles, bundle = native.capture(stage)
            manifest, files, source = native.role(stage)
            self.assertEqual(manifest['steps'], parent['steps'])
            self.assertEqual(manifest['probe'], parent['probe'])
            self.assertEqual(files[parent['build']['cpp_source']], oldfiles[parent['build']['cpp_source']])
            self.assertEqual(manifest['build']['parameters'], parent['build']['parameters'])
            self.assertEqual(source['storage_contract']['unchanged'], 47)
            self.assertEqual(len(source['storage_contract']['changed']), 6)
            self.assertTrue(all(hashlib.sha256(files[n]).hexdigest() == pin for n, pin in manifest['sources'].items()))
            self.assertTrue(all('tagcompact' not in n for n in source['files']))

    def test_aw8_own_read_write_lifetime_not_full_constant_truncation(self):
        items = model.windows((3, 14), interval=212, pointwise=78, rows=16,
                             next_correction=212, second_correction=106)
        self.assertEqual(model.check_windows(items), 118)
        self.assertEqual(model.logical_peak(items, release_offset=166)['peak'], 2)
        first = next(v for v in items if v['context'] == 0 and v['ordinal'] == 0)
        self.assertEqual(first['last_coefficient_read'], 93)
        self.assertEqual(first['last_E4_product_write'], 93)
        manifest, files, source = native.role('aw8')
        self.assertEqual(source['geometry']['feedback_delay'], 18)
        self.assertEqual(source['geometry']['warm_interval'], 212)

    def test_full_observer_identifier_only_no_new_state(self):
        parent, oldfiles, bundle = native.capture('full')
        manifest, files, source = native.role('full')
        observer = 'rtl/' + parent['build']['top'] + '.sv'
        expected = binder.parent.re_identifier(oldfiles[observer].decode(), bundle['top'], source['top']).encode()
        self.assertEqual(files[observer], expected)
        self.assertEqual(manifest['build']['top'], parent['build']['top'])
        self.assertEqual(files['rtl/tb/s4_p16_two_context_full_config.h'], oldfiles['rtl/tb/s4_p16_two_context_full_config.h'])

    def test_reject_mutable_host_source_or_wrong_calendar(self):
        _, _, bundle = native.capture('aw8')
        for key, value in (('warm_interval', 8459), ('pointwise_accept', 79), ('last_sink', 167)):
            mutant = copy.deepcopy(bundle)
            mutant['geometry'][key] = value
            with self.assertRaises(ValueError):
                binder.bind(mutant, enabled=1)
        mutant = copy.deepcopy(bundle)
        mutant['files'][mutant['top'] + '.sv'] += '\n'
        with self.assertRaises(ValueError):
            binder.bind(mutant, enabled=1)


if __name__ == '__main__':
    unittest.main()
