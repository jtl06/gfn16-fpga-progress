import json
import unittest
from fpga.reference import stream27_context_storage_combo_oneshot_long_native as m


class CombinedStorageLong(unittest.TestCase):
    def test_actual_toolchain_identity_emitter(self):
        source=(m.ROOT/m.SELF).read_text()
        self.assertIn("tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1'",source)
        self.assertNotIn('verilator6032',source)

    def test_exact_original_graph_and_calendar(self):
        role, files = m.role(100, 1)
        self.assertEqual(len(role['build']['sv_sources']), 56)
        self.assertEqual(m.sha(files[m.CPP]), m.CPP_PIN)
        self.assertIn(b'COUNT=100,INTERVAL=8459,FIRST_DIGIT=8458,CARRY_DONE=12557', files[m.HEADER])
        calendar = role['context_storage_combo_oneshot']['own_long']['own_calendar']
        self.assertEqual(calendar['frames'], 200)
        self.assertEqual(calendar['launch_gaps'], [4229, 4230])
        self.assertEqual(calendar['lease_peak'], 3)
        self.assertFalse(role['context_storage_combo_oneshot']['own_long']['prior_forecast_used'])

    def test_ledger_and_no_timing_inheritance(self):
        cfg = m.config(100, 1)
        launches = [[204 + k*8459 for k in range(100)], [4433 + k*8459 for k in range(100)]]
        warm = [row[-1]+12558 for row in launches]
        done = [warm[0]+2+4096+655360+6]
        done.append(max(warm[1]+2, done[0]+1)+4096+655360+6)
        value = dict(aw=16, p=16, contexts=2, bases=m.BASES, count_per_context=100,
            squares=200, descriptors=198, doubles=101, reads=262144, signed96=True,
            independent_reference=True, initial_resets=1, initial_load_words=131072,
            interval=8459, peer_live_reads=65536, model_threads=1, launches=launches,
            joint_cycles=done[-1]+65536, overlap_edges=100, done_edges=done,
            warm_edges=warm, setup_edges=[99, 199], reference_seconds=10., model_seconds=500., seconds=510.)
        def stdout():
            return 'R84_C2_THREAD100_PASS ' + json.dumps(value) + '\n'
        self.assertEqual(m.validate(stdout(), '', 0, cfg, {})['status'], 'PASS_expected_contracts')
        value['interval'] = 8460
        with self.assertRaises(ValueError):
            m.validate(stdout(), '', 0, cfg, {})
        value['interval'] = 8459
        value['done_edges'][0] += 1
        with self.assertRaises(ValueError):
            m.validate(stdout(), '', 0, cfg, {})
