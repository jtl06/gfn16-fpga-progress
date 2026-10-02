import hashlib
import copy
import re
import unittest
from fpga.reference import stream27_final_pair_inputreg_native as n
from fpga.reference import stream27_final_pair_inputreg_mutants as m


class FinalPairInputRegister(unittest.TestCase):
    def test_exact_parent_and_complete_single_input_seam(self):
        for name,pin in n.PINS.items():self.assertEqual(hashlib.sha256((n.ROOT/name).read_bytes()).hexdigest(),pin)
        text=(n.ROOT/n.RTL).read_text()
        for member in ('u_q<=u','v_q<=v','lower_root_q<=normalized_lower_root'):
            self.assertIn(member,text)
        self.assertEqual(text.count('genefer_stream27_merged_final_gs_pair_v1 #('),1)
        self.assertIn('.in_valid(input_valid_q)',text)
        self.assertIn('if(!rst_n)input_valid_q<=0;',text)
        self.assertNotIn('genefer_montgomery_mul',text)
        self.assertTrue(n.butterfly().startswith('module genefer_ntt_difdit_butterfly27 #('))
        self.assertEqual(n.butterfly().count('endmodule'),1)

    def test_scalar_precision_domain_and_final_normalization(self):
        for p in n.FIELDS:
            self.assertLess(2*p,1<<28)
            ri=pow(1<<32,-1,p);s=n.scale(p)
            self.assertLess(s,p)
            for u in (0,1,p//2,p-1):
                for v in (0,1,p//2,p-1):
                    for w in (0,1,p-1):
                        total=u+v;fold=total-p if total>=p else total
                        difference=u-v if u>=v else u+p-v
                        self.assertTrue(0<=fold<p and 0<=difference<p)
                        self.assertEqual(fold*s*ri%p,(u+v)*s*ri%p)
                        self.assertEqual(difference*w*ri%p,(u-v)*w*ri%p)
            self.assertEqual(s*ri%p,(1<<32)*pow(256,-1,p)%p)

    def test_edge_reset_ledger_and_static_normal_contract(self):
        c=n.counts();self.assertGreater(c['new_checked'],5000)
        self.assertGreater(c['new_cancelled'],c['old_cancelled'])
        self.assertEqual(c['new_latency']-c['old_latency'],1)
        self.assertEqual(n.contract()['II'],1)
        self.assertEqual(n.contract()['added_variable_products'],0)
        cpp=(n.ROOT/n.CPP).read_text()
        self.assertIn('edge+5+k',cpp)
        self.assertIn('FINAL_PAIR_BIT_EXACT_VALUE',cpp)
        self.assertIn('FINAL_PAIR_BEFORE_EDGE',cpp)
        self.assertIn('FINAL_PAIR_INVALID_HOLD',cpp)
        for p in n.FIELDS:self.assertTrue(n.expected(p).endswith('old_latency=5 new_latency=6\n'))

    def test_test_only_actual_mutations_and_strict_normal_not_weakened(self):
        sv=m.generated_sv();cpp=m.generated_cpp()
        self.assertEqual(len(m.MUTATIONS),5)
        for kind,_,_ in m.MUTATIONS:self.assertIn('mutant_'+kind+'(',sv)
        # Original bad_valid instance collided with the port on native lint.
        ports={'old_valid','new_valid','old_error','new_error','old_y0','old_y1','new_y0','new_y1',
               'bad_valid','bad_error','bad_y0','bad_y1'}
        self.assertFalse(ports & {'mutant_'+kind for kind,_,_ in m.MUTATIONS})
        self.assertIn('FINAL_PAIR_FIVE_REAL_MUTANTS_DETECTED',cpp)
        self.assertIn('FINAL_PAIR_BIT_EXACT_VALUE',cpp)
        self.assertIn('FINAL_PAIR_VALID_E5_E6',cpp)
        self.assertIn('detected==31',cpp)

    def test_role_schema_readiness_and_lowercase_step_names(self):
        gate=(n.ROOT/'tools/native_source_gate_v1.py').read_text()
        self.assertIn("re.fullmatch('[a-z][a-z0-9-]*', n)",gate)
        for p in n.FIELDS:
            role,files=n.role(p)
            self.assertEqual(role['test_role'],'normal')
            for name,pin in role['rtl_readiness']['source_snapshot'].items():
                self.assertTrue(name.endswith('.sv'))
                self.assertEqual(hashlib.sha256(files[name]).hexdigest(),pin)
            for step in role['steps']:
                self.assertIsNotNone(re.fullmatch('[a-z][a-z0-9-]*',step['name']))
            for bad in ('normal-E5','build','probe','normal_value',''):
                broken=copy.deepcopy(role);broken['steps'][0]['name']=bad
                with self.subTest(bad=bad),self.assertRaisesRegex(ValueError,'STEP_GRAMMAR'):
                    n.preflight(broken,files)

    def test_matched_registered_source_sizing_wrapper(self):
        text=(n.ROOT/n.SIZING_SV).read_text()
        self.assertIn('valid_q<=in_valid;',text)
        self.assertIn('u_q[k]<=u[k*28+:28]',text)
        self.assertIn("u_q[k]>=28'(P) ? u_q[k]-28'(P) : u_q[k]",text)
        for k in (0,1):self.assertIn(f'.in_valid(valid_q[{k}])',text)
        cpp=n.sizing_cpp()
        self.assertEqual((n.ROOT/n.SIZING_CPP).read_text(),cpp)
        self.assertIn('edge+6+k',cpp)
        self.assertIn('if(edge%3==0)u+=P;if(edge%5==0)v+=P;',cpp)
        self.assertIn('FINAL_PAIR_BIT_EXACT_VALUE',cpp)
        role,files=n.sizing_role(n.FIELDS[0])
        self.assertEqual(role['build']['top'],n.SIZING_TOP)
        self.assertEqual(role['test_role'],'normal')
        self.assertEqual(n.counts((6,7))['new_latency'],7)
        self.assertEqual(len(role['build']['sv_sources']),5)


if __name__=='__main__':unittest.main()
