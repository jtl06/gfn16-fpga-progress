import unittest
import re
from fpga.reference import stream27_r15_canonical_foldstage_bind as b

class FoldstageSourceTests(unittest.TestCase):
    def test_sampled_internal_diagnostic_same_rtl_and_strict_tokens(self):
        from fpga.reference import stream27_r15_canonical_foldstage_internal_v3_native as diagnostic
        from fpga.reference import stream27_r15_canonical_foldstage_native as native
        for aw in (8,16):
            m,files=diagnostic.role(aw);old,_=native.role(aw,'normal')
            self.assertEqual({k:v for k,v in m['sources'].items() if k.endswith('.sv')},
                             {k:v for k,v in old['sources'].items() if k.endswith('.sv')})
            self.assertTrue(all(re.fullmatch('[a-z][a-z0-9-]*',s['name']) for s in m['steps']))
            cpp=files[diagnostic.CPP].decode()
            self.assertLess(cpp.index('OLD(correction0)[0]='),cpp.index('h.edge();need(OLD(state)==2'))
            self.assertIn('NEW(value)==expected_value',cpp)
            self.assertIn('FOLDSTAGE_INTERNAL_FOLD_TOKEN',cpp)
            self.assertIn('FOLDSTAGE_INTERNAL_TRACE',cpp)
    def test_internal_manifest_step_grammar_and_same_production(self):
        from fpga.reference import stream27_r15_canonical_foldstage_internal_native as diagnostic
        from fpga.reference import stream27_r15_canonical_foldstage_native as native
        for aw in (8,16):
            m,files,_=diagnostic.role(aw)
            self.assertTrue(all(re.fullmatch('[a-z][a-z0-9-]*',s['name']) for s in m['steps']))
            old,_=native.role(aw,'normal')
            self.assertEqual({k:v for k,v in m['sources'].items() if k.endswith('.sv')},
                             {k:v for k,v in old['sources'].items() if k.endswith('.sv')})
    def test_default_reverse_and_registered_operand(self):
        old=b.parent();new=b.bind_leaf(old,enabled=1)
        self.assertEqual(b.bind_leaf(old,enabled=0),old)
        self.assertEqual(b.reverse_leaf(new),old)
        region=new[new.index('// FOLD consumes'):new.index('fold_q=fold_q_payload;')]
        self.assertNotIn('value_next',region)
        self.assertIn('value>=two_base',region)
        self.assertIn('state<=FOLD_WORD;',new)
    def test_literal_authority_and_RAM(self):
        old=b.parent();new=b.bind_leaf(old,enabled=1)
        for start,end in [('    always_comb begin\n        load_bad=0;',
                           '    // The supported profile'),
                          ('    for(genvar b=0;b<P;b=b+1)begin: image_banks',
                           '    // A single accepted begin'),
                          ('                PROCESS_WORD:begin','                default:;')]:
            self.assertEqual(old[old.index(start):old.index(end)],new[new.index(start):new.index(end)])
    def test_width_extrema_and_latency_model(self):
        for base in (599,600,131077,604832956,999999937,1000000000):
            for v in (-2*base-1,-2*base,-base-1,-base,-1,0,base-1,base,2*base,3*base-1,3*base):
                q=2 if v>=2*base else 1 if v>=base else 0 if v>=0 else -1 if v>=-base else -2
                r=v-q*base
                bad=v < -2*base or v>=3*base or r<0 or r>=base
                self.assertEqual(bad,not(-2*base<=v<3*base))
                self.assertLess(abs(v),1<<33)
        for n in (256,65536):
            for special in (False,True):
                self.assertEqual(b.service(n,special,1)-b.service(n,special,0),3*n)

if __name__=='__main__':unittest.main()
