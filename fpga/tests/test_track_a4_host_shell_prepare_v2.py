import unittest
from fpga.reference.track_a4_host_shell_prepare_v2 import check_footer


class HostShellReceiptContract(unittest.TestCase):
    def test_exact_coverage_and_measured_latency_without_fixed_clock_claim(self):
        # Synthetic parser inputs only; these values are not native results.
        prefix='A4_HOST_SHELL_PASS aw=5 commands=155 readbacks=13 errors=5 hold_checks=310 '
        parsed=check_footer(prefix+'ticks=1744 max_latency=100\n')
        self.assertEqual(parsed['measured_command_latency_sum'],1000)
        self.assertEqual(parsed['max_latency'],100)
        for text in (prefix+'ticks=743 max_latency=1\n',prefix+'ticks=1744 max_latency=1001\n',
                     prefix+'ticks=1744 max_latency=100\nextra\n',
                     (prefix+'ticks=1744 max_latency=100\n').replace('commands=155','commands=154')):
            with self.assertRaises(ValueError):check_footer(text)


if __name__=='__main__':unittest.main()
