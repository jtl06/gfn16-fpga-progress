import copy
import unittest
from reference import stream27_context_storage_combo_timing10_bind as dut
from reference import stream27_context_timing10_model as model
from reference import stream27_context_storage_combo_registerederror_bind as r9


class Timing10(unittest.TestCase):
    def test_model(self):
        proof=model.prove()
        self.assertEqual(proof['final_gs_added_edges'],1)
        self.assertEqual(proof['new_healthy_profile_edges'],0)

    def test_default_and_both_geometries(self):
        for n in (256,65536):
            parent=dut.capture(n)
            self.assertEqual(dut.prepare(n),parent)
            self.assertEqual(dut.bind(parent),parent)
            self.assertEqual(parent,dut.capture(n))
            for lean in (0,1):
                b=dut.prepare(n,enabled=1,lean_production=lean)
                self.assertEqual(len(b['files']),58)
                g=b['geometry'];small=n==256
                self.assertEqual((g['warm_interval'],g['first_digit'],g['carry_done']),
                                 (214,195,214) if small else (8460,8459,12558))
                self.assertEqual(g['pointwise_accept'],79 if small else 4207)
                self.assertEqual(g['correction_cache_latency'],78)
                self.assertEqual(g['feedback_delay'],18 if small else 0)
                host=b['files'][b['top']+'.sv']
                self.assertIn(r9.PUB_DRAIN,host)
                self.assertIn(r9.PUB_PROPOSAL,host)
                self.assertEqual(host.count('second_correction_sent<=0;second_correction_pending<=0;'),2)
                self.assertIn('if(child_correction_accept)begin second_correction_sent<=1;',host)
                self.assertIn('.base(canonical_config_base)',host)
                self.assertIn('if(safety_error)canonical_config_valid<=0;',host)
                self.assertIn('canonical_config_owner<=live_owner[(phase[0]!=RAW_READY)*56+:56];',host)
                for name,text in b['files'].items():
                    if name.startswith('genefer_stream27_shared_warm_aw'):
                        self.assertIn(r9.FIELD_PENDING,text)
                        self.assertIn(r9.FIELD_SET,text)
                        self.assertIn(f'.SINK_FIRST({g["sink_accept"]})',text)
                    if name.startswith('genefer_stream28_merged_gs_'):
                        self.assertEqual(text.count('logic [6:0] slot_pipe,start_pipe;'),1)
                        self.assertEqual(text.count('generation_pipe[0:6];'),1)
                        self.assertIn('generation_pipe[6]',text)
                term=next(
                    t for k,t in b['files'].items() if 'storage2_v1_payload_lookahead_v1_select_token_v1.sv' in k)
                self.assertIn('wire bypass=product_slot && product_owner==pointwise_owner && product_row==pointwise_row;',term)
                self.assertIn('wire bypass_payload=data_select_slot && product_owner==payload_owner && product_row==payload_row;',term)
                self.assertIn('if(product_slot && bank_owner[prod_bank]==product_owner)',term)
                self.assertEqual(b['parameters']['ERROR_AGGREGATION_REGISTERED'],1)
                self.assertEqual(b['parameters']['COLD_SECOND_ONESHOT'],1)

    def test_calendar_and_rejection(self):
        b=dut.prepare(65536,enabled=1)
        g=b['geometry'];edges=model.event_calendar(g,2)
        self.assertEqual(edges['first_edges'],[204,4434])
        self.assertEqual(edges['warm_edges'],[21223,25453])
        self.assertEqual(edges['publication_edges'],[680688,1340152])
        self.assertEqual(edges['pair_completion_cycles']+65536,1405688)
        self.assertEqual(model.event_calendar(g,2,solo=True)['pair_completion_cycles']+65536,746124)
        for masks in ((False,False),(True,False),(False,True),(True,True)):
            changed=model.event_calendar(g,1911814,special=masks)
            base=model.event_calendar(g,1911814)
            self.assertEqual(changed['pair_completion_cycles']-base['pair_completion_cycles'],sum(masks)*65536)
        parent=dut.capture(256);bad=copy.deepcopy(parent);bad['parameters']['P']=8
        with self.assertRaises(ValueError):dut.bind(bad,enabled=1)
        with self.assertRaises(ValueError):dut.prepare(256,enabled=False)
        with self.assertRaises(ValueError):dut.prepare(256,lean_production=1)


if __name__=='__main__':unittest.main()
