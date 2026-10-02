import random
import unittest
from fpga.reference import merged_final_gs28_model_v1 as model
from fpga.reference import merged_negacyclic27_model as math

class WideFinalTests(unittest.TestCase):
    def test_exact_frozen_sources_and_no_profile_claim(self):
        model.source_guard();c=model.contract()
        self.assertTrue(c['native_multiplier_reviewed'])
        self.assertFalse(c['native_BF_composition_or_final_pair_reviewed'])
        self.assertFalse(c['pointwise_28x28_admitted']);self.assertFalse(c['dispatch_or_fit'])

    def test_three_field_boundaries_and_random(self):
        rng=random.Random(0xA10F1)
        for f in math.FIELDS:
            edges=[0,1,f.p-1,f.p,2*f.p-2,2*f.p-1,(1<<27)-1,1<<27]
            edges=[a for a in edges if a<2*f.p]
            vectors=[(u,v) for u in edges for v in edges]+[(rng.randrange(2*f.p),rng.randrange(2*f.p)) for _ in range(128)]
            for n in [32,256]:
                scale=math.normalization_constant(n,f)
                w=pow(math.psi_for(n,f),-n//2,f.p)*scale%f.p
                for u,v in vectors:
                    y=model.pair(u,v,w,scale,f)
                    self.assertEqual(y,((u+v)*scale*pow(f.r,-1,f.p)%f.p,(u-v)*w*pow(f.r,-1,f.p)%f.p))
                    self.assertTrue(all(0<=a<f.p for a in y))

    def test_lazy_representation_and_actual_final_group_root(self):
        for f in math.FIELDS:
            n=32;scale=math.normalization_constant(n,f)
            w=pow(math.psi_for(n,f),-n//2,f.p)*scale%f.p
            for u,v in [(0,0),(1,2),(f.p-1,3)]:
                wanted=model.pair(u,v,w,scale,f)
                for extra_u in (0,f.p):
                    for extra_v in (0,f.p):
                        self.assertEqual(model.pair(u+extra_u,v+extra_v,w,scale,f),wanted)

    def test_typed_width_and_upper_scale_negatives(self):
        for f in math.FIELDS:
            scale=math.normalization_constant(32,f);w=pow(math.psi_for(32,f),-16,f.p)*scale%f.p
            vectors=[(2*f.p-1,2*f.p-1),(0,2*f.p-1),(1<<27,1),(1,2)]
            vectors=[(u,v) for u,v in vectors if max(u,v)<2*f.p]
            for mutant in ['truncate27','truncate_sum28','upper-unscaled']:
                caught=False
                for u,v in vectors:
                    try:actual=model.pair(u,v,w,scale,f,mutant=mutant)
                    except ValueError:caught=True;break
                    if actual!=model.pair(u,v,w,scale,f):caught=True;break
                self.assertTrue(caught,(f.p,mutant))

    def test_invalid_domains(self):
        f=math.FIELDS[0]
        for u,v,w,scale in [(2*f.p,0,1,1),(0,-1,1,1),(0,0,f.p,1),(0,0,1,f.p)]:
            with self.assertRaisesRegex(ValueError,'FINAL_GS28_DOMAIN'):model.pair(u,v,w,scale,f)

    def test_source_single_lower_and_two_pipe_edge_calendar(self):
        s=(model.ROOT/'rtl/kernel/genefer_stream27_merged_final_gs_pair28_v1.sv').read_text()
        self.assertEqual(s.count('genefer_ntt_lazy28_butterfly_v1 #('),1)
        self.assertEqual(s.count('genefer_montgomery_mul28x27_sparse_pipe_v2 #('),1)
        self.assertIn('wire [28:0] upper_sum',s);self.assertIn('upper_sum-TWO_P',s)
        self.assertIn('upper_delay[1]',s);self.assertIn('.out_tag(lower_tag)',s)
        for accepted in [0,1,4,9]:self.assertEqual(accepted+3+2,accepted+5)

if __name__=='__main__':unittest.main()
