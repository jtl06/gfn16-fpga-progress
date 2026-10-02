import copy
import unittest
from fpga.reference import stream27_p16_timing_flags as timing

FLAGS=dict(boundary_inputreg=1,descriptor_fifo_ff=1,quarantine_replicas=1,
           final_gs_inputreg=1,canonical_localbase=1,carry_localbase=1)


class SourceTests(unittest.TestCase):
    def test_zero_exact_diet_bundle(self):
        for n in (32,256):
            self.assertEqual(timing.prepare(n),timing.donor.prepare(n))

    def test_explicit_small_frontend_and_feedback(self):
        for n,delay,interval,digit,tail,cache,feedback in (
                (32,41,163,158,163,76,4),(256,8,214,195,214,78,18)):
            b=timing.prepare(n,**FLAGS)
            g=b['geometry']
            self.assertEqual(tuple(g[k] for k in ('input_delay','warm_interval','first_digit','carry_done',
                'correction_cache_latency','feedback_delay')),(delay,interval,digit,tail,cache,feedback))
            self.assertEqual(g['cache_margin'],0)
            roots=[text for name,text in b['files'].items() if name.startswith('genefer_stream27_shared_warm_')]
            for text in roots:
                self.assertIn(f'logic [{delay-1}:0] front_valid;',text)
                self.assertIn(f'd<{delay};',text)
            warm=next(text for name,text in b['files'].items() if name.startswith('genefer_stream27_warm_chain_'))
            self.assertIn(f'logic [{feedback-1}:0] fifo_valid,fifo_start',warm)

    def test_private_factored_final_pair_and_nonfield_leaf_preservation(self):
        before=timing.donor.prepare(32)
        after=timing.bind(before,**FLAGS)
        for name in timing.donor.fitted.PRESERVED:
            self.assertEqual(after['files'][name],before['files'][name])
        name='genefer_stream27_merged_final_gs_pair_v1_p16_diet_v1.sv'
        self.assertEqual(after['files'][name],before['files'][name])
        wrapper='genefer_stream27_merged_final_gs_pair_inputreg_v1_p16_diet_v1.sv'
        self.assertIn(name[:-3]+' #(',after['files'][wrapper])
        self.assertIn('genefer_stream27_montgomery_factored_v1 #(',after['files'][name])
        for filename,text in after['files'].items():
            if 'merged_gs_' in filename:
                last=text[text.index(' if(1)begin: stage4\n'):]
                self.assertEqual(last.count(wrapper[:-3]+' #('),8)
                self.assertIn('generation_pipe[0:6]',last)
                self.assertIn('slot_pipe[6]',last)

    def test_fixed_p16_carry_is_deliberate_generic_binding(self):
        before=timing.donor.prepare(32)
        after=timing.bind(before,**FLAGS)
        calls=[text for text in after['files'].values() if 'blockcarry_lane_localbase_v1 #(.AW(AW),.P(P)) carry (' in text]
        self.assertEqual(len(calls),1)
        self.assertIn('genefer_stream27_blockcarry_lane_localbase_v1 #(.AW(AW),.P(P)) carry (',calls[0])
        self.assertNotIn('genefer_track_a4_blockcarry_lane_v1.sv',after['files'])
        self.assertEqual(after['files']['genefer_track_a4_setup_v1.sv'],before['files']['genefer_track_a4_setup_v1.sv'])

    def test_pair_contains_exact_standalone_and_full_scalar_calendar(self):
        standalone=timing.prepare(256,**FLAGS);paired=timing.prepare(256,paired=True,**FLAGS)
        self.assertTrue(all(paired['files'].get(name)==text for name,text in standalone['files'].items()))
        self.assertEqual(len(paired['files'])-len(standalone['files']),11)
        g=timing.fields.parent.geometry(65536,16,corr_serial_bfs=2)
        new=timing.timing.inverse_geometry(timing.fields.boundary_geometry(g,allow_recalendar=True))
        self.assertEqual(tuple(new[k] for k in ('pointwise_accept','sink_accept','first_digit','warm_interval',
            'carry_done','correction_cache_latency','cache_margin')),(4207,8417,8459,8460,12558,78,30))
        self.assertEqual(2*(new['carry_done']-g['carry_done'])+7*(new['warm_interval']-g['warm_interval']),9)

    def test_no_other_profile_or_context_admitted(self):
        b=timing.donor.prepare(32)
        for key,value in (('P',8),('CONTEXTS',2),('CORR_SERIAL_BFS',0),('MONT_FACTORED',0)):
            bad=copy.deepcopy(b);bad['parameters'][key]=value
            with self.assertRaisesRegex(ValueError,'EXACT_DIET_DONOR'):timing.bind(bad,**FLAGS)

    def test_same_edge_fault_copies_keep_origin_setter(self):
        for f in range(3):
            old=timing.prepare_field(256,16,f)
            new=timing.bind_field(old,boundary_inputreg=1,quarantine_replicas=1,final_gs_inputreg=1)
            text=new['files'][new['top']+'.sv']
            self.assertIn('fault_replicas (',text)
            self.assertIn('assign out_error=controller_error;',text)
            self.assertIn('assign fault_pending=controller_error || (|child_pending)',text)
            self.assertEqual(text.count('controller_error<=1;'),1)
            self.assertIn('.quarantine(transform_quarantine[0])',text)
            self.assertIn('.quarantine(transform_quarantine[1])',text)

    def test_term_payload_selector_preserves_private_factored_authority(self):
        before=timing.prepare(32,**FLAGS)
        after=timing.prepare(32,term_select_token=1,**FLAGS)
        self.assertEqual(before['geometry'],after['geometry'])
        self.assertEqual(before['cycle_contract'],after['cycle_contract'])
        self.assertEqual(after['parameters']['TERM_SELECT_TOKEN'],1)
        self.assertEqual(len(after['term_select_contracts']),3)
        for contract in after['term_select_contracts']:
            self.assertTrue(contract['reverse_to_actual_parent_exact'])
            self.assertTrue(contract['public_fault_and_qualified_controls_unchanged'])
            self.assertEqual(contract['actual_multiplier'],'genefer_stream27_montgomery_factored_v1')
        selector=after['files']['genefer_stream27_mul_select_token_v1_p16_diet_v1.sv']
        self.assertIn('assign data_select_slot=slot_pipe[3] && (&lane_valid) && !out_error;',selector)
        self.assertIn('genefer_stream27_montgomery_factored_v1 #(',selector)
        for name in timing.donor.fitted.PRESERVED:
            self.assertEqual(after['files'][name],before['files'][name])
        private='genefer_stream27_term_context_param_v2_p16_diet_v1_select_token_v1.sv'
        self.assertIn('if(bypass)consumer_missing=1\'b0;',after['files'][private])
        self.assertIn('if(bypass_data)current_term=product_data;',after['files'][private])


if __name__=='__main__':unittest.main()
