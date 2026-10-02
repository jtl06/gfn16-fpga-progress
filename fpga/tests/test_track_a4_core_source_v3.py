import itertools
import unittest
from fpga.reference.track_a4_core_source_v3 import ROOT, verify
from fpga.reference.track_a4_registered_schedule_v1 import registered_schedule


class CoreAdmissionRepairTests(unittest.TestCase):
    def test_exact_delta(self):
        result=verify()
        self.assertEqual(result["exact_successors"],3)
        self.assertEqual(result["normal_cycle_delta"],0)

    def test_exhaustive_source_ownership(self):
        states=("IDLE","COLD_START","COLD_WAIT","NTT_START","NTT_WAIT","POST_WAIT","DRAIN","CHECK","FAILED")
        for state,prefill,post,read in itertools.product(states,(False,True),(False,True),(False,True)):
            raw=(prefill and state!="COLD_WAIT") or (post and state!="POST_WAIT") or (read and state not in ("NTT_WAIT","POST_WAIT"))
            admitted_read=read and not raw
            admitted_write=(prefill or post) and not raw
            if prefill and post:
                self.assertTrue(raw)
                self.assertFalse(admitted_read or admitted_write)
            if admitted_write:
                self.assertTrue((prefill and state=="COLD_WAIT" and not post) or (post and state=="POST_WAIT" and not prefill))
            if admitted_read:
                self.assertIn(state,("NTT_WAIT","POST_WAIT"))
            if state in ("DRAIN","CHECK") and (prefill or post or read):
                self.assertTrue(raw)

    def test_late_fault_wins_done_and_cancel(self):
        # Sequential priority in exact guarded source: CHECK may propose done,
        # but raw/registered fault overrides it before the edge commits.
        for raw,registered,cancel in itertools.product((False,True),repeat=3):
            state,done,error="IDLE",True,False
            admission_error=raw
            if raw or registered:state,done,error="FAILED",False,True
            if cancel:state,done,error,admission_error="IDLE",False,False,False
            self.assertEqual(done,not (raw or registered or cancel))
            if cancel:self.assertFalse(error or admission_error)
            elif raw or registered:self.assertEqual(state,"FAILED")
        text=(ROOT/"rtl/kernel/genefer_track_a4_square_backend_v3.sv").read_text()
        self.assertLess(text.index("CHECK:begin"),text.index("if(fault || raw_admission_fault)"))
        self.assertLess(text.index("if(fault || raw_admission_fault)"),text.index("if(cancel)begin admission_error<=0"))

    def test_ordinary_schedule_unchanged(self):
        for aw in (5,8,16):
            s=registered_schedule(1<<aw)
            self.assertEqual(s["ram_to_ram_displacement"],52)
            self.assertEqual(s["internal_post_clocks"],(1<<aw)//16+62)


if __name__ == "__main__":
    unittest.main()
