"""Adapter/validator tests use synthetic calendars, not a timing-source PASS."""
import copy
import json
import unittest

from fpga.reference import stream27_context_timing_native as native


class ContextTimingNativeTests(unittest.TestCase):
    def fixture(self, stage):
        _, _, bundle = native.capture(stage)
        bundle = copy.deepcopy(bundle)
        g = bundle['geometry']
        # Explicitly synthetic +1 contract exercises adapter arithmetic only.
        g['warm_interval'] += 1
        g['first_digit'] += 1
        g['carry_done'] += 1
        calendar = dict(stage=stage, geometry=copy.deepcopy(g), schedule_proved=True,
                        joint_first_edges=[205, 205 + g['warm_interval'] // 2], capture_during_copy=True)
        freeze = dict(rtl_ready_at_utc='2026-10-02T00:00:00Z', binder_sha256='synthetic-test-only')
        return bundle, calendar, freeze

    def test_aw8_retains_actual_corpus_cpp_and_changes_only_calendar_header(self):
        original, old_files, _ = native.capture('aw8')
        bundle, calendar, freeze = self.fixture('aw8')
        manifest, files = native.adapt('aw8', bundle, calendar, freeze)
        self.assertEqual(manifest['steps'], original['steps'])
        self.assertEqual(files[manifest['build']['cpp_source']], old_files[manifest['build']['cpp_source']])
        header = files['rtl/tb/s4_host_contexts_config_v1.h'].decode()
        self.assertIn('INTERVAL=213,FIRST_DIGIT=194,CARRY_DONE=213', header)
        self.assertIn('FIRST[2]={205,311}', header)
        self.assertIn('counts=3/14 chains=2 squares=17 reads=1024', manifest['steps'][0]['expected_stdout'])
        self.assertFalse(manifest['context_timing']['clock_inherited'])
        self.assertFalse(manifest['context_timing']['parent_qualification_inherited'])

    def test_full_readonly_observer_and_oracle_unchanged(self):
        original, old_files, _ = native.capture('full')
        bundle, calendar, freeze = self.fixture('full')
        manifest, files = native.adapt('full', bundle, calendar, freeze)
        wrapper = files['rtl/' + manifest['build']['top'] + '.sv'].decode()
        self.assertIn('candidate.engine.arithmetic.profile_reciprocal[1]', wrapper)
        self.assertNotIn('always', wrapper)
        self.assertEqual(files[manifest['build']['cpp_source']], old_files[manifest['build']['cpp_source']])
        self.assertEqual(manifest['probe'], original['probe'])
        config = manifest['steps'][0]['validator']['config']
        self.assertEqual(config['interval'], 8460)
        self.assertEqual(config['carry_done'], 12558)
        self.assertEqual(config['first_edges'], [205, 4435])

    def test_missing_unproved_or_mismatched_calendar_is_not_inherited(self):
        bundle, calendar, freeze = self.fixture('aw8')
        for field, value in [('schedule_proved', False), ('stage', 'full'), ('capture_during_copy', False)]:
            bad = copy.deepcopy(calendar)
            bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                native.adapt('aw8', bundle, bad, freeze)
        bad = copy.deepcopy(calendar)
        bad['geometry']['warm_interval'] = 212
        with self.assertRaises(ValueError):
            native.adapt('aw8', bundle, bad, freeze)

    def test_full_typed_calendar_and_values_reject_old_interval(self):
        bundle, calendar, freeze = self.fixture('full')
        config = native.validator_config(bundle, calendar)
        value = dict(aw=16, p=16, contexts=2, bases=config['bases'], squares=8, reads=6 * 65536,
            signed96=True, context_alone_bit_identical=True, independent_reference=True,
            interval=8460, pair_launch_cycles=8460, peer_live_reads=65536, model_threads=1,
            launches=[[205, 8665], [4435, 12895]], single_cycles=[743000, 743100],
            joint_cycles=1400000, overlap_edges=20000, done_edges=[677000, 1333000],
            warm_edges=[21224, 25454], setup_edges=[99, 199], single_first=[104, 104], seconds=300.0)
        def check(v):
            return native.validate_full('R84_C2_FULL_PASS ' + json.dumps(v) + '\n', '', 0, config, {})
        self.assertEqual(check(value)['status'], 'PASS_expected_contracts')
        for key, replacement in [('interval', 8459), ('warm_edges', [21223, 25454]),
                                 ('bases', [config['bases'][0]] * 2), ('peer_live_reads', 65535),
                                 ('launches', [[204, 8664], [4434, 12894]]), ('model_threads', 8)]:
            bad = copy.deepcopy(value)
            bad[key] = replacement
            with self.subTest(key=key), self.assertRaises(ValueError):
                check(bad)


if __name__ == '__main__':
    unittest.main()
