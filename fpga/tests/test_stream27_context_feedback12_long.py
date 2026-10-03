"""Source-only R12 exact own calendar/compiled-header tests, not native PASS."""
import json
from pathlib import Path
import unittest
from fpga.reference import stream27_context_feedback12_long_native as own
from fpga.reference import stream27_context_feedback12_continuous as full
from fpga.reference import stream27_context_feedback12_model as model

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/throughput-20260929/trackS-c2-feedback12-ownlong-v1'


class Feedback12LongTests(unittest.TestCase):
    def test_exact_own_compiled_delta_and_runtime(self):
        pilot=json.loads((BASE/'own100-serial-v1/manifest.json').read_bytes())
        longer=json.loads((BASE/'continuous1000-source-v1/manifest.json').read_bytes())
        self.assertEqual(longer['build'],pilot['build'])
        self.assertEqual(len(longer['build']['sv_sources']),59)
        for name in longer['build']['sv_sources']+[own.CPP,'rtl/tb/native_runtime_context_v1.h',
                  'rtl/tb/stream27_host_chain_full_reference_v1.h','rtl/tb/stream27_shared_reference_ntt_v1.h']:
            self.assertEqual(longer['sources'][name],pilot['sources'][name])
        ph=(BASE/'own100-serial-v1/source/fpga'/own.HEADER).read_bytes()
        fh=(BASE/'continuous1000-source-v1/source/fpga'/own.HEADER).read_bytes()
        self.assertEqual(fh,full.header(ph))
        self.assertIn(b'INTERVAL=8464,FIRST_DIGIT=8462,CARRY_DONE=12561',ph)
        self.assertEqual(full.config(),own.config(1000,1))
        self.assertEqual(own.bits(1000),full.bits(1000))
        for flag in ('FEEDBACK_INGRESS_REG','AUTO_CORRECTION_INGRESS_REG','C0_ADMISSION_DIRECT',
                     'LEAN_PROGRESS_WATCHDOG','LEAN_PRODUCTION'):
            self.assertEqual(longer['build']['parameters'][flag],1)
        cpp=(BASE/'own100-serial-v1/source/fpga'/own.CPP).read_text()
        self.assertEqual(cpp.count('DUT d{&context}'),1)
        self.assertLess(cpp.index('gfn16_runtime::configure(context,argc,argv)'),cpp.index('DUT d{&context}'))

    def test_periodic_windows_queue_and_publications(self):
        bundle=json.loads((ROOT/'results/throughput-20260929/trackS-c2-feedback12-native-v1/full-normal/production-bundle.json').read_bytes())
        for count,pubs,joint in ((2,[680695,1340159],1405695),
                               (100,[1510167,2169631],2235167),
                               (1000,[9127767,9787231],9852767)):
            events=model.event_calendar(bundle['geometry'],count)
            self.assertEqual(events['first_edges'],[204,4436])
            self.assertEqual(events['publication_edges'],pubs)
            self.assertEqual(events['full_read_completion_cycles'],joint)
            if count!=2:
                calendar=own.calendar(bundle['geometry'],count)
                self.assertEqual(calendar['frames'],2*count)
                self.assertEqual(calendar['launch_gaps'],[4232,4232])
                self.assertEqual(calendar['feedback_peak_rows'],[1,1])
                self.assertEqual(calendar['feedback_old_fifo_rows'],0)
                self.assertEqual(calendar['explicit_feedback_register_rows'],1)

    def test_source_only_forecast_not_borrowed(self):
        estimate=full.predict(250,440)
        self.assertIn('Own R12 LEAN',estimate['scope'])
        self.assertEqual(estimate['continuous_command_seconds_estimate'],4375)
        with self.assertRaises(ValueError):full.predict(250,249)
        self.assertFalse((BASE/'continuous1000-source-v1/forecast.json').exists())

    def test_source_owned_sample_recurrence_not_naive_edge_product(self):
        from fpga.reference import stream27_c2_r12_feedback_healthy_join as join
        bundle=join.source()
        value=join.calendar(bundle['geometry'],1911814)
        # Shared scratch serialization is ctx0-led; a later peer FIRST can
        # remain covered by that reservation. Derive the pair, not +I*K.
        self.assertEqual(value['pair_completion_cycles'],16182916927)
        self.assertEqual(value['full_read_completion_cycles'],16182982463)
        self.assertFalse(value['clock_or_area_claim'])


if __name__=='__main__':unittest.main()
