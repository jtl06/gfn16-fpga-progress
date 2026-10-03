"""Source and scalar calendar only; no HDL/full-N arithmetic execution."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'reference'/('stream27_context_storage_combo_timing10_'+name+'.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
own=module('long_native');full=module('continuous')


class Timing10LongTests(unittest.TestCase):
    def test_exact_header_only_compiled_delta(self):
        root=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-timing10-ownlong-v1'
        pilot=json.loads((root/'own100-serial-v1/manifest.json').read_bytes())
        long=json.loads((root/'continuous1000-source-only-v1/manifest.json').read_bytes())
        self.assertEqual(len(long['build']['sv_sources']),59)
        self.assertEqual(long['build'],pilot['build'])
        compiled=long['build']['sv_sources']+[own.CPP,'rtl/tb/native_runtime_context_v1.h',
                  'rtl/tb/stream27_host_chain_full_reference_v1.h','rtl/tb/stream27_shared_reference_ntt_v1.h']
        for name in compiled:self.assertEqual(long['sources'][name],pilot['sources'][name])
        ph=(root/'own100-serial-v1/source/fpga'/own.HEADER).read_bytes()
        fh=(root/'continuous1000-source-only-v1/source/fpga'/own.HEADER).read_bytes()
        self.assertEqual(fh,full.header(ph))
        self.assertIn(b'INTERVAL=8460,FIRST_DIGIT=8459,CARRY_DONE=12558',ph)
        self.assertTrue(long['build']['parameters']['LEAN_PRODUCTION'])

    def test_source_derived_periodic_windows_and_publication(self):
        directory=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-timing10-native-v1/full-normal'
        bundle=json.loads((directory/'production-bundle.json').read_bytes())
        from fpga.reference.stream27_context_timing10_model import event_calendar
        for count,joint in [(100,2234768),(1000,9848768)]:
            calendar=own.calendar(bundle['geometry'],count)
            self.assertEqual(calendar['frames'],2*count)
            self.assertEqual(calendar['launch_gaps'],[4230,4230])
            self.assertEqual(calendar['per_context_interval'],8460)
            self.assertEqual(event_calendar(bundle['geometry'],count)['pair_completion_cycles']+65536,joint)

    def test_forecast_and_lean_scope_are_not_old_source_credit(self):
        self.assertTrue(full.config()['lean_production'])
        self.assertEqual(full.config(),own.config(1000,1))
        value=full.predict(250,440)
        self.assertTrue(value['fits_finite_shape'])
        self.assertIn('GL assumed/unimplemented',value['scope'])
        self.assertEqual(value['continuous_command_seconds_estimate'],4375)
        with self.assertRaises(ValueError):full.predict(250,249)


if __name__=='__main__':unittest.main()
