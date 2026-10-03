"""R11 captured source/header/calendar tests only; no HDL/full-N arithmetic."""
import json
from pathlib import Path
import unittest
from fpga.reference import stream27_context_storage_combo_transport11_long_native as own
from fpga.reference import stream27_context_storage_combo_transport11_continuous as full
from fpga.reference import stream27_context_transport11_model as model

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-transport11-ownlong-v1'


class Transport11LongTests(unittest.TestCase):
    def test_exact_own_header_only_compiled_delta(self):
        pilot=json.loads((BASE/'own100-serial-v1/manifest.json').read_bytes())
        longer=json.loads((BASE/'continuous1000-source-only-v1/manifest.json').read_bytes())
        self.assertEqual(longer['build'],pilot['build'])
        self.assertEqual(len(longer['build']['sv_sources']),59)
        for name in longer['build']['sv_sources']+[own.CPP,'rtl/tb/native_runtime_context_v1.h',
                  'rtl/tb/stream27_host_chain_full_reference_v1.h','rtl/tb/stream27_shared_reference_ntt_v1.h']:
            self.assertEqual(longer['sources'][name],pilot['sources'][name])
        ph=(BASE/'own100-serial-v1/source/fpga'/own.HEADER).read_bytes()
        fh=(BASE/'continuous1000-source-only-v1/source/fpga'/own.HEADER).read_bytes()
        self.assertEqual(fh,full.header(ph))
        self.assertIn(b'INTERVAL=8463,FIRST_DIGIT=8462,CARRY_DONE=12561',ph)
        self.assertEqual(full.config(),own.config(1000,1))
        self.assertEqual(own.bits(1000),full.bits(1000))
        for flag in ('CRT_TRANSPORT_REG','INVERSE_INGRESS_REG','TERM_JOIN_TRANSPORT_REG',
                     'LEAN_PROGRESS_WATCHDOG','LEAN_PRODUCTION'):
            self.assertEqual(longer['build']['parameters'][flag],1)

    def test_source_only_periodic_windows_and_publication(self):
        bundle=json.loads((ROOT/'results/throughput-20260929/trackS-c2-storage-combo-transport11-native-v1/full-normal-v2/production-bundle.json').read_bytes())
        for count in (100,1000):
            calendar=own.calendar(bundle['geometry'],count)
            self.assertEqual(calendar['frames'],2*count)
            self.assertEqual(calendar['launch_gaps'],[4231,4232])
            self.assertEqual(calendar['per_context_interval'],8463)
            events=model.event_calendar(bundle['geometry'],count)
            self.assertEqual(events['first_edges'],[204,4435])
            self.assertEqual(events['warm_edges'],[204+(count-1)*8463+12562,4435+(count-1)*8463+12562])
        events=model.event_calendar(bundle['geometry'],2)
        self.assertEqual(events['publication_edges'],[680694,1340158])
        self.assertEqual(events['full_read_completion_cycles'],1405694)

    def test_own_forecast_scope_and_no_inherited_measured_value(self):
        value=full.predict(250,440)
        self.assertTrue(value['fits_finite_shape'])
        self.assertIn('Own R11 LEAN',value['scope'])
        self.assertEqual(value['continuous_command_seconds_estimate'],4375)
        with self.assertRaises(ValueError):full.predict(250,249)
        self.assertFalse((BASE/'continuous1000-source-only-v1/forecast.json').exists())


if __name__=='__main__':unittest.main()
