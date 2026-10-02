import unittest

from fpga.reference.stream_ntt_two_context_model import (
    ContextBank, Frame, abort_isolation, schedule, transform_frames, verify_sources,
)
from fpga.reference.stream_ntt_blockcarry_schedule import joined_events
from fpga.reference.stream_ntt_model import ModelMismatch


class TwoContextTests(unittest.TestCase):
    def test_frozen_sources(self):
        self.assertEqual(len(verify_sources()), 3)

    def test_small_matched_single_context_timing(self):
        for n in (32,64,128,256,1024):
            result = schedule(n, 3); old = joined_events(n,8)
            self.assertEqual(result['per_context_interval'], old['interval'])
            self.assertEqual(result['minimum_correction_margin'], old['next_X']-old['term_initialization_ready'])
            self.assertEqual(result['forward']['tokens_checked'], 6*n)
            self.assertEqual(result['resources']['extra_transform_data_FIFO_words'],0)

    def test_full_size_event_only(self):
        result = schedule(65536,3)
        self.assertEqual(result['per_context_interval'],16660)
        self.assertEqual(result['launch_gaps'],[8330,8330])
        self.assertEqual(result['minimum_correction_margin'],79)
        self.assertEqual(result['forward']['tokens_checked']+result['inverse']['tokens_checked'],786432)
        for direction in ('forward','inverse'):
            stages=result[direction]['stages']
            self.assertEqual(sum(s['allocated_words'] for s in stages),65536-8)
            self.assertEqual(max(s['peak_resident_frames'] for s in stages),2)
            for stage in stages:
                self.assertLessEqual(stage['peak_live_words'],stage['allocated_words'])
                for a,b in zip(stage['frames'],stage['frames'][1:]):
                    self.assertLess(a['input_last'],b['input_first'])
                    self.assertLess(a['butterfly_last_output'],b['butterfly_first'])
        self.assertEqual(result['resources']['optional_extra_readback_M20K_shape_count'],112)

    def test_arbitrary_gaps_back_to_back_and_three_owners(self):
        for gap in (0,1,3,7,13,31):
            frames=[Frame(i%2,i//2,i, i*(32+gap)) for i in range(4)]
            for inverse in (False,True):
                value=transform_frames(256,frames,inverse=inverse)
                self.assertEqual(value['tokens_checked'],1024)

    def test_collision_negative(self):
        with self.assertRaisesRegex(ModelMismatch,'S5-input-overlap'):
            transform_frames(256,[Frame(0,0,0,0),Frame(1,0,0,31)])

    def test_phase_and_flush_negatives(self):
        for mutant in ('flush-on-frame','free-running-phase'):
            with self.assertRaisesRegex(ModelMismatch,'S5-(shuffle-valid|context-order|stage-edges)'):
                transform_frames(256,[Frame(0,0,0,0),Frame(1,0,0,33)],mutant=mutant)

    def test_correction_arrival_negative(self):
        with self.assertRaisesRegex(ModelMismatch,'S5-correction-arrival'):
            schedule(256,2,correction_delay=24)

    def test_abort_isolation_control_and_mutant(self):
        self.assertTrue(abort_isolation())
        with self.assertRaisesRegex(ModelMismatch,'S5-abort-leakage'):
            abort_isolation(mutant=True)

    def test_base_load_read_double_and_generations(self):
        bank=ContextBank(); bank.load(0,[7]*32,173); bank.load(1,[9]*32,1009)
        b=bank.read(1); a=bank.start(0,1)
        with self.assertRaisesRegex(ModelMismatch,'S5-host-busy'): bank.read(0)
        with self.assertRaisesRegex(ModelMismatch,'S5-host-busy'): bank.change_base(0,1009)
        # B can change while A's tagged frame is in flight.
        bank.load_digit(1,3,11); self.assertEqual(bank.read(1),b+2*1009**3)
        bank.change_base(1,2003); b2=bank.read(1)
        self.assertTrue(bank.complete(a))
        self.assertEqual(bank.read(0),(a[3]**2*2)%(173**32+1))
        self.assertEqual(bank.read(1),b2)
        old=bank.start(0); bank.abort(0); bank.load(0,[2]*32,173)
        self.assertFalse(bank.complete(old)); self.assertEqual(bank.canonical_digits(0),[2]*32)
        self.assertEqual(bank.read(1),b2)

    def test_changed_base_reject_and_global_reset(self):
        bank=ContextBank(); bank.load(0,[999]*32,1009); bank.load(1,[4]*32,173)
        job=bank.start(1)
        with self.assertRaisesRegex(ModelMismatch,'S5-base-reload'): bank.change_base(0,173)
        self.assertTrue(bank.complete(job))
        bank.reset_all()
        for ctx in (0,1):
            with self.assertRaisesRegex(ModelMismatch,'S5-reload-required'): bank.read(ctx)

    def test_exceptional_minus_one_base_change_partial_load(self):
        bank=ContextBank(); bank.load(0,[-1]+[0]*31,173)
        bank.change_base(0,1009)
        self.assertEqual(bank.read(0),1009**32)
        bank.load_digit(0,1,2)
        self.assertEqual(bank.read(0),2*1009-1)

    def test_protocol_profile_base_bound(self):
        with self.assertRaises(ValueError): ContextBank().load(0,[0]*32,171)


if __name__=='__main__': unittest.main()
