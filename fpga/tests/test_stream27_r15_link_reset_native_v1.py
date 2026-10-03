import unittest
from fpga.reference import stream27_r15_link_reset_native_v1 as native


class ResetProbeSource(unittest.TestCase):
    def test_literal_leaf_and_source_closure(self):
        m,f=native.role()
        self.assertEqual(f[native.RTL],(native.ROOT/native.RTL).read_bytes())
        self.assertEqual(m['build']['runtime_threads'],1)
        self.assertFalse(m['scope']['outstanding_command_write_drain'])
        self.assertFalse(m['scope']['independent_review'])
        for p,v in f.items():self.assertEqual(native.hashlib.sha256(v).hexdigest(),m['sources'][p])

    def test_two_seeds_and_clock_gaps(self):
        m,f=native.role();probe=f[native.PROBE].decode();cpp=f[native.CPP].decode()
        self.assertEqual(probe.count('genefer_stream27_r15_link_reset_v2 '),2)
        self.assertIn("SESSION_SEED(32'hfffffffe)",probe)
        self.assertIn('gfn16_runtime::configure(context,argc,argv)',cpp)
        self.assertLess(cpp.index('gfn16_runtime::configure'),cpp.index('Vstream27_r15_link_reset_probe d'))
        self.assertIn('own_domain_release=2',m['steps'][0]['expected_stdout'])
        self.assertIn('tick<70',cpp)
        self.assertIn('R15_RESET_SESSION_NOT_ADVANCED_BEFORE_RELEASE',cpp)

    def test_finite_no_wrap_scalar_control(self):
        # Counter update reference only; not execution of RTL/async circuit.
        def advance(s):return (s,True) if s==0xffffffff else (s+1,False)
        normal=0
        for expected in range(1,6):
            normal,exhausted=advance(normal);self.assertEqual(normal,expected);self.assertFalse(exhausted)
        limit,exhausted=advance(0xfffffffe);self.assertEqual(limit,0xffffffff);self.assertFalse(exhausted)
        limit,exhausted=advance(limit);self.assertEqual(limit,0xffffffff);self.assertTrue(exhausted)


if __name__=='__main__':unittest.main()
