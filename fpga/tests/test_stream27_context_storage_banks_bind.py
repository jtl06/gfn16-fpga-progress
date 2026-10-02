import copy
import hashlib
import json
import re
import unittest

from fpga.reference import stream27_context_storage_banks_bind as b
from fpga.reference import stream27_c2_state_analysis as m


def captured_bundle():
    project = m.BASE / 'source-explicit-v2/project'
    manifest = json.loads((project / 'manifest.json').read_text())
    files = {name: (project / 'rtl' / name).read_text() for name in manifest['source_sha256']}
    return dict(top=manifest['top'], files=files, geometry=manifest['geometry'],
                generated_sha256=manifest['source_sha256'], rtl_sources=list(files),
                parameters=manifest['core_parameters'])


class BindTests(unittest.TestCase):
    def test_disabled_full_default_is_exact(self):
        parent = captured_bundle()
        self.assertEqual(b.bind(parent), parent)
        self.assertEqual(len(parent['files']), 53)

    def test_private_two_bank_leaf_keeps_full_owner_and_E4(self):
        parent = captured_bundle()
        original = copy.deepcopy(parent)
        result = b.bind(parent, enabled=1)
        self.assertEqual(parent, original)
        self.assertEqual(len(result['files']), 53)
        text = result['files'][b.TERM + '_storage2_v1.sv']
        self.assertIn('context_data[0:1][0:3]', text)
        self.assertIn('prod_bank=product_owner[24]', text)
        for anchor in ('bank_owner[prod_bank]!=product_owner',
                       'bank_owner[pw_bank]!=pointwise_owner',
                       'if(bypass)begin current_term=product_data;consumer_missing=1\'b0;end',
                       'if(product_slot && bank_owner[prod_bank]==product_owner)begin'):
            self.assertIn(anchor, text)

    def test_only_three_fields_term_leaf_caller_and_top_change(self):
        parent = captured_bundle()
        result = b.bind(parent, enabled=1)
        unchanged = []
        changed = []
        for name, text in parent['files'].items():
            new_name = name[:-3] + '_storage2_v1.sv' if name not in result['files'] else name
            (unchanged if result['files'][new_name] == text else changed).append(name)
        self.assertEqual(len(changed), 6)  # term, three fields, one caller, host name
        self.assertEqual(len(unchanged), 47)
        protocol = parent['files']['genefer_stream27_epoch_protocol_contexts_v1.sv']
        self.assertEqual(protocol, result['files']['genefer_stream27_epoch_protocol_contexts_v1.sv'])
        for field in range(3):
            name = next(k for k in result['files'] if k.startswith('genefer_stream27_shared_warm_aw16_p16_f' + str(field)))
            text = result['files'][name]
            self.assertIn('.CONTEXTS(2),.BANKS(4)', text)
            self.assertIn('logic [3:0] tables_ready;', text)
            self.assertIn('payload_owner[fwd_generation[24]]!={pointwise_bank,fwd_generation}', text)
            self.assertIn('payload_reserved[correction_context])admission_bad=1', text)
            self.assertIn("pw_row==ROW_W'(ROWS-1)", text)

    def test_reject_bool_generic_geometry_and_drift(self):
        parent = captured_bundle()
        with self.assertRaises(ValueError):
            b.bind(parent, enabled=True)
        for key, value in (('n', 256), ('warm_interval', 8460), ('contexts', 1)):
            mutant = copy.deepcopy(parent)
            mutant['geometry'][key] = value
            with self.assertRaises(ValueError):
                b.bind(mutant, enabled=1)
        mutant = copy.deepcopy(parent)
        mutant['files'][mutant['top'] + '.sv'] += '\n'
        with self.assertRaises(ValueError):
            b.bind(mutant, enabled=1)

    def test_full_owner_early_cache_raw_cancel_and_wrap(self):
        owners = m.PhysicalOwners()
        first = (0, 0, 65535, 7)
        peer = (1, 1, 42, 9)
        nxt = (2, 0, 0, 7)
        owners.reserve(first)
        self.assertFalse(owners.cache(peer))
        self.assertTrue(owners.cache(first))
        owners.reserve(peer)
        self.assertTrue(owners.cache(peer))
        # Cancelled context must raw-drain; peer remains publishable.
        self.assertFalse(owners.consume(first, enabled=False))
        self.assertTrue(owners.consume(peer, live_generation=9))
        with self.assertRaises(ValueError):
            owners.reserve(nxt)
        owners.retire_raw(first)
        owners.reserve(nxt)
        self.assertFalse(owners.cache(first))
        self.assertFalse(owners.cache((0, 0, 0, 7)))  # wrong logical bank, same lower tuple
        self.assertTrue(owners.cache(nxt))
        self.assertTrue(owners.consume(nxt))
        with self.assertRaises(ValueError):
            owners.retire_raw(first)

    def test_reset_revokes_cached_eligibility(self):
        owners = m.PhysicalOwners()
        key = (2, 0, 0, 3)
        owners.reserve(key)
        owners.cache(key)
        owners.reset()
        with self.assertRaises(ValueError):
            owners.consume(key)
        self.assertFalse(owners.cache(key))
        owners.reserve(key)
        self.assertFalse(owners.cache(key, physical_valid=False))
        with self.assertRaises(ValueError):
            owners.consume(key)
        self.assertTrue(owners.cache(key))


if __name__ == '__main__':
    unittest.main()
