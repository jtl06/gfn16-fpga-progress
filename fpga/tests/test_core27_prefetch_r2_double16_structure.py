"""Source/control-model qualification only; no HDL compilation or execution."""
import itertools
from pathlib import Path
import random
import unittest
from unittest.mock import patch

from reference import core27_prefetch_r2_double16_structure as s


class Double16StructureTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def read(self, name):
        return (self.root / 'rtl/kernel' / (name + '.sv')).read_text()

    def test_pinned_clone_and_frozen_dependency_identities(self):
        result = s.validate_files(self.root)
        self.assertEqual(result, {'rtl/kernel/' + s.CANDIDATE + '.sv': s.CANDIDATE_SHA})
        self.assertEqual(self.read(s.CANDIDATE), s.expected(self.read(s.ANCESTOR)))

    def test_exact_five_control_changes_plus_module_identity(self):
        original = self.read(s.ANCESTOR)
        normalized = self.read(s.CANDIDATE)
        self.assertEqual(len(s.SUBSTITUTIONS), 6)
        for old, new in reversed(s.SUBSTITUTIONS):
            self.assertEqual(normalized.count(new), 1)
            normalized = normalized.replace(new, old)
        self.assertEqual(normalized, original)

    def test_same_edge_reset_hold_and_consumer_topology(self):
        candidate = self.read(s.CANDIDATE)
        self.assertNotIn('double_reg', candidate)
        for anchor in ('localparam int CARRY_LANES=16;',
                       'localparam int IO_WIDTH=VECTOR_IO ? CARRY_LANES : 1;',
                       'always_ff @(posedge clk or negedge rst_n) begin\n        if(!rst_n) begin\n            state<=IDLE;',
                       "double_lane_q<='0;",
                       'base_reg<=base; double_lane_q<={IO_WIDTH{double_bit}}; busy<=1;',
                       'double_lane_q[h] ? (coefficient_words[h] <<< 1)',
                       'double_lane_q[0] ? (coefficient <<< 1)',
                       '(* preserve, dont_merge *) logic [IO_WIDTH-1:0] double_lane_q;'):
            self.assertEqual(candidate.count(anchor), 1)
        self.assertEqual(s.IO_WIDTH - 1, 15)

    def test_unrelated_fsm_interfaces_masks_and_child_binding_unchanged(self):
        original = self.read(s.ANCESTOR)
        candidate = self.read(s.CANDIDATE)
        for anchor in ('if(base<2 || base>1000000000 || AW<1 || AW>16 ||',
                       "NTT_LANES!=64 || base <= 32'(2*N+4)",
                       'genefer_ntt_banked27_prefetch_r2_host_broadcast_engine #(',
                       'stream_valid(state==RESIDUES && crt_valid)',
                       'if(residue_issue) issue_count<=',
                       'profile_cache_valid<=0;',
                       'carry_stream_ready;',
                       'coefficient_words[h])',
                       '.stream_mask(IO_MASK)'):
            self.assertEqual(candidate.count(anchor), original.count(anchor))

    def test_acceptance_domain_boundaries(self):
        for aw in (1, 5, 7, 16):
            minimum = 2 * (1 << aw) + 4
            self.assertFalse(s.accepts_start(minimum, aw))
            self.assertTrue(s.accepts_start(minimum + 1, aw))
        self.assertTrue(s.accepts_start(1_000_000_000))
        self.assertFalse(s.accepts_start(1_000_000_001))
        self.assertFalse(s.accepts_start(604_832_956, ntt_lanes=16))

    def test_exhaustive_bounded_accepted_rejected_busy_and_reset_transitions(self):
        events = (('assert',), ('release',),
                  ('edge', 1, 1, 1, 0), ('edge', 1, 1, 1, 1),
                  ('edge', 0, 1, 1, 0), ('edge', 0, 1, 1, 1),
                  ('edge', 1, 1, 0, 0), ('edge', 1, 1, 0, 1))
        count = 0
        for sequence in itertools.product(events, repeat=5):
            for original, copies in s.control_trace((('assert',), ('release',)) + sequence):
                self.assertEqual(copies, (original,) * 16)
                count += 1
        self.assertEqual(count, 229376)

    def test_input_toggles_hold_rejected_start_and_immediate_next_start(self):
        events = (('assert',), ('release',), ('edge', 1, 1, 1, 1),
                  ('edge', 0, 1, 1, 0), ('edge', 1, 0, 1, 0),
                  ('edge', 1, 1, 0, 0), ('edge', 1, 1, 1, 0))
        values = [value for value, _ in s.control_trace(events)]
        self.assertEqual(values, [0, 0, 1, 1, 1, 1, 0])
        self.assertTrue(all(copies == (value,) * 16 for value, copies in s.control_trace(events)))

    def test_asynchronous_assertion_and_held_reset_ignore_new_start(self):
        events = (('edge', 1, 1, 1, 1), ('assert',),
                  ('edge', 1, 1, 1, 1), ('release',), ('edge', 1, 0, 1, 1))
        self.assertEqual(s.control_trace(events), [(1, (1,) * 16)] + [(0, (0,) * 16)] * 4)

    def test_wrong_predecessor_and_free_running_capture_witnesses(self):
        start = (('assert',), ('release',), ('edge', 1, 1, 1, 1))
        self.assertNotEqual(s.control_trace(start), s.control_trace(start, wrong_delay=True))
        busy_toggle = start + (('edge', 0, 1, 1, 0),)
        self.assertNotEqual(s.control_trace(busy_toggle),
                            s.control_trace(busy_toggle, wrong_free_running=True))

    def test_signed96_lane_mux_and_truncation_equivalence(self):
        rng = random.Random(0xD016)
        boundaries = (-(1 << 95), -(1 << 94), -1, 0, 1, (1 << 94) - 1, (1 << 95) - 1)
        values = boundaries + tuple(rng.randrange(-(1 << 95), 1 << 95) for _ in range(1000))
        for selector in (0, 1):
            original, copies = s.control_trace((('edge', 1, 1, 1, selector),))[-1]
            for coefficient in values:
                expected = s.carry_mux(coefficient, original)
                self.assertTrue(all(s.carry_mux(coefficient, copy) == expected for copy in copies))
        self.assertEqual(s.carry_mux((1 << 95) - 1, 1), -2)
        self.assertEqual(s.carry_mux(-(1 << 95), 1), 0)

    def test_semantic_and_topology_source_mutants_rejected(self):
        path = self.root / 'rtl/kernel' / (s.CANDIDATE + '.sv')
        original = self.read(s.CANDIDATE)
        read = Path.read_text
        mutations = (
            ('(* preserve, dont_merge *)', '(* preserve *)'),
            ('(* preserve, dont_merge *)', '(* dont_merge *)'),
            ('double_lane_q[h] ?', 'double_lane_q[0] ?'),
            ('double_lane_q[0] ? (coefficient <<< 1)', 'double_lane_q[1] ? (coefficient <<< 1)'),
            ("double_lane_q<='0;", "double_lane_q<='1;"),
            ('double_lane_q<={IO_WIDTH{double_bit}};', 'double_lane_q<={IO_WIDTH{double_lane_q[0]}};'),
            ('case(state)', 'double_lane_q<={IO_WIDTH{double_bit}}; case(state)'),
            ('clk or negedge rst_n', 'clk'),
            ("NTT_LANES!=64 || base <= 32'(2*N+4)", "NTT_LANES!=64 || base < 32'(2*N+4)"),
            ('genefer_ntt_banked27_prefetch_r2_host_broadcast_engine #(',
             'genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_engine #('),
        )
        for old, new in mutations:
            self.assertIn(old, original)
            mutant = original.replace(old, new)
            def supplied(p, *args, **kwargs):
                return mutant if p == path else read(p, *args, **kwargs)
            with self.subTest(anchor=old), patch.object(Path, 'read_text', supplied), self.assertRaises(ValueError):
                s.validate_files(self.root)

    def test_bad_events_and_changed_ancestor_rejected(self):
        for event in (('bad',), ('edge', 1, 1, 1, 2), ('edge', True, 1, 1, 0)):
            with self.assertRaises(ValueError):
                s.control_trace((event,))
        with self.assertRaisesRegex(ValueError, 'frozen ancestor'):
            s.expected(self.read(s.ANCESTOR) + '\n')


if __name__ == '__main__':
    unittest.main()
