import copy
import itertools
import unittest

from reference import stream27_context_storage_combo_timing10_bind as parent
from reference import stream27_context_storage_combo_transport11_bind as candidate
from reference import stream27_context_storage_combo_transport11_source_v2 as closure


class Transport11Source(unittest.TestCase):
    def test_capture_closure_only_adapter(self):
        for n in (256,65536):
            kwargs=dict(enabled=1,lean_production=1,crt_transport_reg=1,
                        inverse_ingress_reg=1,term_join_transport_reg=1,lean_progress_watchdog=1)
            first=candidate.prepare(n,**kwargs);bound=closure.prepare(n,**kwargs)
            for key in ('files','generated_sha256','top','parameters','geometry'):
                self.assertEqual(bound[key],first[key])
            captures=[path for path in bound['source_dependencies']
                      if 'trackS-c2-storage-combo-timing10-native-v1/' in path and path.endswith('production-bundle.json')]
            self.assertEqual(len(captures),2)
            self.assertTrue(all(bound['source_sha256'][path] for path in captures))

    def test_default_exact_both_modes_and_geometries(self):
        for n,lean in itertools.product((256,65536),(0,1)):
            expected=parent.prepare(n,enabled=1,lean_production=lean)
            self.assertEqual(candidate.prepare(n,lean_production=lean),expected)

    def test_primary_owned_calendar_and_authority(self):
        for n,lean in itertools.product((256,65536),(0,1)):
            b=candidate.prepare(n,enabled=1,lean_production=lean,
                crt_transport_reg=1,inverse_ingress_reg=1,term_join_transport_reg=1,
                lean_progress_watchdog=lean)
            p=parent.prepare(n,enabled=1,lean_production=lean)
            g=b['geometry'];old=p['geometry']
            self.assertEqual(len(b['files']),58)
            self.assertEqual(g['sink_accept'],old['sink_accept']+2)
            self.assertEqual(g['first_digit'],old['first_digit']+3)
            self.assertEqual(g['warm_interval'],old['warm_interval']+3)
            self.assertEqual(g['carry_done'],old['carry_done']+3)
            for key in ('pointwise_accept','correction_cache_latency','term_seed_first','term_seed_last','feedback_delay'):
                self.assertEqual(g[key],old[key])
            for name,body in p['files'].items():
                if 'term_context_param' in name or 'epoch_protocol' in name or 'mul_select_token' in name:
                    self.assertEqual(b['files'][name],body)
            arith=next(body for name,body in b['files'].items() if name.startswith('genefer_stream27_threefield'))
            self.assertIn('if(joined && field_row[0]==ROW_W\'(ROWS-1) && !join_bad && !error_barrier)bank_live[bank]<=0;',arith)
            self.assertIn('if(crt_transport_slot)begin crt_tag[0]<=crt_transport_tag;',arith)
            self.assertIn('.base(crt_transport_base)',arith)
            for body in b['files'].values():
                if 'inverse_transform (' in body:
                    self.assertIn('.data_in(inverse_data_q)',body)
                    self.assertIn('.lhs(pair_lhs_q),.rhs(pair_rhs_q)',body)
            self.assertIn('publish_owner!=live_owner',b['files'][b['top']+'.sv'])
            self.assertIn('second_correction_sent',b['files'][b['top']+'.sv'])
            self.assertIn('if(raw_begin_carry && ((|lane_busy) || (crt_transport_slot && crt_transport_start)))carry_bad=1;',arith)
            if lean:self.assertIn('lean_square_progress',b['files'][b['top']+'.sv'])

    def test_independent_switches_and_fail_closed(self):
        for crt,inv,term in itertools.product((0,1),repeat=3):
            if not(crt or inv or term):continue
            b=candidate.prepare(256,enabled=1,crt_transport_reg=crt,
                                inverse_ingress_reg=inv,term_join_transport_reg=term)
            self.assertEqual(b['geometry']['sink_accept'],153+inv+term)
            self.assertEqual(b['geometry']['first_digit'],195+crt+inv+term)
        for kwargs in ({'enabled':0,'crt_transport_reg':1},
                       {'enabled':1}, {'enabled':1,'crt_transport_reg':2},
                       {'enabled':1,'crt_transport_reg':1,'lean_progress_watchdog':1}):
            with self.assertRaises(ValueError):candidate.prepare(256,**kwargs)


if __name__=='__main__':unittest.main()
