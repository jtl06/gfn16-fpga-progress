"""Own FIELD100 source/header/validator tests; no native arithmetic locally."""
import copy,json
from pathlib import Path
import unittest
from fpga.reference import stream27_protected_field100_native_v2 as normal
from fpga.reference import stream27_protected_field100_long_native as own
from fpga.reference import stream27_protected_field100_continuous as longer

ROOT=normal.ROOT
BASE=ROOT/'results/throughput-20260929/trackS-c2-protected-field100-native-v1'


class Field100OwnSourceTests(unittest.TestCase):
    def test_exact_both_geometries_closed_flags_and_real_runtime(self):
        for directory,interval in ((BASE/'aw8-normal',215),(BASE/'full-normal-v2',8461)):
            m=json.loads((directory/'manifest.json').read_bytes())
            b=json.loads((directory/'production-bundle.json').read_bytes())
            self.assertEqual(len(b['files']),58)
            self.assertEqual(m['build']['parameters'],dict(b['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42))
            self.assertEqual(b['geometry']['warm_interval'],interval)
            self.assertTrue(b['context_protected_field100']['source_ready'])
            self.assertFalse(b['context_protected_field100']['R11_transports_composed'])
            for flag in ('LEAN_PRODUCTION','LEAN_PROGRESS_WATCHDOG','CRT_TRANSPORT_REG',
                    'INVERSE_INGRESS_REG','TERM_JOIN_TRANSPORT_REG'):
                self.assertNotIn(flag,m['build']['parameters'])
            for flag in b['context_protected_field100']['flags']:
                self.assertEqual(m['build']['parameters'][flag],1)
            for name,body in b['files'].items():
                self.assertEqual((directory/'source/fpga/rtl'/name).read_bytes(),body.encode())
            cpp=(directory/'source/fpga'/m['build']['cpp_source']).read_text()
            normal.runtime_before_model(cpp)

    def test_full_observer_every_parameter_and_fast_are_passive(self):
        d=BASE/'full-normal-v2';m=json.loads((d/'manifest.json').read_bytes())
        text=(d/'source/fpga/rtl'/(m['build']['top']+'.sv')).read_text()
        self.assertNotIn('\\n',text)
        self.assertNotIn('always_ff',text)
        self.assertIn('dbg_field_fast=candidate.engine.arithmetic.field_fast',text)
        self.assertTrue(all('.'+k+'('+k+')' in text for k in m['build']['parameters']))

    def test_own_source_calendar_long_header_and_unchanged_compiled_bytes(self):
        b=json.loads((BASE/'full-normal-v2/production-bundle.json').read_bytes())
        pilot=own.BASE/'own100-serial-v1';full=own.BASE/'continuous1000-source-v1'
        pm=json.loads((pilot/'manifest.json').read_bytes());fm=json.loads((full/'manifest.json').read_bytes())
        self.assertEqual(pm['build'],fm['build'])
        for name in pm['build']['sv_sources']+[own.CPP]:self.assertEqual(pm['sources'][name],fm['sources'][name])
        self.assertEqual((full/'source/fpga'/own.HEADER).read_bytes(),longer.header((pilot/'source/fpga'/own.HEADER).read_bytes()))
        self.assertEqual(longer.config(),own.config(1000))
        for count,joint in ((100,2234867),(1000,9849767)):
            scalar=own.calendar(b['geometry'],count)
            self.assertEqual(scalar['launch_gaps'],[4230,4231])
            self.assertEqual(b['context_protected_field100']['healthy_calendars'][str(count)]['full_read_completion_cycles'],joint)
        self.assertFalse((full/'forecast.json').exists())

    def test_full_typed_normal_rejects_ancestor_calendar(self):
        g=json.loads((ROOT/'queue/evidence/s4-p16-c2-protected-field100-full-normal-q1-v1/gate-receipt.json').read_bytes())
        v=g['steps'][0]['validation']['measurements']
        self.assertEqual(normal.validate('R84_C2_FULL_PASS '+json.dumps(v)+'\n','',0,normal.config(),{})['status'],'PASS_expected_contracts')
        for key,wrong in (('interval',8464),('joint_cycles',1405695),('done_edges',[680695,1340159])):
            mutated=copy.deepcopy(v);mutated[key]=wrong
            with self.assertRaises(ValueError):normal.validate('R84_C2_FULL_PASS '+json.dumps(mutated)+'\n','',0,normal.config(),{})


if __name__=='__main__':unittest.main()
