import unittest
from fpga.reference import anext_cold_legality_prepare_v1 as p
class ColdLegalityLadder(unittest.TestCase):
    def test_frozen_normal_values_and_new_fault_source_closure(self):
        for aw in (5,8):
            for kind in ('normal','fault'):
                m,f=p.role(aw,kind)
                self.assertEqual(len(m['build']['sv_sources']),30)
                self.assertTrue(set(m['build']['sv_sources']+[m['build']['cpp_source']])<=f.keys())
                self.assertNotIn(p.s.PARENT,m['build']['sv_sources'])
                self.assertEqual(m['cold_legality']['contract']['warm_cycle_delta'],0)
                self.assertEqual(m['cold_legality']['contract']['normal_cold_cycle_delta'],0)
    def test_actual_source_check_observers_and_fullclock_cancel(self):
        e=p.fault.expected();top=e[p.fault.SV];back=e[p.fault.BACK]
        self.assertIn('capture_valid[1]',top);self.assertIn('destination_tag==sim_fault_offset',top)
        self.assertIn('ram_write_en',top);self.assertIn('.cancel(square_cancel || sim_cancel)',top)
        self.assertIn('transfers.request_write',top)
        self.assertIn('sim_fault_mode==2',back);self.assertIn('sim_fault_mode==3',back);self.assertIn('sim_fault_mode==4',back)
        self.assertNotIn('force ',top);self.assertNotIn('release ',top)
    def test_typed_edge_and_recovery_reject_corrupt_contract(self):
        for aw in (5,8):
            for c in p.fault.CASES:
                delta=int(c in ('numeric-first','numeric-final','upper33-final','cancel-after-source'))
                n=1<<aw;g=max(1,n//128);ntt=2*aw*(g+10)+(n+63)//64+15
                out=f'COLDLEG_FAULT_PASS aw={aw} case={c} fields=3 raw_delta={delta} invalid_reducer=0 invalid_ram=0 quiet=16 reload_words={n} recovery_ntt={ntt} ticks=10000\n'
                self.assertEqual(p.fault.validate(out,'',0,dict(aw=aw,case=c),{})['status'],'PASS_expected_contracts')
                for bad in (out.replace('invalid_ram=0','invalid_ram=1'),out.replace(f'raw_delta={delta}',f'raw_delta={1-delta}'),out+'extra\n'):
                    with self.assertRaises(ValueError):p.fault.validate(bad,'',0,dict(aw=aw,case=c),{})
        self.assertEqual(p.fault.validate('','COLDLEG_NUMERIC_EDGE_CONTRACT\n',1,dict(aw=5,case='negative-edge'),{})['status'],'PASS_expected_contracts')
if __name__=='__main__':unittest.main()
