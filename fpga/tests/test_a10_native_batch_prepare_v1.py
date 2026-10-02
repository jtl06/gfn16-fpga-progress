from pathlib import Path
import tempfile
import unittest

from fpga.reference import a10_native_batch_prepare_v1 as batch


class A10FiniteBatchTests(unittest.TestCase):
    def test_three_exact_fault_successors(self):
        original, files = batch.donor()
        for kind, phase, index in [('root', 'forward', 0), ('normalization', 'inverse', 0),
                                    ('form', 'forward', 1)]:
            altered, delta = batch.mutation(files, kind)
            self.assertEqual({k: v for k, v in altered.items() if k in files}, files)
            self.assertEqual(altered[delta['successor']].decode().replace(delta['after'], delta['before'], 1),
                             files[delta['parent']].decode())
            self.assertEqual(delta['expected_stderr'],
                f'A10_NUMERIC_{kind.upper()}_MISMATCH phase={phase} index={index}\n')
            m, source = batch.role('aw5-' + kind)
            self.assertEqual(m['steps'][0]['expected_returncode'], 1)
            self.assertIn(delta['successor'], m['build']['sv_sources'])
            self.assertNotIn(delta['parent'], m['build']['sv_sources'])

    def test_fields_whole_and_geometry_contracts(self):
        m, _ = batch.role('aw5-f2')
        self.assertEqual((m['build']['parameters']['P'], m['build']['parameters']['Q']), (67239937, 4227727361))
        self.assertIn('residues=480 cycles=540', m['steps'][0]['expected_stdout'])
        m, _ = batch.role('aw5-e2e1')
        self.assertEqual([s['expected_returncode'] for s in m['steps']], [0, 1])
        self.assertEqual(m['steps'][1]['validator']['config']['negative'], 'comparator')
        self.assertEqual(len(m['batch_role']['dependencies']), 5)
        for number in range(3):
            m, _ = batch.role('aw8-f' + str(number))
            self.assertEqual(m['build']['parameters']['AW'], 8)
            self.assertEqual(m['source_only_ledger']['residues'], 3840)
            self.assertEqual(m['source_only_ledger']['engine_work_cycles'], 935)
            self.assertIn('aw5-e2e1', m['batch_role']['dependencies'])
        with self.assertRaisesRegex(ValueError, 'FULL_CONSTANTS_EXPLICIT'):
            batch.role('aw16-f0')

    def test_dual_profile_package_once_and_frozen_design_preserved(self):
        budget = batch.ROOT / 'artifacts/native-shared-smoke-v1/budget.json'
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'f2'
            r = batch.prepare_role(output, 'aw5-f2', budget)
            self.assertEqual(len(r['variants']), 2)
            self.assertNotEqual(r['variants'][0]['resource_profile_sha256'], r['variants'][1]['resource_profile_sha256'])
            self.assertTrue(r['select_exactly_one'])
            self.assertFalse(r['promotion_allowed'])
            with self.assertRaisesRegex(ValueError, 'FRESH_ROLE'):
                batch.prepare_role(output, 'aw5-f2', budget)
