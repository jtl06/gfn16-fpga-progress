import unittest
from fpga.reference.stream27_host_chain_calendar_v1 import check


class Calendar(unittest.TestCase):
    def test_all_supported_event_geometries_wrap(self):
        for p in (8,16):
            for aw in range(5,17):
                proof=check(1<<aw,p)
                self.assertEqual(proof['witnesses'],72)
                self.assertLess(proof['maximum_job_cycles'],1<<64)
                self.assertLess(proof['lease_horizon'],1<<31)

    def test_full_prp_crosses_calendar_not_counter_width(self):
        for p in (8,16):
            proof=check(65536,p)
            self.assertGreater(proof['maximum_job_cycles'],1<<32)
            self.assertFalse('native'==proof['scope'])


if __name__=='__main__':unittest.main()
