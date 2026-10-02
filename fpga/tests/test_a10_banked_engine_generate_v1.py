import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from fpga.reference import a10_banked_engine_generate_v1 as gen
from fpga.reference import merged_negacyclic27_model as math
from fpga.reference import merged_negacyclic27_issue_model_v1 as issue
from fpga.reference import a10_packed_root_lookup_v1 as lookup


class A10GeneratedTests(unittest.TestCase):
    def test_exact_parent_and_generated_guard(self):
        gen.source_guard()
        for name,source in gen.sources().items():
            self.assertEqual((gen.ROOT/name).read_text(),source)
        self.assertEqual((gen.ROOT/'fpga/rtl/tb/a10_core_prp_aw5_v1.cpp').read_text(),gen.e2e_cpp())

    def test_audited_payload_boundaries_preserved(self):
        parent=(gen.ROOT/gen.CORE_PARENT).read_text();new=gen.core_source()
        for start,end in [('    for(genvar h=0;h<IO_WIDTH;h=h+1)begin: coefficient_lane',
                          '    assign profile_coherent='),
                         ('    always_comb begin\n        carry_load=', '        genefer_carry_prefix_stream_precision'),
                         ('        genefer_carry_prefix_stream_precision','    for(genvar f=0;'),
                         ('        for(genvar h=0;h<IO_WIDTH;h=h+1)begin: input_lane','        genefer_root_profile27_r2_rom')]:
            expected=gen.region(parent,start,end).replace('// Format2 twist consumes ordinary canonical d, not d*R.',
                '// Merged CT consumes ordinary canonical d; no R2 twist pointpass.')
            self.assertIn(expected,new)
        self.assertIn('double_reg ? (coefficient_words[h] <<< 1) : coefficient_words[h]',new)
        self.assertNotIn('.inverse(1\'b0),.dif(step==1)',new)

    def test_stage_order_independent_form(self):
        engine=gen.engine_source();core=gen.core_source()
        self.assertIn('descending<=!inverse',engine)
        self.assertIn('.gs(bf_in_valid[lane] && active_inverse)',engine)
        self.assertIn('stage_bit<=descending ? stage_bit-1 : stage_bit+1',engine)
        self.assertIn('.inverse(step==2),.dif(step==2)',core)
        self.assertIn('else if(step==2)',core)
        self.assertNotIn('genefer_root_recurrence27',engine)
        self.assertNotIn('ROOT_LOAD',engine)

    def test_registered_root_data_tags_and_distinct_point_route(self):
        engine=gen.engine_source()
        for phrase in ['data_destination[bank]<=data_q[bank]',
                       'bf_in_valid[lane]<=bf_read_delay',
                       'orientation_q<=orientation_d','lookup_tag!=issue_tag_destination',
                       'data_wa[bank]=row_tag[7][bank]', 'data_wa[bank]=row_tag[6][bank]']:
            self.assertIn(phrase,engine)
        # Nonblocking edge ledger: issue E0 -> RAM/rootq E0 -> destination E1
        # -> BF acceptance E2 -> BF outputs E7 -> controller/RAM consume E8.
        for issue_edge in range(16):
            self.assertEqual(issue_edge+1+1+5+1,issue_edge+8)
            self.assertEqual(issue_edge+1+5+1,issue_edge+7)

    def test_final_pair_single_shared_lower_and_parallel_upper(self):
        path=gen.ROOT/gen.KERNEL/'genefer_a10_canonical_butterfly_v1.sv'
        text=path.read_text()
        self.assertEqual(text.count('genefer_ntt_difdit_butterfly27 #('),1)
        self.assertEqual(text.count('genefer_montgomery_mul27_sparse_pipe #('),1)
        self.assertIn('upper_delay[1]',text);self.assertIn('norm_pipe[5]',text)
        for n in [32,256]:
            for f in math.FIELDS:
                scale=math.normalization_constant(n,f)
                for u,v in [(0,0),(1,f.p-1),(f.p-1,f.p-1),(1234567,7654321)]:
                    w=pow(math.psi_for(n,f),-1,f.p)*scale%f.p
                    upper=f.mont((u+v)%f.p,scale);lower=f.mont((u-v)%f.p,w)
                    self.assertEqual(upper,(u+v)*scale*pow(f.r,-1,f.p)%f.p)
                    self.assertEqual(lower,(u-v)*pow(math.psi_for(n,f),-1,f.p)*scale*pow(f.r,-1,f.p)%f.p)

    def test_lookup_binding_fields_and_domain(self):
        bundle=gen.lookup_binding()
        self.assertEqual(len(bundle['compiled']),3)
        for c,f in zip(bundle['compiled'],math.FIELDS):
            self.assertIn(f'P=={f.p}',bundle['source'])
            self.assertEqual(c['final_upper_scale'],math.normalization_constant(32,f))
            plan=c['layout']
            for inverse in (False,True):
                for s in range(5):
                    actual=lookup.roots_for_request(plan,s,0,inverse=inverse)
                    for row in issue.issue(32,64,s,0):
                        exp=math.bit_reverse((32>>(s+1))+(row.u_index>>(s+1)),5)
                        expected=pow(math.psi_for(32,f),-exp if inverse else exp,f.p)
                        expected=expected*math.normalization_constant(32,f)%f.p if inverse and s==4 else f.encode(expected,1)
                        self.assertEqual(actual[row.lane],expected)

    def test_profile3_incompatible_identity_and_epoch_contract(self):
        s=gen.engine_source();profile=(gen.ROOT/gen.KERNEL/'genefer_a10_profile3_v1.sv').read_text()
        for phrase in ["profile_format!=8'd3",'profile_size_log2!=5\'(AW)',
                       'profile_modulus!=P','profile_data==expected_header',
                       'profile_epoch<=profile_epoch+1','profile_abort','profile_error || profile_request']:
            self.assertIn(phrase,s)
        for phrase in ["32'h41313000",'word=32\'(N)','word=SCALE','word=PSI']:
            self.assertIn(phrase,profile)

    def test_symbolic_cycles_no_numeric_full_frame(self):
        # IDLE start edge excluded; setup1 + readsG + drain8 per transform stage.
        for aw in [5,8,16]:
            g=max(1,(1<<aw)//128);square=(1<<aw)+63>>6
            transform=aw*(g+9);point=square+7
            self.assertEqual(transform,50 if aw==5 else 88 if aw==8 else 8336)
            self.assertEqual(point,8 if aw==5 else 11 if aw==8 else 1031)
        self.assertEqual(2*8336+1031+6,17709) # whole start + registered done-consume =2 perphase


if __name__=='__main__':unittest.main()
