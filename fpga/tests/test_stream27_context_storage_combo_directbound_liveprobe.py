import unittest
from fpga.reference import stream27_context_storage_combo_directbound_liveprobe as p


class DirectBoundLiveProbeTests(unittest.TestCase):
    def test_actual_parent_candidate_leaf_reverse_and_observer(self):
        m, files = p.role()
        self.assertEqual(len(m['build']['sv_sources']), 4)
        self.assertEqual(m['test_role'], 'deliberate_fault')
        wrapper = files['rtl/' + p.TOP + '.sv'].decode()
        self.assertNotRegex(wrapper, r'\b(always|always_ff|always_comb|initial)\b')
        self.assertIn('assign parent_bound_bad=parent_dut.correction_bad;', wrapper)
        self.assertIn('assign local_bound_bad=local_dut.correction_bad;', wrapper)
        self.assertTrue(m['steps'][0]['expected_stdout'].endswith('\n'))
        self.assertNotIn('\\n', m['steps'][0]['expected_stdout'])

    def test_boundary_count_independent_scalar(self):
        bases = [0, 1, 2, 1008, 1009, 1010, 0x7ffffffe, 0x7fffffff,
                 0x80000000, 0x80000001, 0xfffffffe, 0xffffffff, 1000000000]
        count = 13*11*16 + sum(-(1<<31) <= q < (1<<31) for b in bases
                              for q in (b-1, b, -b+1, -b))*16 + 6*16 + 20000
        self.assertEqual(count, 23024)


if __name__ == '__main__':
    unittest.main()
