import unittest
import copy
from fpga.reference import stream27_shared_field_v4 as donor
from fpga.reference import stream27_timing_field_native as n


class TimingFieldNormalPackaging(unittest.TestCase):
    def test_bounded_reference_and_every_edge_lease_contract(self):
        # Frozen donor exercises only generic harness emission here. This is
        # NOT a claim that the new shared r75 API/RTL has passed source/native.
        for field in range(3):
            b=donor.prepare(256,8,field,mode='warm',contexts=1)
            cpp,header,counts,ledgers,footer=n.compile_normal(b,field)
            self.assertIn('ref_self_check();',cpp)
            self.assertIn('R75_FIELD_OWNER_EDGE',cpp)
            self.assertIn('tick<f.start+SINK+T-1',cpp)
            self.assertIn('S4_PHYSICAL_TAG',cpp)
            self.assertIn('S4_COMMIT_TAG',cpp)
            self.assertIn('expected=',cpp)
            self.assertIn('S4_FAULT_ORIGIN',cpp)
            self.assertEqual(counts['physical_words'],9*256)
            self.assertEqual(counts['eligible_rows'],7*32)
            self.assertFalse(any(item['rejected'] for item in ledgers))
            self.assertTrue(footer.startswith(f'S4_R75_FIELD_PASS aw=8 p=8 field={field}'))
            self.assertIn(f'SINK={b["geometry"]["sink_accept"]}',header)

    def test_geometry_and_frozen_api_reject_before_compiler_use(self):
        for aw,p,field in ((5,8,0),(8,32,0),(8,8,3),(8,8.0,0)):
            with self.subTest(aw=aw,p=p,field=field),self.assertRaisesRegex(ValueError,'GEOMETRY'):
                n.field_bundle(aw,p,field,'0'*64)

    def test_local_native_label_and_source_join_preflight(self):
        files={'rtl/t.sv':b'module t; endmodule','rtl/t.cpp':b'int main(){return 0;}'}
        role=dict(steps=[dict(name='normal-r75-field')],sources={name:n.sha(raw) for name,raw in files.items()},
            build=dict(sv_sources=['rtl/t.sv'],cpp_source='rtl/t.cpp',parameters=dict(AW=8,P=8)),
            rtl_readiness=dict(source_snapshot={'rtl/t.sv':n.sha(files['rtl/t.sv'])}))
        n.preflight(role,files)
        for name in ('normal-E6','build','wrong_label'):
            bad=copy.deepcopy(role);bad['steps'][0]['name']=name
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'STEP_GRAMMAR'):n.preflight(bad,files)

    def test_actual_r75_p16_small_field_calendar_and_root_binding(self):
        # Current mutable tool routing is hash-bound by the role; captured
        # P8 packets retain their historical API bytes and are not rehosted.
        pin=n.sha((n.ROOT/n.API_BY_P[16]).read_bytes())
        primes=(104857601,69206017,67239937)
        for field,p in enumerate(primes):
            b=n.field_bundle(8,16,field,pin);g=b['geometry']
            self.assertEqual((g['pointwise_accept'],g['physical_first'],g['sink_accept'],g['warm_interval'],g['correction_cache_latency']),(79,152,153,214,78))
            text=next(value for name,value in b['files'].items() if name.startswith('genefer_stream28_merged_gs_') and name.endswith('_inputreg_v1.sv'))
            wrapper=b['inverse_inputreg_parent']['wrapper_module']
            self.assertEqual(text.count(wrapper+' #('),8)
            self.assertEqual(text.count(f".UPPER_SCALE(32'd{pow(1<<32,2,p)*pow(256,-1,p)%p})"),8)
            self.assertIn('generation_pipe[0:6]',text)
            self.assertIn('k<7;k=k+1)generation_pipe',text)
            self.assertEqual(b['parameters']['FINAL_GS_INPUTREG'],1)
            self.assertEqual(b['parameters']['BOUNDARY_INPUTREG'],1)
            self.assertEqual(b['parameters']['QUARANTINE_REPLICAS'],1)
            self.assertEqual(b['parameters']['CORR_SERIAL_BFS'],2)
            self.assertEqual(b['parameters']['COMM_STAGE_SHARED_MLAB'],1)
            self.assertEqual(b['parameters']['MONT_FACTORED'],1)
            self.assertEqual(b['parameters']['TERM_SELECT_TOKEN'],1)
            self.assertTrue(b['term_select']['reverse_to_actual_parent_exact'])
            self.assertEqual(g['input_delay'],8)
            self.assertEqual(g['cache_margin'],0)
            with self.assertRaisesRegex(ValueError,'FROZEN_SHARED_API'):
                n.field_bundle(8,16,field,'0'*64)
        self.assertEqual(n.field_flags(8),n.FLAGS)
        self.assertNotIn('term_select_token',n.field_flags(8))
        self.assertEqual(n.sha((n.ROOT/n.REFERENCE).read_bytes()),n.REFERENCE_PIN)

    def test_p16_full_source_constants_and_calendar_no_numeric_ntt(self):
        # Root/source generation only: the full numerical reference executes
        # on the native worker, never in this source-only test.
        pin=n.sha((n.ROOT/n.API_BY_P[16]).read_bytes())
        for field,prime in ((0,104857601),(2,67239937)):
            b=n.field_bundle(16,16,field,pin);g=b['geometry']
            self.assertEqual(tuple(g[key] for key in ('pointwise_accept','physical_first',
                'sink_accept','warm_interval','correction_cache_latency','cache_margin')),
                (4207,8416,8417,8460,78,30))
            text=next(value for name,value in b['files'].items()
                if name.startswith('genefer_stream28_merged_gs_') and name.endswith('_inputreg_v1.sv'))
            scale=pow(1<<32,2,prime)*pow(65536,-1,prime)%prime
            self.assertEqual(text.count(f".UPPER_SCALE(32'd{scale})"),8)
            self.assertFalse(g['full_N_numeric_NTT_performed'])
            self.assertTrue(b['term_select']['geometry_unchanged'])

    def test_short_native_wrapper_preserves_every_production_byte(self):
        pin=n.sha((n.ROOT/n.API_BY_P[16]).read_bytes())
        for field in range(3):
            before=n.field_bundle(8,16,field,pin)
            after=n.native_wrapper_bundle(before,field)
            self.assertLess(len(after['top']),128)
            self.assertEqual(after['geometry'],before['geometry'])
            self.assertEqual(after['parameters'],before['parameters'])
            self.assertTrue(all(after['files'][name]==text for name,text in before['files'].items()))
            self.assertEqual(len(after['files']),len(before['files'])+1)
            wrapper=after['files'][after['top']+'.sv']
            self.assertIn('candidate (.*);',wrapper)
            self.assertNotIn('always',wrapper)
            self.assertEqual(after['native_wrapper']['added_edges'],0)
            for key in after['native_wrapper']['parameter_names']:
                self.assertIn('.'+key+'('+key+')',wrapper)
            self.assertEqual(n.role_version(16),2)
        bad=copy.deepcopy(before);bad['parameters']['UNDECLARED_FLAG']=1
        with self.assertRaisesRegex(ValueError,'PARAMETER_JOIN'):n.native_wrapper_bundle(bad,2)


if __name__=='__main__':unittest.main()
