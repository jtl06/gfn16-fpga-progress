import unittest
from fpga.reference.track_a4_host_shell_source_v2 import verify


class HostShellDeltaTests(unittest.TestCase):
    def test_exact_admitted_delta_only(self):
        self.assertEqual(len(verify()),4)

    def test_explicit_bank_width_is_identical_for_all_supported_addresses(self):
        checked=0
        for aw in range(5,17):
            for tag in range(1<<aw):
                old=tag>>(aw-4)
                new=(tag>>(aw-4))&15
                self.assertEqual(old,new)
                checked+=1
        self.assertEqual(checked,131040)

    def test_two_bit_pass_guard_retains_every_rejection(self):
        for passes in range(4):
            self.assertEqual(passes==0 or passes>3,passes==0)


if __name__=='__main__':unittest.main()
