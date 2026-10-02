import unittest
from fpga.reference.track_a4_registered_schedule_v1 import registered_schedule


class RegisteredScheduleTests(unittest.TestCase):
    def test_exact_budget_and_ports(self):
        for aw in range(5,17):
            n=1<<aw
            s=registered_schedule(n)
            t=n//16
            self.assertEqual(len(s["read_edges"]),t)
            self.assertEqual(len(s["write_edges"]),t+2)
            self.assertEqual(s["internal_post_clocks"],t+62)
            self.assertEqual(s["post_through_backend_done_clocks"],t+65)
            self.assertEqual(s["same_address_collisions"],0)
            self.assertEqual(s["ram_to_ram_displacement"],52)
            self.assertEqual(s["boundary_commit_edge"]+1,s["patch_launch_edge"])
        s=registered_schedule()
        self.assertEqual(s["warm_backend_cycles"],24720)
        self.assertEqual(s["warm_host_latency"],24722)
        self.assertEqual(s["cold_backend_penalty"],4108)

    def test_register_tokens_and_cancel(self):
        # Independent simultaneous register updates: two forward stages, one
        # RAM output, two return stages. Caller consumes at E5, not E4.
        for cancelled in (None,0,1,2,3,4):
            source=destination=ram=return_source=return_destination=None
            got=[]
            for edge in range(9):
                token=(7,0x5a5a,1234) if edge==0 else None
                if cancelled is not None and edge>=cancelled:
                    source=destination=ram=return_source=return_destination=None
                    continue
                if return_destination is not None:got.append((edge,return_destination))
                source,destination,ram,return_source,return_destination=(token,source,destination,ram,return_source)
            self.assertEqual(got,[(5,(7,0x5a5a,1234))] if cancelled is None else [])


if __name__ == "__main__":
    unittest.main()
