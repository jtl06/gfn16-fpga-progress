import random
import unittest
from fpga.reference import stream27_l7_resetfree_mont as l7

class ResetfreeProof(unittest.TestCase):
    def test_literal_only_numeric_reset_delta(self):
        contract=l7.verify()
        self.assertEqual(contract['removed_source_reset_bits'],193)
        self.assertEqual(contract['preserved_valid_reset_bits'],4)
        self.assertEqual(contract['latency'],3)
        self.assertFalse(contract['physical_register_or_LAB_saving_claim'])

    def test_arbitrary_dirty_start_busyreset_firstpostreset(self):
        for p in l7.math.FIELDS:
            for seed in range(8):
                new=l7.Core(p,seed=seed);old=l7.Core(p,reset_payload=True,seed=seed+81)
                rng=random.Random(seed);pending=[]
                for edge in range(1000):
                    rst=edge%31!=0;valid=rng.randrange(4)!=0
                    lhs=rng.randrange(2*p);rhs=rng.randrange(p)
                    if not rst:pending=[]
                    elif valid:pending.append((edge+3,l7.math.multiply(lhs,rhs,p,lazy=True)))
                    a=new.tick(rst,valid,lhs,rhs);b=old.tick(rst,valid,lhs,rhs)
                    due=bool(pending and pending[0][0]==edge)
                    self.assertEqual(a[0],due);self.assertEqual(b[0],due)
                    if due:self.assertEqual(a[1],pending[0][1]);self.assertEqual(b[1],pending.pop(0)[1])
                    if not rst:self.assertFalse(a[0]);self.assertEqual(b[1],0)

    def test_payload_retains_but_validity_does_not(self):
        state=l7.Core(104857601,seed=53)
        before=dict(state.data);self.assertEqual(state.tick(False,True,1,2),(False,before['result']))
        self.assertEqual(state.data,before)
        for edge in range(4):
            valid,result=state.tick(True,edge==0,123,456)
            self.assertEqual(valid,edge==3)
            if valid:self.assertEqual(result,l7.math.multiply(123,456,state.p,lazy=True))

    def test_bound_field_changes_only_leaf_and_consumer_identifiers(self):
        from fpga.reference import stream27_timing_field_native as normal
        pin='ee144c0fdd5c84f58cb0ca392eccb472878978cc029992608fb95b69e9dd0414'
        for field in range(3):
            before=normal.field_bundle(8,16,field,pin);after=l7.bind(before)
            self.assertEqual(before['geometry'],after['geometry'])
            self.assertEqual(before['parameters'],after['parameters'])
            reverse={v:k for k,v in l7.NAMES.items()}
            for name,text in before['files'].items():
                if name==l7.Path(l7.PARENT).name:continue
                self.assertEqual(l7.identifiers(after['files'][name],reverse),text)
            self.assertEqual(l7.bind(before,enabled=0),before)
            manifest,files=l7.field_role(8,16,field,pin,'2026-10-01T23:13:29Z')
            self.assertIn('lineage/'+l7.SELF,files)
            self.assertIn('rtl/'+l7.Path(l7.RTL).name,manifest['build']['sv_sources'])
            self.assertEqual(manifest['rtl_readiness']['rtl_ready_at_utc'],l7.RTL_READY)
            self.assertFalse(manifest['r75_field']['full_N_numeric_locally_performed'])

    def test_typed_normal_and_fault_contracts_reject_counter_mutation(self):
        for p in l7.math.FIELDS:
            good=f'PASS_L7_RESETFREE P={p} checked=16925 canceled=224 holds=3166 edges=20091 outputs=4 latency=3 ii=1 dirty_reset_retention=true\n'
            l7.validate(good,'',0,dict(p=p),{})
            with self.assertRaisesRegex(ValueError,'TYPED_RESULT'):
                l7.validate(good.replace('canceled=224','canceled=0'),'',0,dict(p=p),{})
            faults=good.replace('PASS_L7_RESETFREE','PASS_L7_RESETFREE_MUTANTS').replace(' edges=',' detected=31 edges=')
            l7.validate_mutants(faults,'',0,dict(p=p),{})
            with self.assertRaisesRegex(ValueError,'MUTANT_TYPED_RESULT'):
                l7.validate_mutants(faults.replace('detected=31','detected=30'),'',0,dict(p=p),{})

if __name__=='__main__':unittest.main()
