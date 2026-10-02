"""Matched registered F2 source/config tests; no native/vendor work."""
import json
from pathlib import Path
import tempfile
import unittest

from fpga.reference import f2_registered_probe_v1 as probe


class RegisteredProbe(unittest.TestCase):
    def test_matched_shells_same_bytes_except_wrapper_and_child_names(self):
        sources, receipts = probe.generated_sources()
        parent = sources['rtl/kernel/'+probe.MODULES['parent']+'.sv']
        candidate = sources['rtl/kernel/'+probe.MODULES['candidate']+'.sv']
        candidate = candidate.replace(probe.MODULES['candidate'], probe.MODULES['parent'])
        candidate = candidate.replace(probe.rec.NAMES[probe.rec.HOST], probe.rec.HOST)
        self.assertEqual(parent, candidate)
        for receipt in receipts.values():
            self.assertEqual(len(receipt['source_register_anchors']), 24)
            self.assertEqual(len(receipt['destination_register_anchors']), 21)
            self.assertEqual(receipt['request_added_edges'], 1)
            self.assertEqual(receipt['response_added_edges'], 1)

    def test_generated_host_oracle_pulses_each_delayed_transaction(self):
        sources, _ = probe.generated_sources()
        text = sources[probe.BENCH]
        self.assertIn('auto pulse = [&]() { tick(); idle(); tick(); tick(); };', text)
        self.assertEqual(text.count('pulse();'), 10)
        self.assertNotIn('Vroot_lookahead_engine_pair_v1', text)
        self.assertIn('F2_REGISTERED_FIELD_INTEGER_ORACLE', text)
        self.assertIn('F2_REGISTERED_FIELD_RESET_QUARANTINE', text)
        self.assertIn('context.threads()', text)

    def test_exact_registered_footer_and_cycle_mutants(self):
        vectors, _ = probe.field.corpus(5, 0)
        footer = ('F2_REGISTERED_FIELD_PASS aw=5 p=104857601 cases=4 operations=20 readbacks=640 '
                  'aborts=10 faults=11 phase_cycles=44,72,8,68,44 threads=1\n')
        config = dict(aw=5,p=104857601,runtime_threads=1)
        result = probe.validate(footer, '', 0, config, {'vectors': vectors})
        self.assertFalse(result['public_drop_in_interface'])
        self.assertEqual(result['child_cycle_counter_delta'], 0)
        for value in [footer.replace('REGISTERED_', ''), footer.replace('44,72,8,68,44', '45,72,8,68,44'),
                      footer.replace('threads=1', 'threads=2'), footer+'extra\n']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                probe.validate(value, '', 0, config, {'vectors': vectors})

    def test_native_manifest_complete_frozen_ancestry_and_typed_negative(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory).resolve()/'native'
            receipt = probe.prepare_native(output)
            manifest = json.loads((output/'role-manifest.json').read_text())
            root = output/'source/fpga'
            self.assertEqual(manifest['build']['top'], probe.PAIR)
            self.assertEqual(manifest['build']['runtime_threads'], 1)
            self.assertEqual(manifest['build']['parameters']['AW'], 5)
            self.assertEqual(len(manifest['build']['sv_sources']), 13)
            self.assertTrue(all(name in manifest['sources'] for name in manifest['build']['sv_sources']))
            self.assertEqual(manifest['steps'][1]['expected_stderr'], 'F2_REGISTERED_FIELD_INTEGER_ORACLE\n')
            self.assertEqual(manifest['sources'], {p.relative_to(root).as_posix(): probe.sha(p)
                                                  for p in root.rglob('*') if p.is_file()})
            old = json.loads((probe.PARENT_PACKET/probe.PARENT_MANIFEST).read_text())
            self.assertTrue(all(manifest['sources'].get(name) == pin for name,pin in old['sources'].items()))
            self.assertFalse(receipt['native_RTL_executed'])
            with self.assertRaisesRegex(ValueError, 'fresh canonical'):
                probe.prepare_native(output)

    def test_physical_settings_match_and_declared_scope_is_not_fit_permission(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory).resolve()/'physical'
            receipt = probe.prepare_physical(output)
            parent, candidate = output/'parent', output/'candidate'
            a, b = (parent/'probe.qsf').read_text(), (candidate/'probe.qsf').read_text()
            for old, new in probe.rec.NAMES.items():
                b = b.replace(new, old)
            b = b.replace(probe.MODULES['candidate'], probe.MODULES['parent'])
            self.assertEqual(a, b)
            self.assertEqual((parent/'probe.sdc').read_bytes(), (candidate/'probe.sdc').read_bytes())
            for project in (parent, candidate):
                manifest = json.loads((project/'manifest.json').read_text())
                self.assertEqual(manifest['core_parameters'], dict(AW=16,LANES=64,HOST_LANES=16,P=104857601,Q=4190109697))
                self.assertEqual(len(manifest['source_sha256']), 8)
                spec = json.loads((project/'structural-spec.json').read_text())
                result = probe.structural.source_inventory(project, spec)
                self.assertEqual(result['findings'], [])
                self.assertEqual(len(spec['blocks']), 1)
                self.assertEqual(spec['scope'], 'component_probe')
                saved = json.loads((project/'structural-source-result.json').read_text())
                self.assertFalse(saved['fit_allowed'])
                self.assertTrue(saved['scope_awaits_fit_owner_confirmation'])
                self.assertTrue(saved['native_design_assistant_pending'])
            self.assertFalse(receipt['fit_allowed'])


if __name__ == '__main__':
    unittest.main()
