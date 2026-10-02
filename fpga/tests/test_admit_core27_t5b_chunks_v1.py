"""Time/cycle metadata tests only; no reference arithmetic/HDL execution."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('_chunk_admission',ROOT/'tools/admit_core27_t5b_chunks_v1.py')
ADMIT=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(ADMIT)


class DurationAdmission(unittest.TestCase):
    def test_actual_short_source_bound_forecast(self):
        value=ADMIT.admission(ROOT/'queue/done/soak-t5b-aw16-short-native-q3-v1.json',
                              ROOT/'queue/done/soak-t5b-aw16-full-reference-q3-v1.json')
        self.assertEqual(value['status'],'PASS_bounded_chunk_duration_estimate')
        self.assertEqual(value['compatible_hosts'],['gfn16-pilot-c4d'])
        self.assertFalse(value['continuous_admitted'])
        self.assertLess(value['forecast']['chunk_command_seconds_estimate'],1800)
        self.assertGreater(value['forecast']['continuous_command_seconds_estimate'],1800)

    def test_tick_formula_and_margin(self):
        steps={name:{'seconds':seconds} for name,seconds in
               (('soak-normal',65.633542),('soak-negative-boundary',46.695348),
                ('soak-negative-loaded-state',25.468034))}
        result=ADMIT.predict(steps,41674,28826,16.721184)
        self.assertEqual(result['margin'],1.75)
        self.assertEqual(result['measured_ticks']['soak-normal'],332652)
        self.assertEqual(result['chunk_model_ticks'],3092161)
        self.assertAlmostEqual(result['chunk_command_seconds_estimate'],1067.661,delta=1)

    def test_missing_nonfinite_or_zero_timing_fails(self):
        base={name:{'seconds':1} for name in
              ('soak-normal','soak-negative-boundary','soak-negative-loaded-state')}
        for bad in (0,float('nan'),float('inf')):
            value={k:dict(v) for k,v in base.items()};value['soak-normal']['seconds']=bad
            with self.assertRaisesRegex(ValueError,'finite measured'):
                ADMIT.predict(value,1,1,1)
        base.pop('soak-negative-boundary')
        with self.assertRaisesRegex(ValueError,'complete finite'):
            ADMIT.predict(base,1,1,1)

    def test_frozen_crtmont_gate_is_not_T5b(self):
        with self.assertRaisesRegex(ValueError,'actual T5b short result'):
            ADMIT.admission(ROOT/'queue/done/soak-aw16-short-f16-q2-v4.json',
                            ROOT/'queue/done/soak-t5b-aw16-full-reference-q3-v1.json')


if __name__=='__main__':
    unittest.main()
