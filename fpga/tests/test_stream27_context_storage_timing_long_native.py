import json
import unittest
from fpga.reference import stream27_context_storage_timing_long_native as m


class StorageTimingLong(unittest.TestCase):
    def test_frozen_graph_and_real_descriptors(self):
        role, files = m.role(100, 1)
        self.assertEqual(len(role['build']['sv_sources']), 59)
        self.assertEqual(m.sha(files[m.CPP]), m.CPP_PIN)
        self.assertIn(b'COUNT=100,INTERVAL=8460', files[m.HEADER])
        self.assertEqual(role['timing_storage2']['own_long']['descriptors'], 198)
        self.assertEqual(role['timing_storage2']['own_long']['own_calendar']['frames'], 200)
        self.assertFalse(role['timing_storage2']['own_long']['prior_forecast_used'])

    def test_prefix_and_thread_envelope(self):
        self.assertEqual([r[:100] for r in m.bits(1000)], m.bits(100))
        self.assertEqual(sum(map(sum, m.bits(100))), 101)
        self.assertEqual(m.config(100, 1)['threads'], 1)
        with self.assertRaises(ValueError):
            m.config(100, 8)

    def test_strict_source_specific_footer(self):
        cfg = m.config(100, 1)
        value = dict(aw=16, p=16, contexts=2, bases=m.BASES, count_per_context=100,
            squares=200, descriptors=198, doubles=101, reads=262144, signed96=True,
            independent_reference=True, initial_resets=1, initial_load_words=131072,
            interval=8460, peer_live_reads=65536, model_threads=1,
            launches=[[204 + k*8460 for k in range(100)], [4434 + k*8460 for k in range(100)]],
            joint_cycles=2240000, overlap_edges=100, done_edges=[1540000, 1610000],
            warm_edges=[850303, 854533], setup_edges=[99, 199],
            reference_seconds=10., model_seconds=500., seconds=510.)
        def stdout():
            return 'R84_C2_THREAD100_PASS ' + json.dumps(value) + '\n'
        self.assertEqual(m.validate(stdout(), '', 0, cfg, {})['status'], 'PASS_expected_contracts')
        for key, bad in [('model_threads', 8), ('descriptors', 197), ('interval', 8459)]:
            old = value[key]
            value[key] = bad
            with self.assertRaises(ValueError):
                m.validate(stdout(), '', 0, cfg, {})
            value[key] = old
