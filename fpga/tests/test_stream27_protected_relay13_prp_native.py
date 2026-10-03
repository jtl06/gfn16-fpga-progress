"""Own protected graph/header/validator checks, not a local PRP simulation."""
import json
import unittest
from fpga.reference import stream27_protected_relay13_prp_native as own

class ProtectedRelay13PRPTests(unittest.TestCase):
    def test_captured_source_and_runtime_before_dut(self):
        m,f,b,_=own.role()
        self.assertEqual(len(m['build']['sv_sources']),58)
        self.assertNotIn('LEAN_PRODUCTION',m['build']['parameters'])
        self.assertEqual(m['build']['parameters']['CRT_TRANSPORT_REG'],0)
        self.assertTrue(all(f['rtl/'+n]==text.encode() for n,text in b['files'].items()))
        cpp=f[own.CPP].decode()
        self.assertLess(cpp.index('gfn16_runtime::configure(context,argc,argv)'),cpp.index('DUT d(&context)'))
        header=f[own.HEADER].decode()
        self.assertIn(own.LABEL,header)
        self.assertIn('INTERVAL=218,CARRY_DONE=217',header)
        self.assertIn('FIRST[2]={204,313}',header)

    def test_frozen_all_digit_comparator_controls(self):
        m,f,_,_=own.role(True)
        assets=dict(oracle=f[own.ASSET].decode())
        for step in m['steps']:
            result=own.validate(own.LABEL+'\n','A_PRP_RESIDUE_MISMATCH case=0 digit=0\n',1,
                step['validator']['config'],assets)
            self.assertEqual(result['status'],'PASS_expected_contracts')
            with self.assertRaises(ValueError):
                own.validate(own.LABEL+'\n','',0,step['validator']['config'],assets)

    def test_known_small_oracle_is_full_exponent_and_sentinel(self):
        _,f,_,_=own.role();oracle=json.loads(f[own.ASSET])
        self.assertEqual([r['base'] for r in oracle['cases']],list(own.BASES))
        self.assertEqual(sum(r['steps'] for r in oracle['cases'])+2,41091)
        self.assertTrue(all(len(r['expected_digits'])==256 for r in oracle['cases']))
        self.assertEqual(len(oracle['sentinel']['expected_digits']),256)

if __name__=='__main__':unittest.main()
