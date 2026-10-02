"""Replay actual prepared source-only packet identities; no native/math."""
import copy
import json
from pathlib import Path
import unittest

from fpga.tools import native_thread_wide_compare_v4 as compare


class PreparedWideProviderComparisonTests(unittest.TestCase):
    def test_actual_three_prepared_packets_share_all_source_and_allocation(self):
        root = Path(__file__).resolve().parents[1] / 'results/throughput-20260929/threaded-wide-package-v3'
        manifests = [json.loads((root / f'packet{n}/manifest.json').read_text()) for n in (2, 4, 8)]
        self.assertEqual(manifests[0]['sources'], manifests[1]['sources'])
        self.assertEqual(manifests[1]['sources'], manifests[2]['sources'])
        self.assertTrue(compare.role_equal(manifests[0], manifests[1]))
        self.assertTrue(compare.role_equal(manifests[0], manifests[2]))
        current = 'results/throughput-20260929/threaded-wide-package-v3/provider.json'
        self.assertIn(current, manifests[0]['sources'])
        allowed = copy.deepcopy(manifests[1])
        allowed['sources'].pop(current)
        fresh = 'results/throughput-20260929/core27-t5b-thread-wide-source-v1/execution-inputs-v1/provider.json'
        allowed['sources'][fresh] = '1' * 64
        self.assertTrue(compare.role_equal(manifests[0], allowed))
        for changed in (fresh.replace('execution-inputs-v1', 'unrecognized'), 'arbitrary/provider.json'):
            bad = copy.deepcopy(allowed); bad['sources'].pop(fresh); bad['sources'][changed] = '2' * 64
            with self.subTest(changed=changed), self.assertRaises(ValueError): compare.role_equal(manifests[0], bad)
        bad = copy.deepcopy(allowed); bad['sources'][current] = '3' * 64
        with self.assertRaisesRegex(ValueError, 'one closed'): compare.role_equal(manifests[0], bad)


if __name__ == '__main__':
    unittest.main()
