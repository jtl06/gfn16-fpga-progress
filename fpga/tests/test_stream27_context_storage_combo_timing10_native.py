"""Metadata-only R10 tests; never run HDL/full-size arithmetic on this host."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('timing10_native',ROOT/'reference/stream27_context_storage_combo_timing10_native.py')
native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)


class Timing10NativeTests(unittest.TestCase):
    def test_captured_own_sources_and_runtime(self):
        base=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-timing10-native-v1'
        for stage,count in [('aw8',58),('full',59)]:
            directory=base/(stage+'-normal');manifest=json.loads((directory/'manifest.json').read_bytes())
            bundle=json.loads((directory/'production-bundle.json').read_bytes())
            self.assertEqual(len(bundle['files']),58)
            self.assertEqual(len(manifest['build']['sv_sources']),count)
            self.assertEqual(manifest['build']['parameters']['LEAN_PRODUCTION'],1)
            self.assertTrue(manifest['context_timing10']['host_GL_assumed_unimplemented'])
            self.assertFalse(manifest['context_timing10']['protected_fault_rollback_claim'])
            for name,pin in manifest['sources'].items():
                self.assertEqual(native.sha((directory/'source/fpga'/name).read_bytes()),pin)
            native.runtime_before_model((directory/'source/fpga'/manifest['build']['cpp_source']).read_text())

    def test_exact_new_calendar_accepts_and_old_rejected(self):
        directory=ROOT/'queue/evidence/s4-p16-c2-combo-r9-full-normal-q1-v1/attempt-0/collected/output/native'
        report=json.loads((directory/'report.json').read_bytes())
        actual=report['validations']['normal-full-c2-r9-alone-and-joint']['measurements']
        value=dict(actual,interval=8460,pair_launch_cycles=8460,launches=[[204,8664],[4434,12894]],
                   warm_edges=[21223,25453],done_edges=[680688,1340152],joint_cycles=1405688,
                   single_cycles=[746124,746124],overlap_edges=680687)
        stdout='R84_C2_FULL_PASS '+json.dumps(value)+'\n'
        self.assertEqual(native.validate(stdout,'',0,native.config(),{})['status'],'PASS_expected_contracts')
        with self.assertRaises(ValueError):
            native.validate('R84_C2_FULL_PASS '+json.dumps(actual)+'\n','',0,native.config(),{})

    def test_full_observer_forwards_every_new_parameter(self):
        directory=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-timing10-native-v1/full-normal'
        manifest=json.loads((directory/'manifest.json').read_bytes())
        text=(directory/'source/fpga/rtl'/ (manifest['build']['top']+'.sv')).read_text()
        for key in ['LEAN_PRODUCTION','FINAL_GS_INPUTREG','CANONICAL_LOCALBASE','CARRY_LOCALBASE',
                    'TERM_SELECT_TOKEN','CANONICAL_PROFILE_SNAPSHOT','CANONICAL_BEGIN_PAYLOAD_SPLIT']:
            self.assertIn(key+'=1,',text)
            self.assertIn('.'+key+'('+key+')',text)
        self.assertNotRegex(text,r'\b(always|always_ff|always_comb|initial)\b')


if __name__=='__main__':unittest.main()
