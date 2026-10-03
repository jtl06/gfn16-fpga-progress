import unittest
from fpga.reference import stream27_r15_shell_application_full_native as own


class R15FullApplicationNativeTests(unittest.TestCase):
    def test_full_literal70_remote_reference_and_no_transport_free_claim(self):
        m,f,b=own.role()
        self.assertEqual(len(b['files']),70)
        self.assertEqual(len(m['build']['sv_sources']),71)
        self.assertEqual(m['build']['parameters']['EPOCH_SEED0'],0)
        self.assertEqual(m['build']['parameters']['EPOCH_SEED1'],0)
        self.assertIn('EPOCHS[2]={0,0}',f[own.HEADER].decode())
        cpp=f[own.CPP].decode()
        self.assertIn('s4_full_reference::square',cpp)
        self.assertIn('BITS[c][0]?4u:0u',cpp)
        self.assertIn('for(unsigned i=0;i<8;i++)d.cold_writedata[i]=0;',cpp)
        self.assertNotIn('C0[c]',cpp)
        self.assertIn(own.FOOTER.rstrip('\n'),cpp)
        self.assertFalse(m['r15_shell_application_native']['context_alone_identity_claim'])
        self.assertEqual(m['sources'],{n:own.sha(v) for n,v in f.items()})

    def test_full_typed_result_has_exact_finite_scope(self):
        self.assertEqual(own.validate(own.FOOTER,'',0,own.config(),{})['status'],'PASS_expected_contracts')
        with self.assertRaises(ValueError):own.validate(own.FOOTER,'',1,own.config(),{})


if __name__=='__main__':unittest.main()
