"""Metadata and mocked admission ordering only; no GMP/model/full-N math."""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from fpga.reference import anext_writeback_soak_portable_v1 as p


class PortableF3(unittest.TestCase):
    def assets(self):
        paths = {
            'runtime': p.ROOT/'artifacts/anext-writeback-qualification-pilot-role-v1/source/fpga/donor/fpga/soak/runtime.json',
            'generation-runtime': p.ROOT/'artifacts/anext-writeback-qualification-pilot-role-v1/source/fpga/donor/fpga/soak/runtime.json',
            'target-f16': p.ROOT/'results/throughput-20260929/soak-azure-f16-runtime-v1/runtime.json',
            'target-burst': p.ROOT/'results/throughput-20260929/soak-azure-f32-runtime-v1/runtime.json',
        }
        return {key: paths[key].read_text() if key in paths else '{}' for key in p.ASSETS}

    def test_actual_host_selection_and_original_bytes(self):
        assets = self.assets()
        for host, label in (('gfn16-pilot-c4d', 'runtime'),
            ('gfn16-azure-f16', 'target-f16'), ('gfn16-azure-sim-f32', 'target-burst')):
            chosen = p.selected_assets(assets, host)
            self.assertEqual(chosen['runtime'], assets[label])
            self.assertEqual(chosen['oracle'], assets['oracle'])
            self.assertEqual(set(chosen), {'oracle', 'runtime'} if host == 'gfn16-pilot-c4d' else p.COMMON)
        self.assertEqual(p.text_sha(assets['generation-runtime']), p.GENERATION_SHA)

    def test_missing_extra_unknown_host_and_drift_reject(self):
        assets = self.assets()
        for host in ('macOS', 'gfn16-unknown', ''):
            with self.assertRaises(ValueError): p.selected_assets(assets, host)
        for key in p.ASSETS:
            altered = dict(assets); altered.pop(key)
            with self.subTest(key=key), self.assertRaises(ValueError):
                p.selected_assets(altered, 'gfn16-pilot-c4d')
        for key in ('runtime', 'generation-runtime', 'target-f16', 'target-burst'):
            altered = dict(assets); altered[key] += ' '
            with self.subTest(key=key), self.assertRaises(ValueError):
                p.selected_assets(altered, 'gfn16-azure-f16')
        with self.assertRaises(ValueError):
            p.selected_assets(dict(assets, unbound='{}'), 'gfn16-pilot-c4d')

    def test_target_rejection_precedes_reference_work(self):
        trace = []
        def reject(_):
            trace.append('admit'); raise ValueError('target drift')
        b = SimpleNamespace(binding=lambda _: trace.append('binding'), validate=lambda *a: trace.append('BAD-validate'))
        d = SimpleNamespace(admit_runtime=reject, reference=lambda: trace.append('BAD-reference'))
        with patch.object(p.socket, 'gethostname', return_value='gfn16-azure-f16'), \
            patch.object(p, 'bridge', return_value=b), patch.object(p.prior, 'donor', return_value=d), \
            patch.object(p.prior, 'normalise', side_effect=AssertionError('numeric work')):
            with self.assertRaisesRegex(ValueError, 'target drift'):
                p.validate('', '', 0, {'negative': 'none'}, self.assets())
        self.assertEqual(trace, ['binding', 'admit'])

    def test_azure_preserves_both_identities_after_admission(self):
        trace = []
        def admit(value): trace.append('admit'); return {'runtime': p.text_sha(value)}
        def reference(): trace.append('metadata'); return object()
        def normalise(*args): trace.append('normalise'); return 'converted', {'operations': 100}
        def compare(*args):
            trace.append('cross-compare')
            self.assertEqual(args[0], 'converted')
            return {'generation_reference': 'original', 'target_reference': 'actual'}
        with patch.object(p.socket, 'gethostname', return_value='gfn16-azure-sim-f32'), \
            patch.object(p, 'bridge', return_value=SimpleNamespace(binding=lambda _: trace.append('binding'), validate=compare)), \
            patch.object(p.prior, 'donor', return_value=SimpleNamespace(admit_runtime=admit, reference=reference)), \
            patch.object(p.prior, 'normalise', side_effect=normalise):
            result = p.validate('', '', 0, {'negative': 'none'}, self.assets())
        self.assertEqual(trace, ['binding', 'admit', 'metadata', 'normalise', 'cross-compare'])
        self.assertEqual(result['candidate_core_sha256'], p.prior.CORE_SHA)
        self.assertEqual(result['actual_reference_host'], 'gfn16-azure-sim-f32')
        self.assertEqual(result['generation_reference_host'], 'gfn16-pilot-c4d')
        self.assertEqual(result['actual_runtime_manifest_sha256'], p.TARGETS['gfn16-azure-sim-f32'][1])
        self.assertFalse(result['promotion_allowed'])

    def test_gcp_uses_unchanged_original_validator_only(self):
        with patch.object(p.socket, 'gethostname', return_value='gfn16-pilot-c4d'), \
            patch.object(p.prior, 'validate', return_value={'status': 'PASS_expected_contracts'}) as validate, \
            patch.object(p, 'bridge', side_effect=AssertionError('wrong host bridge')):
            result = p.validate('', '', 0, {'negative': 'none'}, self.assets())
        self.assertEqual(set(validate.call_args.args[-1]), {'oracle', 'runtime'})
        self.assertEqual(result['actual_runtime_manifest_sha256'], p.GENERATION_SHA)

if __name__ == '__main__':
    unittest.main()
