import copy
import json
import unittest

from fpga.reference import stream27_p16_two_context_continuous as continuous


class C2ContinuousTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m, cls.files = continuous.role()
        cls.pilot = json.loads(continuous.PILOT_MANIFEST.read_text())

    def test_only_private_count_header_changes_compiled_sources(self):
        self.assertEqual(self.m['build'], self.pilot['build'])
        self.assertEqual(self.m['probe'], self.pilot['probe'])
        self.assertEqual(self.m['fixed_execution'], self.pilot['fixed_execution'])
        names = set(self.m['build']['sv_sources']) | {self.m['build']['cpp_source']}
        self.assertTrue(all(self.m['sources'][name] == self.pilot['sources'][name] for name in names))
        self.assertEqual(len(self.m['build']['sv_sources']), 54)
        self.assertNotEqual(self.m['sources'][continuous.HEADER], self.pilot['sources'][continuous.HEADER])
        old = (continuous.PILOT_SOURCE/continuous.HEADER).read_bytes()
        self.assertEqual(self.files[continuous.HEADER], continuous.header(old))
        changed = old.replace(b'COUNT=100,INTERVAL', b'COUNT=999,INTERVAL')
        with self.assertRaises(ValueError):
            continuous.header(changed)
        for row, pilot in zip(continuous.bits(), continuous.bits(100)):
            self.assertEqual(row[:100], pilot)
        self.assertEqual(sum(map(sum, continuous.bits())), 1022)

    def test_feed_loop_and_owner_remain_uninterrupted(self):
        source = self.files[continuous.CPP].decode()
        self.assertIn('d.start_contexts=d.batch_mode=d.feed_mode=mask', source)
        self.assertIn('d.command_index=next_command[command_ctx]', source)
        self.assertIn('const bool accepted_command=d.command_accept;', source)
        self.assertIn('s4_full_reference::square(reference[ctx],BASES[ctx],BITS[ctx][k])', source)
        self.assertEqual(source.count('Result joint=run(d,3,input,reference);'), 1)
        self.assertEqual(self.m['r84']['continuous']['initial_resets'], 1)
        self.assertTrue(self.m['r84']['continuous']['no_reload_or_checkpoint_barrier'])

    @staticmethod
    def footer():
        launch = [[204+k*8459 for k in range(1000)], [4433+k*8459 for k in range(1000)]]
        warm = [row[-1]+12558 for row in launch]
        # No invented precise finalizer prediction: the bench proves actual9N
        # canonical/N+3 copy, these positive mock values exercise the parser.
        done = [warm[0]+660000, warm[0]+1320000]
        return dict(aw=16, p=16, contexts=2, bases=continuous.BASES, count_per_context=1000,
            squares=2000, descriptors=1998, doubles=1022, reads=4*65536,
            signed96=True, independent_reference=True, initial_resets=1,
            initial_load_words=2*65536, interval=8459, peer_live_reads=65536, model_threads=8,
            launches=launch, joint_cycles=done[1]+65536, overlap_edges=1500000,
            done_edges=done, warm_edges=warm, setup_edges=[99,199],
            reference_seconds=100., model_seconds=400., seconds=500.)

    def test_exact1000_footer_and_counter_mutants(self):
        def check(v):
            return continuous.validate('R84_C2_THREAD100_PASS '+json.dumps(v)+'\n', '', 0, continuous.config(), {})
        self.assertEqual(check(self.footer())['status'], 'PASS_expected_contracts')
        for key, wrong in [('count_per_context',100), ('squares',1999), ('descriptors',1997),
                           ('doubles',1021), ('model_threads',1), ('initial_resets',2),
                           ('initial_load_words',65536), ('reads',131072), ('seconds',501.)]:
            value = self.footer(); value[key] = wrong
            with self.subTest(key=key), self.assertRaises(ValueError):
                check(value)
        value = self.footer(); value['launches'][1][999] += 1
        with self.assertRaises(ValueError):
            check(value)
        value = self.footer(); value['setup_edges'][0] += 1
        with self.assertRaises(ValueError):
            check(value)

    def test_own_measured_source_thread_forecast_not_c1(self):
        value = continuous.forecast(self.m)
        self.assertEqual(value['schema'], continuous.SCHEMA)
        self.assertEqual(value['pilot_native_validation']['measurements']['count_per_context'], 100)
        self.assertTrue(value['forecast']['fits_finite_shape'])
        self.assertAlmostEqual(value['forecast']['continuous_command_seconds_estimate'], 2479.583882300012)
        self.assertAlmostEqual(value['forecast']['overall_seconds_estimate'], 3433.0724904160197)
        self.assertEqual(value['full_config']['count'], 1000)
        self.assertEqual(value['allowed_compiled_delta']['path'], continuous.HEADER)
        with self.assertRaises(ValueError):
            continuous.predict(10, 20, margin=1.5)
        with self.assertRaises(ValueError):
            continuous.predict(float('nan'), 20)


if __name__ == '__main__':
    unittest.main()
