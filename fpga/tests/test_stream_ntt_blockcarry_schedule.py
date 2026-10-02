"""Pure Python S1 tests; no HDL, vendor job, physical or board claim."""
import random
import unittest
from fpga.reference import stream_ntt_blockcarry_schedule as schedule
from fpga.reference import stream_ntt_blockwrap2_proposal as arithmetic
from fpga.reference.stream_ntt_model import ModelMismatch


class BlockcarryScheduleTests(unittest.TestCase):
    def test_minimum_and_conservative_boundary(self):
        self.assertEqual(schedule.minimum_base(32,8),172)
        self.assertEqual(schedule.minimum_base(32,16),300)
        self.assertEqual(schedule.minimum_base(65536,8),131077)
        for n,p in ((32,8),(32,16),(64,8),(64,16)):
            b=schedule.minimum_base(n,p)
            A=arithmetic.bound_proof(n,p,b)['doubled_coefficient_bound']
            for coefficients in ([A]*n,[-A]*n,[A if i%2 else -A for i in range(n)]):
                result=schedule.split_carry_tokens(coefficients,b,p)
                self.assertEqual(result['state'],arithmetic.carry_serial(coefficients,b,p)[0])
                self.assertEqual(result['last_digit_edge']-result['first_digit_edge'],n//p-1)
        with self.assertRaises(ValueError):schedule.minimum_base(16,8)

    def test_literal_joined_arithmetic_and_montgomery_fusion(self):
        rng=random.Random(300930)
        for n,p in ((32,8),(32,16),(64,8),(64,16),(128,8),(256,16)):
            b=schedule.minimum_base(n,p);K=2*n+24*p
            state=arithmetic.BlockState(tuple(rng.randrange(b) for _ in range(n)),b,
                tuple(rng.randrange(1-b,b) for _ in range(p)),
                tuple(rng.randrange(-K,K+1) for _ in range(p)))
            for double in (0,1):
                coefficients=arithmetic.square_coefficients(state,double)
                want=arithmetic.carry_serial(coefficients,b,p)[0]
                self.assertEqual(schedule.joined_square(state,double)['state'],want)
                # Second dependent epoch uses freshly produced block-boundary
                # tables, rather than reusing the initial arbitrary correction.
                next_want=arithmetic.carry_serial(arithmetic.square_coefficients(want,1-double),b,p)[0]
                self.assertEqual(schedule.joined_square(want,1-double)['state'],next_want)

    def test_segment_reseeding_and_zero_coefficients(self):
        for n,p in ((32,8),(64,16),(256,8),(512,16)):
            for field in range(3):
                table=[0 if i%2 else i+1 for i in range(p)]
                out=schedule.segmented_term(n,p,table,field)
                self.assertEqual(out['total_operations'],n)
                self.assertEqual(out['seed_operations']+out['update_operations'],n)
                with self.assertRaises(ModelMismatch):schedule.segmented_term(n,p,table,field,contexts=3)
                with self.assertRaises(ModelMismatch):schedule.segmented_term(n,p,[1]*p,field,wrong_frequency=True)

    def test_wrong_boundary_wire_rejected(self):
        with self.assertRaises(ModelMismatch):schedule.split_carry_tokens([0]*32,172,8,wrong_lane=True)

    def test_queued_dense_frames_and_complete_fifo_words(self):
        for n in (32,64,128,256,1024):
            for p in (8,16):
                result=schedule.joined_events(n,p)
                self.assertEqual(result['first_digit']+1,result['unwaited_interval'])
                self.assertEqual(result['epochs_checked'],2)
                delayed=schedule.joined_events(n,p,extra_correction_delay=100)
                self.assertGreater(delayed['wait'],0)
                self.assertEqual(delayed['pointwise_stored_bits'],delayed['pointwise_stored_points']*81)
                self.assertEqual(delayed['pointwise_stored_points'],min(delayed['wait'],n//p)*p)
                for direction in ('forward','inverse'):
                    for stage in result['transform_stage_events'][direction]:
                        self.assertEqual(stage['ports_per_FIFO'],'1R/1W')

    def test_fullN_queued_geometry(self):
        for p,want in ((8,16660),(16,8466)):
            result=schedule.joined_events(65536,p)
            self.assertEqual(result['interval'],want)
            self.assertEqual(result['wait'],0)
            self.assertEqual(result['tagged_tokens_checked'],4*65536)

    def test_fullN_explicit_executor_opt_in(self):
        # Gate fails before transform work; fullN may be separately authorized
        # on the bounded native CPU executor, never silently enabled locally.
        class State:digits=(0,)*65536;c0=(0,)*8;base=1_000_000_000
        with self.assertRaises(ValueError):schedule.joined_square(State())
        with self.assertRaises(ValueError):schedule.joined_square(State(),2)


if __name__=='__main__':unittest.main()
