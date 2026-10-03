import unittest
from fpga.reference import stream27_r15_watchdog_native as own


class R15WatchdogNativeTests(unittest.TestCase):
    def test_same_build_positive_and_sensitive_peer_negative(self):
        normal,nfiles=own.role('normal');fault,ffiles=own.role('fault')
        self.assertEqual(nfiles,ffiles)
        self.assertEqual(normal['build'],fault['build'])
        self.assertEqual(fault['steps'][1]['expected_returncode'],1)
        self.assertEqual(fault['steps'][1]['expected_stderr'],'R15_WATCHDOG_CONTEXT_STALL\n')
        self.assertEqual(normal['build']['runtime_threads'],1)
        self.assertFalse(normal['r15_watchdog_component']['whole_host_signal_qualification'])
        cpp=nfiles[own.CPP].decode()
        self.assertIn('H(int a,char**v):c(a,v),d(&c)',cpp)
        self.assertIn('gfn16_runtime::configure(*this,a,v)',cpp)
        self.assertEqual(normal['sources'],{n:own.sha(raw) for n,raw in nfiles.items()})

    def test_invalid_mode(self):
        with self.assertRaises(ValueError):own.role('prp')


if __name__=='__main__':unittest.main()
