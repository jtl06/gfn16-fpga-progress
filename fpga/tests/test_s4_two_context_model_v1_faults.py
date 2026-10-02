import subprocess
import sys
import unittest

from fpga.reference.s4_two_context_model_v1 import (
    Frame,ModelError,correction_calendar,geometry,schedule,stopped_context_buffer)
from fpga.reference.s4_two_context_model_v1_faults import cross_talk_negative


class TwoContextFaults(unittest.TestCase):
    def test_naive_T_offset_rejects_real_carry_overlap(self):
        for p in (8,16):
            with self.assertRaisesRegex(ModelError,'S4_TWO_RESOURCE_CARRY'):
                schedule(65536,p,offset=65536//p)

    def test_current_two_bank_capacity_cannot_admit_third_lease(self):
        for p in (8,16):
            with self.assertRaisesRegex(ModelError,'S4_TWO_LEASE_CAPACITY'):
                schedule(65536,p,capacity=2)

    def test_immediate_cold_B_correction_collides_shared_term_port(self):
        for p in (8,16):
            normal=schedule(65536,p)
            frames=[Frame(**{k:v for k,v in x.items() if k!='bank'}) for x in normal['frames']]
            with self.assertRaisesRegex(ModelError,'S4_TWO_RESOURCE_TERM_ROOT_ROM'):
                correction_calendar(frames,geometry(65536,p),immediate_cold=True)

    def test_same_edge_cache_capture_is_not_preedge_ready(self):
        g=geometry(65536,16);g['correction_cache_latency']+=g['cache_margin']+1
        normal=schedule(65536,16)
        frames=[Frame(**{k:v for k,v in x.items() if k!='bank'}) for x in normal['frames']]
        with self.assertRaisesRegex(ModelError,'S4_TWO_CACHE_DEADLINE'):
            correction_calendar(frames,g)

    def test_l1_latency_does_not_inherit_small_frozen_frontend(self):
        with self.assertRaisesRegex(ModelError,'S4_TWO_CACHE_DEADLINE'):
            schedule(256,16,correction_latency=77,correction_pair_interval=60)

    def test_feedback_FIFO_is_not_a_waiting_final_image_buffer(self):
        for p in (8,16):
            with self.assertRaisesRegex(ModelError,'S4_TWO_STOP_BUFFER_CAPACITY'):
                stopped_context_buffer(65536,p,capacity_rows=4)

    def test_context_parity_alias_detected_after_normal_agreement(self):
        for n in (32,256):
            for p in (8,16):
                self.assertEqual(cross_talk_negative(n,p)['signed_canonical_words_checked'],8*n)

    def test_typed_negative_is_exact_rc1_empty_stdout(self):
        for p in (8,16):
            run=subprocess.run([sys.executable,'-m','fpga.reference.s4_two_context_model_v1_faults',
                '--n','32','--p',str(p)],capture_output=True,text=True,check=False)
            self.assertEqual(run.returncode,1)
            self.assertEqual(run.stdout,'')
            self.assertEqual(run.stderr,f'S4_TWO_CONTEXT_CROSS_TALK_NEGATIVE_REJECT n=32 p={p}\n')


if __name__=='__main__':unittest.main()
