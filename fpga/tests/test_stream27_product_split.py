import random
import unittest
from fpga.reference import stream27_product_split as s
from fpga.reference import stream27_product_split_native as native

class ProductSplitTests(unittest.TestCase):
    def test_reverse_exact_parent(self):
        proof=s.verify_source();self.assertEqual(proof['latency'],3);self.assertFalse(proof['mapping_or_savings_claim'])
    def test_scalar_identity_and_independent_oracle(self):
        rng=random.Random(0x6a09e667)
        for p in s.model.FIELDS:
            cases=[(x,y) for x in (0,1,p-1,p,2*p-1,(1<<27)-1,1<<27) for y in (0,1,31,32,p-1)]
            cases += [(rng.randrange(2*p),rng.randrange(p)) for _ in range(30000)]
            inverse=pow(1<<32,-1,p)
            for x,y in cases:
                lo,hi=s.reconstruct(x,y,p)
                self.assertEqual(lo+(hi<<32),x*y)
                self.assertEqual(s.multiply(x,y,p),(x*y*inverse)%p)
    def test_overlap_carry_is_required(self):
        witnessed=0
        rng=random.Random(731)
        for p in s.model.FIELDS:
            for _ in range(1000):
                x,y=rng.randrange(1<<27,2*p),rng.randrange(p);product=(x&((1<<27)-1))*y
                overlap=((product>>27)&31)+(y&31)
                if overlap>=32:
                    lo,hi=s.reconstruct(x,y,p);self.assertNotEqual(lo+((hi-1)<<32),x*y);witnessed+=1;break
        self.assertGreater(witnessed,0)
    def test_native_contract_and_independent_fixture(self):
        for field,p in enumerate(s.model.FIELDS):
            m,files=native.role(field)
            self.assertEqual(m['build']['parameters']['P'],p)
            self.assertEqual(m['steps'][0]['expected_returncode'],0)
            self.assertIn('const uint64_t canonical=uint64_t(lhs)*rhs%P;',files[native.CPP].decode())
            self.assertIn('due?15:0',files[native.CPP].decode())
            self.assertIn('genefer_stream27_product_split_lazy_v1',files[native.PAIR].decode())
            self.assertIn('genefer_stream27_montgomery28x27_factored_v1',files[native.PAIR].decode())
    def test_explicit_nonblocking_replay(self):
        # k acceptance -> k+3 output. Old stage state drives this edge,
        # including canceled occupancy and held outputs during invalid edges.
        rng=random.Random(919)
        for p in s.model.FIELDS:
            valid=[0,0,0];product=high_rhs=t_stage2=q_stage3=held=0;queue=[]
            for edge in range(2004):
                reset=edge%31!=0;accept=edge<2000 and edge%7!=6
                x,y=rng.randrange(2*p),rng.randrange(p)
                if not reset:
                    valid=[0,0,0];product=high_rhs=t_stage2=q_stage3=held=0;queue=[];continue
                if accept:queue.append((edge+3,(x*y*pow(1<<32,-1,p))%p))
                out=bool(valid[2])
                if out:held=q_stage3
                due=bool(queue and queue[0][0]==edge)
                self.assertEqual(out,due)
                if due:self.assertEqual(held,queue.pop(0)[1])
                new_q=s.model.reduce_product(t_stage2,p) if valid[1] else q_stage3
                overlap=((product>>27)&31)+(high_rhs&31)
                new_t=((product&((1<<27)-1))|((overlap&31)<<27))+((product>>32)+(high_rhs>>5)+(overlap>>5))*(1<<32) if valid[0] else t_stage2
                if accept:product=(x&((1<<27)-1))*y;high_rhs=y if x>>27 else 0
                valid=[int(accept),valid[0],valid[1]];t_stage2=new_t;q_stage3=new_q
    def test_zero_binding_and_probe_independence(self):
        from fpga.reference import stream27_product_split_probe as probe
        b={'files':{'caller.sv':'module untouched; endmodule'},'other':[1,2]}
        self.assertEqual(s.bind(b,enabled=0),b)
        self.assertIsNot(s.bind(b,enabled=0),b)
        text=probe.wrapper()
        self.assertEqual(text.count('.in_valid(valid_q['),4)
        self.assertIn('lhs_q[0+:32]',text);self.assertIn('lhs_q[96+:28]',text)
        self.assertNotIn('genefer_montgomery_mul27_sparse_pipe',text)
    def test_typed_carry_fault_exact_one_site(self):
        normal,n=native.role(0);fault,f=native.role(0,mutant=True)
        changed=[key for key in n if n[key]!=f[key]]
        self.assertEqual(changed,[s.RTL])
        self.assertEqual(fault['steps'][0]['expected_stderr'],'MONT28_ARITHMETIC_MISMATCH edge=35\n')
        self.assertEqual(fault['steps'][0]['expected_returncode'],1)
    def test_invalid_inputs_fail(self):
        p=next(iter(s.model.FIELDS))
        for x,y in ((-1,0),(2*p,0),(0,p),(True,0)):
            with self.assertRaises(ValueError):s.reconstruct(x,y,p)
        with self.assertRaises(ValueError):s.bind({},enabled=True)
    def test_private_lazy_only_field_binding(self):
        from fpga.reference import stream27_shared_field_flags as core
        from fpga.reference import stream27_product_split_field as field
        for aw in (8,16):
            parent=core.prepare(1<<aw,16,0,mode='warm',contexts=1,allow_full_constants=aw==16,
                corr_serial_bfs=2,comm_stage_shared_mlab=1,mont_factored=1)
            self.assertEqual(s.bind(parent,enabled=0),parent)
            candidate=s.bind(parent,enabled=1)
            self.assertEqual(candidate['geometry'],parent['geometry'])
            self.assertEqual(candidate['parameters'],parent['parameters'])
            self.assertEqual(candidate['files']['genefer_stream27_montgomery_factored_v1.sv'],parent['files']['genefer_stream27_montgomery_factored_v1.sv'])
            for n,text in parent['files'].items():
                if n in candidate['product_split']['changed_consumers']:
                    self.assertEqual(candidate['files'][n].replace(s.NAMES['genefer_stream27_montgomery28x27_factored_v1'],
                        'genefer_stream27_montgomery28x27_factored_v1'),text)
                else:self.assertEqual(candidate['files'][n],text)
            m,files=field.role(aw);self.assertEqual(m['product_split_field']['counts']['physical_words'],9*(1<<aw))
            self.assertFalse(m['product_split_field']['full_N_numeric_locally_performed'])
    def test_field_fault_rejects_nontyped_outcomes(self):
        from fpga.reference.stream27_product_split_field_fault import validate
        self.assertEqual(validate('','S4_DATA case=1 tick=123 lane=0 expected=3 actual=4\n',1,{}, {})['status'],'PASS_expected_contracts')
        for rc,out,err in ((0,'',''),(-6,'','S4_DATA case=1 tick=123 lane=0 expected=3 actual=4\n'),
            (1,'noise','S4_DATA case=1 tick=123 lane=0 expected=3 actual=4\n'),(1,'','build failure\n'),
            (1,'','S4_DATA case=1 tick=123 lane=0 expected=3 actual=3\n')):
            with self.assertRaises(ValueError):validate(out,err,rc,{}, {})

if __name__=='__main__':unittest.main()
