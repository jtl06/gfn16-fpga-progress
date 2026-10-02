import hashlib
import json
import re
import unittest
from fpga.reference import stream27_montgomery_fused_native as s
from fpga.reference import stream27_montgomery_fused_probe as probe
from fpga.reference import stream27_montgomery_fused_mutants as mutants


class FusedButterflySource(unittest.TestCase):
    def test_sign_successor_is_separate_with_signed29_not_biased_compare(self):
        s.verify(2)
        mutants.verify(2);probe.verify(2)
        self.assertIn('bad_ct_sign_y0',mutants.generated_cpp(2))
        self.assertNotIn('expected.correct_y0',mutants.generated_cpp(2))
        text=s.rtl(2)
        self.assertNotIn('ct_total',text)
        self.assertNotIn('TWO_P30',text)
        self.assertIn('wire signed [28:0] ct_sum=',text)
        self.assertIn("28'(ct_sum<0 ? ct_sum+P29 : ct_sum)",text)
        self.assertEqual(text.count('wire [53:0] low_product=lhs[26:0]*rhs;'),1)
        for p in s.model.FIELDS:
            manifest,files=s.role(p,2)
            self.assertEqual(manifest['build']['sv_sources'],[s.RTL2])
            self.assertEqual(manifest['test_role'],'normal')
            self.assertNotIn(s.RTL,files)
            _,counts=s.donor.corpus(p)
            footer=f'P5_FUSED_SIGN_BFLY_PASS p={p} '+' '.join(f'{k}={v}' for k,v in counts.items())+'\n'
            self.assertEqual(s.validate(footer,'',0,{'p':p,'variant':2},{})['latency'],5)
            with self.assertRaises(ValueError):s.validate(footer,'',0,{'p':p},{})
            deliberate,_=mutants.role(p,2)
            self.assertEqual(deliberate['test_role'],'deliberate_fault')
            self.assertEqual(deliberate['build']['sv_sources'],[mutants.SV2,s.RTL2])
            mutant_footer=footer.replace('BFLY_PASS','MUTANTS_PASS').rstrip()+' detected=15\n'
            self.assertEqual(mutants.validate(mutant_footer,'',0,{'p':p,'variant':2},{})['mutants_detected'],
                ['highbit','ct_sign','gs_bias','latency'])

    def test_deliberate_mutants_are_separate_actual_single_site_copies(self):
        mutants.verify()
        self.assertIn('expected.y0%P',mutants.generated_cpp())
        self.assertNotIn('expected.correct_y0',mutants.generated_cpp())
        self.assertEqual(mutants.generated_sv().count('wire [53:0] low_product=lhs[26:0]*rhs;'),4)
        self.assertEqual(len(mutants.MUTATIONS),4)
        for p in s.model.FIELDS:
            manifest,_=mutants.role(p)
            self.assertEqual(manifest['test_role'],'deliberate_fault')
            self.assertEqual(manifest['build']['sv_sources'],[mutants.SV,s.RTL])
            _,counts=s.donor.corpus(p)
            footer=f'P5_FUSED_MUTANTS_PASS p={p} '+' '.join(f'{k}={v}' for k,v in counts.items())+' detected=15\n'
            self.assertEqual(len(mutants.validate(footer,'',0,{'p':p},{})['mutants_detected']),4)
            with self.assertRaises(ValueError):mutants.validate(footer.replace('detected=15','detected=14'),'',0,{'p':p},{})

    def test_matched_probe_has_three_independent_cells_and_reversible_baseline(self):
        probe.verify()
        old=(s.ROOT/probe.OLD).read_text()
        normalized=probe.normalized_source().replace('genefer_stream27_factored_lazy28_butterfly_v1',
            'genefer_ntt_lazy28_butterfly_v1').replace('genefer_stream27_montgomery28x27_factored_v1',
            'genefer_montgomery_mul28x27_sparse_pipe_v2')
        self.assertEqual(old,normalized)
        for index,name in enumerate(('frozen_butterfly','factored_butterfly','fused_butterfly')):
            self.assertIn(name+'(',probe.TEXT)
            self.assertIn(f'.in_valid(valid_q[{index}])',probe.TEXT)
            self.assertIn(f'.u(u_q[{28*index}+:28])',probe.TEXT)
        self.assertEqual(len(probe.gates()),6)

    def test_private_raw_domain_and_exact_normal_fixture(self):
        s.verify()
        text=s.rtl()
        self.assertEqual(text.count('wire [53:0] low_product=lhs[26:0]*rhs;'),1)
        self.assertNotIn('if(t_hi>=mp_hi)',text)
        self.assertIn('wire signed [29:0] ct_total=',text)
        self.assertIn('output logic signed [27:0] result_raw',text)
        self.assertIn('output logic [27:0] y0,y1',text)
        self.assertIn('out_valid<=product_valid;',text)
        self.assertIn('tag_pipe[0:4]',text)
        self.assertIn('d.y0%P==expected.y0%P',s.cpp())
        self.assertIn('d.y0<2*P&&d.y1<2*P',s.cpp())
        self.assertIn('LAZY_BFLY_INVALID_HOLD',s.cpp())

    def test_closed_normal_roles_and_typed_control_footer(self):
        for p in s.model.FIELDS:
            manifest,files=s.role(p)
            self.assertEqual(manifest['test_role'],'normal')
            self.assertEqual(manifest['build']['sv_sources'],[s.RTL])
            self.assertTrue(all(re.fullmatch('[a-z][a-z0-9-]*',x['name']) for x in manifest['steps']))
            self.assertTrue(all(s.sha(raw)==manifest['sources'][name] for name,raw in files.items()))
            ready=manifest['rtl_readiness'];snapshot=ready['source_snapshot']
            self.assertEqual(ready['candidate_source_sha256'],hashlib.sha256(
                json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()).hexdigest())
            self.assertEqual(snapshot[s.RTL],manifest['sources'][s.RTL])
            _,counts=s.donor.corpus(p)
            footer=f'P5_FUSED_BFLY_PASS p={p} '+' '.join(f'{k}={v}' for k,v in counts.items())+'\n'
            validation=s.validate(footer,'',0,{'p':p},{})
            self.assertEqual((validation['latency'],validation['II']),(5,1))
            for wrong in (footer.replace('checked=4628','checked=4627'),
                          footer.replace('cancelled=204','cancelled=0'),
                          footer.replace('ct=', 'wrong_ct=')):
                with self.assertRaises(ValueError):s.validate(wrong,'',0,{'p':p},{})
            with self.assertRaises(ValueError):s.validate(footer,'',1,{'p':p},{})
            with self.assertRaises(ValueError):s.validate(footer,'unexpected',0,{'p':p},{})


if __name__=='__main__':unittest.main()
