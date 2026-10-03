import unittest
from reference import stream27_protected_field100_bind as parent
from reference import stream27_protected_relay13_bind as candidate


class Relay13Source(unittest.TestCase):
    def parent(self,n):
        return parent.prepare(n,enabled=1,**{k.lower():1 for k in parent.FLAGS})

    def test_disabled_exact_frozen_field100(self):
        for n in (256,65536):self.assertEqual(candidate.prepare(n),self.parent(n))

    def test_primary_reverses_every_byte_and_counts_actual_relays(self):
        for n,interval in ((256,218),(65536,8464)):
            old=self.parent(n)
            new=candidate.prepare(n,enabled=1,**{k.lower():1 for k in candidate.FLAGS})
            c=new['context_protected_relay13']
            self.assertEqual(len(new['files']),58)
            self.assertNotIn('LEAN_PRODUCTION',new['parameters'])
            self.assertEqual(new['parameters']['CRT_TRANSPORT_REG'],0)
            self.assertEqual(new['geometry']['warm_interval'],interval)
            self.assertEqual(c['field_boundary_edges_added'],3)
            self.assertEqual(c['declared_new_register_bits'],5523)
            for name,row in c['source_edits'].items():
                self.assertEqual(candidate.reverse(new['files'][row['new_file']],row['edits']),old['files'][name])
            fields=[t for name,t in new['files'].items() if name.startswith('genefer_stream27_shared_warm_aw')]
            self.assertEqual(len(fields),3)
            for t in fields:
                self.assertIn('wire stop=out_error_fast;',t)
                self.assertIn('assign out_error_fast=protocol_error;',t)
                self.assertIn('controller_error<=out_error_fast;',t)
                self.assertIn('.in_slot_valid(forward_slot_q && !stop)',t)
                self.assertIn('.in_slot_valid(pair_slot_q && !stop)',t)
                self.assertIn('.in_slot_valid(inverse_slot_q && !stop)',t)
                self.assertIn('forward_generation_q<=launch_tag[ROW_W+25:ROW_W+1]',t)
                self.assertIn(f'.POINTWISE_FIRST({new["geometry"]["pointwise_accept"]})',t)
                self.assertIn(f'.SINK_FIRST({new["geometry"]["sink_accept"]})',t)

    def test_FAST_protocol_arithmetic_fold_and_one_shot_literals(self):
        for n in (256,65536):
            old=self.parent(n);new=candidate.prepare(n,enabled=1,**{k.lower():1 for k in candidate.FLAGS})
            for name,t in old['files'].items():
                if name.startswith(('genefer_stream27_epoch_protocol_contexts','genefer_stream27_canonical_image_foldpayload')):
                    self.assertEqual(new['files'][name],t)
            oldarith=next(t for name,t in old['files'].items() if name.startswith('genefer_stream27_threefield_carry_aw'))
            newarith=next(t for name,t in new['files'].items() if name.startswith('genefer_stream27_threefield_carry_aw'))
            row=next(r for name,r in new['context_protected_relay13']['source_edits'].items()
                if name.startswith('genefer_stream27_threefield_carry_aw'))
            self.assertEqual(candidate.reverse(newarith,row['edits']),oldarith)
            oldhost=old['files'][old['top']+'.sv'];newhost=new['files'][new['top']+'.sv']
            for begin,end in (('   if(publish_pending)begin','   if(shadow_commit_ack'),
                    ('wire cold_second_due','wire cold_correction')):
                self.assertEqual(newhost.split(begin,1)[1].split(end,1)[0],oldhost.split(begin,1)[1].split(end,1)[0])
            warmold=next(t for name,t in old['files'].items() if name.startswith('genefer_stream27_warm_contexts_aw'))
            warmnew=next(t for name,t in new['files'].items() if name.startswith('genefer_stream27_warm_contexts_aw'))
            row=next(r for name,r in new['context_protected_relay13']['source_edits'].items()
                if name.startswith('genefer_stream27_warm_contexts_aw'))
            self.assertEqual(candidate.reverse(warmnew,row['edits']),warmold)

    def test_closed_switches(self):
        with self.assertRaises(ValueError):candidate.prepare(256,inverse_ingress_reg=1)
        with self.assertRaises(ValueError):candidate.prepare(256,enabled=1)
        with self.assertRaises(ValueError):candidate.prepare(256,enabled=True)


if __name__=='__main__':unittest.main()
