import copy
import unittest

from fpga.reference import stream27_context_timing_continuous as continuous


class TimingContinuousTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.files = continuous.role()

    def test_only_header_compiled_delta_and_same_eight_thread_model(self):
        import json
        pilot = json.loads(continuous.PILOT_MANIFEST.read_text())
        names = set(self.manifest['build']['sv_sources']) | {continuous.CPP,
            'rtl/tb/native_runtime_context_v1.h', 'rtl/tb/stream27_host_chain_full_reference_v1.h',
            'rtl/tb/stream27_shared_reference_ntt_v1.h'}
        self.assertEqual(len(self.manifest['build']['sv_sources']), 59)
        self.assertEqual(self.manifest['build'], pilot['build'])
        self.assertEqual(self.manifest['probe'], pilot['probe'])
        self.assertEqual(self.manifest['fixed_execution'], pilot['fixed_execution'])
        self.assertTrue(all(self.manifest['sources'][name] == pilot['sources'][name] for name in names))
        self.assertNotEqual(self.manifest['sources'][continuous.HEADER], pilot['sources'][continuous.HEADER])
        self.assertEqual(self.manifest['context_timing']['own_long']['own_calendar']['frames'], 2000)
        self.assertTrue(self.manifest['r84']['continuous']['no_reload_or_checkpoint_barrier'])

    def test_header_prefix_and_old_interval_rejected(self):
        old = (continuous.PILOT_SOURCE / continuous.HEADER).read_bytes()
        self.assertEqual(self.files[continuous.HEADER], continuous.header(old))
        for row, prefix in zip(continuous.bits(), continuous.bits(100)):
            self.assertEqual(row[:100], prefix)
        self.assertEqual(sum(map(sum, continuous.bits())), 1022)
        with self.assertRaises(ValueError):
            continuous.header(old.replace(b'INTERVAL=8460', b'INTERVAL=8459'))

    def test_pure_prediction_is_finite_and_never_an_old_source_forecast(self):
        result = continuous.predict(200.0, 400.0)
        self.assertEqual(result['continuous_command_seconds_estimate'], 3500.0)
        self.assertEqual(result['overall_seconds_estimate'], 4450.0)
        self.assertTrue(result['fits_finite_shape'])
        for command, overall in ((float('nan'), 400), (500, 400), (0, 400)):
            with self.assertRaises(ValueError):
                continuous.predict(command, overall)
        with self.assertRaises(ValueError):
            continuous.predict(200, 400, margin=1.5)


if __name__ == '__main__':
    unittest.main()
