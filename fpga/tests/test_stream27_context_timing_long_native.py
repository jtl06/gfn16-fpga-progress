import copy
import json
import unittest

from fpga.reference import stream27_context_timing_long_native as long


class TimingLongNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.files = long.role(100)

    def test_exact_frozen59_and_uninterrupted_source_driver(self):
        self.assertEqual(len(self.manifest['build']['sv_sources']), 59)
        self.assertEqual(long.sha(self.files[long.CPP]), long.CPP_PIN)
        cpp = self.files[long.CPP]
        self.assertIn(b'const bool accepted_command=d.command_accept;', cpp)
        self.assertIn(b'd.command_index=next_command[command_ctx]', cpp)
        self.assertEqual(cpp.count(b'Result joint=run(d,3,input,reference);'), 1)
        self.assertIn(b'COUNT=100,INTERVAL=8460,FIRST_DIGIT=8459,CARRY_DONE=12558', self.files[long.HEADER])
        self.assertIn(b'R84_PER_CONTEXT_PROFILE_SNAPSHOT', cpp)
        self.assertFalse(self.manifest['context_timing']['own_long']['old_pilot_forecast_used'])
        self.assertEqual(self.manifest['rtl_readiness']['rtl_ready_at_utc'], '2026-10-02T05:26:55Z')

    def test_own200_frame_ports_and_full_period_feedback(self):
        model = self.manifest['context_timing']['own_long']['own_calendar']
        self.assertEqual(model['frames'], 200)
        self.assertEqual(model['launch_gaps'], [4230, 4230])
        self.assertEqual(model['lease_peak'], 3)
        self.assertEqual(model['feedback_peak_rows'], [0, 0])
        self.assertGreaterEqual(min(row['margin'] for row in model['correction']), 0)
        self.assertFalse(model['full_N_numeric_performed'])

    @staticmethod
    def footer(count=100):
        launch = [[204 + k * 8460 for k in range(count)], [4434 + k * 8460 for k in range(count)]]
        warm = [row[-1] + 12559 for row in launch]
        done = [warm[0] + 660000, warm[0] + 1320000]
        return dict(aw=16, p=16, contexts=2, bases=long.BASES, count_per_context=count, squares=2 * count,
            descriptors=2 * (count - 1), doubles=sum(map(sum, long.bits(count))), reads=4 * 65536, signed96=True,
            independent_reference=True, initial_resets=1, initial_load_words=2 * 65536, interval=8460,
            peer_live_reads=65536, model_threads=8, launches=launch, joint_cycles=done[1] + 65536,
            overlap_edges=1000000, done_edges=done, warm_edges=warm, setup_edges=[99, 199],
            reference_seconds=100.0, model_seconds=400.0, seconds=500.0)

    def test_exact_edges_thread_phase_and_counter_mutants(self):
        def check(value):
            return long.validate('R84_C2_THREAD100_PASS ' + json.dumps(value) + '\n', '', 0, long.config(100), {})
        self.assertEqual(check(self.footer())['status'], 'PASS_expected_contracts')
        for key, wrong in [('interval', 8459), ('model_threads', 1), ('descriptors', 197),
                           ('initial_resets', 2), ('doubles', 100), ('seconds', 501.0)]:
            value = self.footer()
            value[key] = wrong
            with self.subTest(key=key), self.assertRaises(ValueError):
                check(value)
        value = copy.deepcopy(self.footer())
        value['launches'][1][50] += 1
        with self.assertRaises(ValueError):
            check(value)

    def test_future1000_count_metadata_not_outcome_inheritance(self):
        value = self.footer(1000)
        self.assertEqual(long.validate('R84_C2_THREAD100_PASS ' + json.dumps(value) + '\n', '', 0,
                                      long.config(1000), {})['status'], 'PASS_expected_contracts')
        self.assertEqual(sum(map(sum, long.bits(1000))), 1022)
        for row, prefix in zip(long.bits(1000), long.bits(100)):
            self.assertEqual(row[:100], prefix)


if __name__ == '__main__':
    unittest.main()
