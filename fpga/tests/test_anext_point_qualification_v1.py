"""Small-N numerical and source-only point qualification adaptation tests."""
import json
import unittest
from fpga.reference import anext_point_qualification_v1 as q
from fpga.reference import anext_point_small_prp_v1 as prp
from fpga.reference.anext_point_soak_output_v1 import normalise
from fpga.tests.test_anext_soak_v1 import fixture


class PointQualification(unittest.TestCase):
    def test_exact_identity_only_delta(self):
        self.assertTrue(q.verify()['reset_reload_loop_unchanged'])
        self.assertFalse(q.verify()['RTL_changed'])
        text = q.expected()['rtl/tb/anext_point_soak_v1.cpp']
        self.assertEqual(text.count('d.rst_n=0;'), 1)
        self.assertEqual(text.count('command(0,0,0,false);'), 1)
        self.assertIn('No reset/reload between operations', text)
        begin = text.index('for (unsigned k = 0; k < bits.size(); ++k)')
        loop = text[begin:text.index('require(next_check == count', begin)]
        self.assertNotIn('d.rst_n', loop)
        self.assertNotIn('command(0', loop)
        self.assertNotIn('command(1', loop)
        self.assertIn('uint64_t(n)/64)+14;', text)

    def test_small_arrays_and_both_controls_unchanged(self):
        for negative in ('none', 'boundary', 'loaded-state'):
            text, oracle, ref, error, returncode = fixture(negative)
            rows = []
            for line in text.splitlines():
                prefix, raw = line.split(' ', 1)
                row = json.loads(raw)
                if prefix == 'ANEXT_SOAK_STEP':
                    row['cycles'] += 1
                    row['ntt'] += 1
                if prefix == 'ANEXT_SOAK_PASS':
                    row['cycles'] += row['operations']
                rows.append(prefix+' '+json.dumps(row))
            good = '\n'.join(rows)+'\n'
            converted, metrics = normalise(good, oracle, ref)
            result = ref.validate_rows(converted, error, returncode, {'negative': negative}, oracle)
            if negative == 'none':
                self.assertEqual(result['operations'], 4)
                self.assertEqual(metrics['cold_prefill'], 2)
                for before, after in [('"prefill": 12', '"prefill": 0'),
                                      ('"cache_cold": 1', '"cache_cold": 2')]:
                    self.assertNotEqual(good.replace(before, after, 1), good)
                    with self.assertRaises(ValueError):
                        normalise(good.replace(before, after, 1), oracle, ref)
            if negative != 'loaded-state':
                with self.assertRaises(ValueError):
                    normalise(text, oracle, ref)  # missing point's +1-cycle accounting

    def test_prp_valid_base_numeric_assets_unchanged(self):
        from fpga.reference.anext_small_prp_v1 import corpus
        self.assertEqual(prp.corpus(), corpus())
        _, oracle = prp.corpus()
        self.assertEqual(oracle['base_floor'], 300)
        self.assertEqual(len(oracle['cases']), 8)
        self.assertEqual(oracle['operations'], 5051)
        self.assertIn("candidate='A-next-point-v1'", q.expected()['reference/anext_point_small_prp_v1.py'])
        self.assertIn('k==0?207u:184u', q.expected()['rtl/tb/anext_point_small_prp_v1.cpp'])
        with self.assertRaises(ValueError):
            prp.validate('', '', True, {'mode': 'normal'}, dict(corpus=prp.corpus()[0], oracle=json.dumps(oracle)))

    def test_closed_identity_anchor_is_not_permissive(self):
        for text in ('missing', 'same same'):
            with self.assertRaises(ValueError):
                q.once(text, 'same', 'different')


if __name__ == '__main__':
    unittest.main()
