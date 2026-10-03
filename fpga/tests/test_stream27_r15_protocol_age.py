import unittest
from fpga.reference import stream27_r15_protocol_age_model as model
from fpga.reference import stream27_r15_protocol_age_bind as binder


class ProtocolAge(unittest.TestCase):
    def test_modular_induction_and_random_table(self):
        p=model.prove();self.assertEqual(p['bounded_edges'],20000)
        self.assertEqual(p['reduced_width_identity_checks'],131072)
        self.assertFalse(p['native_RTL'])

    def test_off_by_one_and_stop_mutants(self):
        t=model.Ages(79,153,cycle=model.MASK)
        with self.assertRaises(ValueError):t.edge(allocate=0,allocation_offset=0)
        t=model.Ages(79,153,cycle=model.MASK);t.edge(allocate=0)
        with self.assertRaises(ValueError):t.edge(stop=True,freeze_on_stop=True)

    def test_reset_reuse_retire_and_wrap(self):
        t=model.Ages(79,153,cycle=model.MASK-1);t.edge(allocate=0)
        t.edge(allocate=1,retire=0);self.assertFalse(t.banks[0].valid)
        t.elapsed((1<<32)*3+7);t.edge(stop=True,retire=1)
        self.assertTrue(t.banks[1].valid)  # STOP cancels raw retirement too
        t.edge(retire=1);self.assertFalse(t.banks[1].valid)
        t.edge(allocate=0);t.edge(reset=True);self.assertFalse(any(b.valid for b in t.banks))
        t.edge(allocate=0);self.assertTrue(t.check())

    def test_off_literal_and_private_closure_both_sizes(self):
        for n in (256,65536):
            old=binder.capture(n);self.assertEqual(binder.prepare(n),old)
            new=binder.prepare(n,1)
            self.assertEqual(len(new['files']),60)
            self.assertEqual(new['geometry'],old['geometry'])
            self.assertEqual(new['r15_protocol_age']['latency_delta'],0)
            self.assertEqual(len(new['r15_protocol_age']['modified']),7)
            self.assertFalse(new['r15_protocol_age']['native_qualified'])
            self.assertIn(binder.PRIVATE_LEAF,new['files'])
            self.assertIn('parameter bit EPOCH_AGE_REG=0',new['files'][binder.PRIVATE_LEAF])
            for name,body in new['files'].items():
                if name in new['r15_protocol_age']['modified'] and name!=binder.PRIVATE_LEAF:
                    self.assertIn('CONTEXTS=2,EPOCH_AGE_REG=0,',body)
                    self.assertIn('.EPOCH_AGE_REG(EPOCH_AGE_REG)',body)

    def test_checks_and_retirement_byte_literal(self):
        old=binder.capture(65536)['files'][binder.LEAF]
        new,_=binder.leaf(old)
        for begin,end in ((' always_comb begin: protocol_checks',' always_ff @(posedge clk or negedge rst_n)'),
                          (' always_ff @(posedge clk or negedge rst_n)',' // synthesis translate_off\n always @(negedge clk)')):
            original=old[old.index(begin):old.index(end,old.index(begin)+1)]
            self.assertIn(original,new)
        self.assertIn("if(valid[i])begin\n    pw_age_q",new)
        self.assertNotIn('if(valid[i] && !stop)',new)

    def test_own_native_headers_wrapper_and_all60_pins(self):
        from fpga.reference import stream27_r15_protocol_age_native as native
        for stage in ('aw8','full'):
            m,f,b=native.role(stage)
            self.assertEqual(len(b['files']),60)
            for name,pin in b['generated_sha256'].items():self.assertEqual(binder.sha(f['rtl/'+name]),pin)
            self.assertEqual(m['build']['parameters']['EPOCH_AGE_REG'],1)
            self.assertFalse(m['r15_protocol_age']['promotion_allowed'])
            self.assertEqual(len(m['build']['sv_sources']),60 if stage=='aw8' else 61)
            if stage=='full':
                text=f['rtl/'+m['build']['top']+'.sv'].decode()
                self.assertIn('.EPOCH_AGE_REG(EPOCH_AGE_REG)',text)
                self.assertEqual(m['steps'][0]['validator']['source'],native.SELF)


if __name__=='__main__':unittest.main()
