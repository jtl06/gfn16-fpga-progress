import unittest
from fpga.reference.stream27_commutator_slots_model import (
    SlotPair,Token,scenario,token_width_scenarios,verify_sources,
)


class ComposableSlots(unittest.TestCase):
    def test_source_pins(self):self.assertEqual(len(verify_sources()),2)

    def test_two_cell_geometry_gaps_contexts(self):
        for contexts in (1,2):
            for depths in ((1,1),(1,2),(2,1),(2,4),(4,2),(4,16),(16,4)):
                for gap in (0,1,3,138):
                    result=scenario(*depths,gap=gap,contexts=contexts)
                    self.assertEqual(result['physical_rows'],3*result['T'])
                    self.assertEqual(result['physical_frame_starts'],3)
                    self.assertEqual(result['delay'],sum(depths)+1)

    def test_cancel_head_middle_tail_never_holes_B(self):
        for depths in ((1,2),(2,4),(16,4),(256,16),(4096,1)):
            T=max(8,2*max(depths))
            for cancel in (0,T//2,T-1,T+sum(depths)):
                result=scenario(*depths,cancel_age=cancel)
                self.assertEqual(result['physical_rows'],3*T)
                self.assertEqual(result['B_rows'],T)
                self.assertGreater(result['killed_rows_still_transported'],0)

    def test_reset_all_small_phase_and_link_ages_immediate_restart(self):
        for depths in ((1,1),(1,2),(2,4),(4,2)):
            T=max(8,2*max(depths));delay=sum(depths)+1
            for age in range(3*T+delay):
                result=scenario(*depths,reset_age=age)
                self.assertGreaterEqual(result['physical_rows'],3*T)

    def test_broken_filtered_link_and_sameedge_negative(self):
        with self.assertRaisesRegex(AssertionError,'SLOTS_CHAIN_CADENCE'):
            scenario(2,4,cancel_age=7,broken_link=True)
        with self.assertRaisesRegex(AssertionError,'SLOTS_CHAIN_EDGE'):
            scenario(2,4,same_edge=True)

    def test_killed_frame_start_is_physical_and_payload_keeps_moving(self):
        cell=SlotPair(2,8);output=[]
        for tick in range(10):
            row=tuple(Token(tick*2+l,0,0,tick*2+l) for l in range(2)) if tick<8 else None
            out=cell.edge(row,frame_start=tick==0,generations=(1,0))
            if out.slot_valid:output.append(out)
        self.assertEqual(len(output),8);self.assertTrue(output[0].frame_start)
        self.assertTrue(all(not r.eligible for r in output))
        self.assertEqual(sorted(t.data for r in output for t in r.tokens),list(range(16)))

    def test_malformed_physical_stream_quarantines_not_context_cancel(self):
        cell=SlotPair(2,8);row=(Token(1,0,0,0),Token(2,0,0,1))
        self.assertFalse(cell.edge(row,frame_start=True).error)
        self.assertTrue(cell.edge().error)
        self.assertTrue(cell.edge(row,frame_start=True).error)
        self.assertFalse(cell.edge(reset=True).error)
        self.assertFalse(cell.edge(row,frame_start=True).error)

    def test_widths_are_explicit_not_fit_claim(self):
        counts=token_width_scenarios()
        self.assertEqual(counts['diagnostic']['stored_bits'],53)
        self.assertEqual(counts['proposed_minimal']['stored_bits'],38)
        self.assertFalse(counts['proposed_minimal']['adopted'])
        self.assertGreater(counts['diagnostic']['M20K_per_FIFO_shape'],counts['proposed_minimal']['M20K_per_FIFO_shape'])


if __name__=='__main__':unittest.main()
