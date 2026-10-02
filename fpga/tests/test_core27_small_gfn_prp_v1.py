"""Small AW5 bigint/config/validator checks only; no HDL or cloud execution."""
import json
from pathlib import Path
import tempfile
import unittest

from fpga.reference import core27_crtmont_prp_e2e_v1 as baseline
from fpga.reference import core27_small_gfn_prp_v1 as e


class SmallGFNTests(unittest.TestCase):
    def assets(self):
        text, oracle = e.corpus()
        return dict(corpus=text, oracle=json.dumps(oracle))

    def output(self, candidate='t5b', mode='normal'):
        _, oracle = e.corpus()
        lines, total = [], 0
        for case in oracle['cases'][:8 if mode == 'normal' else 1]:
            base = case['base']
            exponent = base**32 ^ (1 if mode == 'negative-schedule' else 0)
            residue = pow(2, exponent, base**32+1)
            steps = case['operations']
            doubles = case['doubles']-(1 if mode == 'negative-schedule' else 0)
            conversion = 11 if candidate == 't5b' else steps*8
            cycles = steps*5000
            total += cycles
            lines.append(f"E2E_RESULT case={case['index']} base={base} class={case['classification']} "
                         f"steps={steps} doubles={doubles} cycles={cycles} cold=1 warm={steps-1} "
                         f"conversion={conversion} roots=3089 prp={int(residue == 1)} digits="+
                         ','.join(map(str, e.encode(residue, base))))
        if mode == 'normal':
            conversions = 88 if candidate == 't5b' else 8*oracle['operations']
            lines.append(f"E2E_PASS aw=5 cases=8 operations={oracle['operations']} doubles={oracle['doubles']} "
                         f"readbacks=8 cycles={total} cold=8 warm={oracle['operations']-8} "
                         f"conversion={conversions} roots=24712")
        return '\n'.join(lines)+'\n'

    def validate(self, candidate='t5b', mode='normal', out=None, err=None, code=None, assets=None):
        return e.validate(self.output(candidate, mode) if out is None else out,
                          ('' if mode == 'normal' else e.MISMATCH) if err is None else err,
                          (0 if mode == 'normal' else 1) if code is None else code,
                          dict(candidate=candidate, mode=mode), self.assets() if assets is None else assets)

    def test_exact_established_corpus_and_proven_labels(self):
        text, oracle = e.corpus()
        old_text, old_oracle = baseline.corpus()
        self.assertEqual(text, old_text)
        self.assertEqual(oracle['corpus_sha256'], old_oracle['corpus_sha256'])
        self.assertEqual((oracle['operations'], oracle['doubles']), (4650, 1737))
        for case, old in zip(oracle['cases'], old_oracle['cases']):
            self.assertEqual(case['certificate'], old['certificate'])
            self.assertEqual(case['expected_digits'], old['expected_digits'])
            exponent = case['base']**32
            self.assertEqual(int(case['exponent_bits'], 2), exponent)
            self.assertEqual(int(case['expected_residue_hex'], 16), pow(2, exponent, exponent+1))
        for args in [(70, 'prime', 2), (96, 'prime', 4), (96, 'composite', 5), (68, 'composite', 2)]:
            with self.assertRaises(ValueError):
                e.prove_label(*args)

    def test_radix_range_and_exceptional_minus_one(self):
        for base in (69, 96, 1000000000):
            for value in (0, 1, base-1, base, base**32-1, base**32):
                self.assertEqual(e.decode(e.encode(value, base), base), value)
            self.assertEqual(e.encode(base**32, base), [-1]+[0]*31)
            for digits in ([-1, 1]+[0]*30, [base]+[0]*31, [0]*31):
                with self.assertRaises(ValueError):
                    e.decode(digits, base)

    def test_normal_and_typed_negatives_for_reusable_profiles(self):
        for candidate in ('t5b', 'crtmont'):
            for mode in ('normal', 'negative-comparator', 'negative-schedule'):
                result = self.validate(candidate, mode)
                self.assertFalse(result['promotion_allowed'])
                self.assertEqual(len(result['cases']), 8 if mode == 'normal' else 1)
        _, oracle = e.corpus()
        case = oracle['cases'][0]
        changed = pow(2, case['base']**32 ^ 1, case['base']**32+1)
        self.assertNotEqual(e.encode(changed, case['base'])[0], case['expected_digits'][0])

    def test_arithmetic_schedule_label_counters_and_footer_drift_rejected(self):
        normal = self.output()
        failures = [normal.replace('steps=196', 'steps=195', 1),
                    normal.replace('doubles=96', 'doubles=95', 1),
                    normal.replace('class=composite', 'class=prime', 1),
                    normal.replace('conversion=11', 'conversion=0', 1),
                    normal.replace('roots=3089', 'roots=3088', 1),
                    normal.replace('cold=1', 'cold=0', 1),
                    normal.replace('warm=195', 'warm=194', 1),
                    normal.replace('cases=8', 'cases=7'),
                    normal.replace('readbacks=8', 'readbacks=9'),
                    normal+'extra\n', normal.rsplit('\n', 2)[0]+'\n']
        head, raw = normal.splitlines()[0].split(' digits=')
        digits = list(map(int, raw.split(',')))
        digits[0] = (digits[0]+1)%69
        failures.append(normal.replace(head+' digits='+raw, head+' digits='+','.join(map(str, digits)), 1))
        for changed in failures:
            self.assertNotEqual(changed, normal)
            with self.assertRaises(ValueError):
                self.validate(out=changed)

    def test_negative_must_be_exact_typed_failure_with_expected_actual_residue(self):
        for mode in ('negative-comparator', 'negative-schedule'):
            for params in (dict(code=0), dict(code=-6), dict(err=''), dict(err=e.MISMATCH+'other\n'),
                           dict(out=self.output())):
                with self.assertRaises(ValueError):
                    self.validate(mode=mode, **params)
        with self.assertRaises(ValueError):
            self.validate(mode='negative-schedule', out=self.output(mode='negative-comparator'))
        with self.assertRaises(ValueError):
            self.validate(mode='negative-comparator', out=self.output(mode='negative-schedule'))

    def test_oracle_assets_and_config_drift_rejected(self):
        assets = self.assets()
        bad_oracle = json.loads(assets['oracle'])
        bad_oracle['cases'][0]['classification'] = 'prime'
        for changed in (dict(assets, corpus=assets['corpus']+'\n'),
                        dict(assets, oracle=json.dumps(bad_oracle)), dict(assets, extra='x')):
            with self.assertRaises(ValueError):
                self.validate(assets=changed)
        with self.assertRaises(ValueError):
            e.validate(self.output(), '', 0, dict(candidate='a4', mode='normal'), assets)

    def test_exact_frozen_actual_rtl_and_closed_preparation(self):
        order, pins = e.lineage()
        self.assertEqual(len(order), 16)
        self.assertEqual(pins['rtl/kernel/'+e.T5B_TOP+'.sv'], e.T5B_SHA)
        self.assertEqual(pins['rtl/kernel/genefer_carry_prefix_stream_precision_emit.sv'],
                         'ac01093c075b8bb0f7c5493b18623209164e42659a92a0310893aee086619c3a')
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary).resolve()/'prepared'
            result = e.prepare(out)
            self.assertEqual(result['unchanged_rtl_files'], 16)
            manifest = json.loads((out/'manifest.json').read_text())
            source = out/'source/fpga'
            self.assertEqual({str(x.relative_to(source)):e.sha(x) for x in source.rglob('*') if x.is_file()}, manifest['sources'])
            self.assertEqual(manifest['build']['sv_sources'], order)
            self.assertEqual(manifest['build']['parameters'], dict(AW=5, NTT_LANES=64))
            self.assertEqual([s['expected_returncode'] for s in manifest['steps']], [0, 1, 1])
            with self.assertRaises(ValueError):
                e.prepare(out)


if __name__ == '__main__':
    unittest.main()
