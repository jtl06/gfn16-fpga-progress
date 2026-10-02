"""Source-delta and permutation checks, not RTL or physical validation."""
from pathlib import Path
import random
import unittest
from reference.ntt27_rootpipe_structure import expected, validate_files


class RootPipelineStructure(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.source = (self.root/'rtl/kernel/genefer_ntt_banked27_tiled_engine.sv').read_text()
        self.candidate = (self.root/'rtl/kernel/genefer_ntt_banked27_rootpipe_engine.sv').read_text()

    def test_exact_frozen_source_delta(self):
        self.assertEqual(validate_files(self.root)['status'], 'passed_structure_not_simulation')

    def test_reject_unrelated_ancestor_edit(self):
        with self.assertRaises(ValueError):
            expected(self.source.replace('completed+bf_lanes', 'completed+1'))

    def test_alignment_is_explicit_in_candidate(self):
        required = ['ROOT_CUT=KW>1 ? KW/2 : 1', 'root_cut_q[b]<=root_xor_stages[ROOT_CUT].words[b]',
                    'bf_route_valid<=bf_mid_valid', 'mul_route_valid<=mul_mid_valid',
                    'data_route_q[b]<=data_mid_q[b]', 'root_point_q[b]<=root_point_mid_q[b]',
                    'pairing_e<=pairing_mid', 'orientation_e<=orientation_mid',
                    'rotation_mid<=rotation_d', 'folded_root_bank_mid<=folded_root_bank_d',
                    'stage_bit_e<=stage_bit_mid', 'low_stage_e<=low_stage_mid',
                    'point_half_e<=point_half_mid', 'row_tag[8][bank]',
                    'point_half_pipe[8]', 'orientation_pipe[8]',
                    'if(ROOT_CUT==KW) assign root_rotate_option[b][d]=root_cut_q[ROT]']
        for anchor in required:
            self.assertIn(anchor, self.candidate)
        # Host memory timing, arithmetic primitive and six-cycle type tag unchanged.
        for anchor in ['assign read_data=data_q[host_bank_d]',
                       'point_type_pipe<={point_type_pipe[4:0],mul_route_valid[lane]}']:
            self.assertIn(anchor, self.candidate)

    def test_split_permutation_matches_independent_index(self):
        # Exhaust all XOR controls and rotations for every supported bank count.
        # Values label source banks, so mismatches cannot hide behind equal data.
        for kw in range(1, 8):
            banks = 1 << kw
            cut = max(1, kw//2)
            for control in range(banks):
                words = list(range(banks))
                for bit in range(cut):
                    words = [words[b ^ (1 << bit)] if control >> bit & 1 else words[b]
                             for b in range(banks)]
                registered = words[:]
                for bit in range(cut, kw):
                    registered = [registered[b ^ (1 << bit)] if control >> bit & 1 else registered[b]
                                  for b in range(banks)]
                for rotation in range(kw):
                    def rol(b):
                        return ((b << rotation) | (b >> (kw-rotation))) & (banks-1)
                    result = [registered[rol(b)] for b in range(banks)]
                    self.assertEqual(result, [rol(b) ^ control for b in range(banks)])

    def test_stream_control_delay_matters(self):
        # Witness why upper XOR/rotation controls must come from the cut frame,
        # not the next RAM response. This is an independent abstract model.
        rng = random.Random(0xC071)
        wrong_tail = wrong_rotation = False
        for _ in range(128):
            control, following = rng.randrange(128), rng.randrange(128)
            rotation, next_rotation = rng.randrange(7), rng.randrange(7)
            low, high = control & 7, control & ~7
            first = [b ^ low for b in range(128)]
            for b in range(128):
                rol = lambda b, r: ((b << r) | (b >> (7-r))) & 127
                good = first[rol(b, rotation) ^ high]
                self.assertEqual(good, rol(b, rotation) ^ control)
                wrong_tail |= good != first[rol(b, rotation) ^ (following & ~7)]
                wrong_rotation |= good != first[rol(b, next_rotation) ^ high]
        self.assertTrue(wrong_tail and wrong_rotation)

    def test_cycle_cost_model(self):
        # Five phases: twist, forward, square, unnormalized inverse, untwist.
        n, lanes, lg = 65536, 64, 16
        old = 2*lg*((n+2*lanes-1)//(2*lanes)+1+8) + 3*((n+lanes-1)//lanes+8)
        new = 2*lg*((n+2*lanes-1)//(2*lanes)+1+9) + 3*((n+lanes-1)//lanes+9)
        self.assertEqual((old, new, new-old), (19768, 19803, 35))

    def test_point_root_delay_mutant_needs_high_fold_boundary(self):
        # A skipped point-root delay can hide while bank halves alternate:
        # that bank's RAM value is held for two edges. The first consecutive
        # accesses to the same half occur at group127→128 (N must be>=16384).
        # This identifies necessary directed coverage, not RTL equivalence.
        def bank(address):
            result=0
            while address:
                result^=address & 127
                address>>=7
            return result
        def half(group):return bank(group*64)>>6
        same=[g for g in range(255) if half(g)==half(g+1)]
        self.assertEqual(same[0],127)
        self.assertTrue(all(half(g)!=half(g+1) for g in range((1<<13)//64-1)))
        self.assertEqual((127*64>>7,128*64>>7),(63,64))
        self.assertEqual(half(127),half(128))


if __name__ == '__main__':
    unittest.main()
