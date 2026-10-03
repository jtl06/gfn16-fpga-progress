import unittest
from reference import stream27_context_storage_combo_transport11_source_v2 as parent
from reference import stream27_context_feedback12_bind as candidate


class Feedback12Source(unittest.TestCase):
    def test_disabled_exact_both_modes_and_geometries(self):
        for n in (256,65536):
            for lean in (0,1):
                baseline=parent.prepare(n,enabled=1,lean_production=lean,crt_transport_reg=1,
                    inverse_ingress_reg=1,term_join_transport_reg=1,lean_progress_watchdog=lean)
                self.assertEqual(candidate.prepare(n,lean_production=lean),baseline)

    def test_literal_reversal_and_calendar(self):
        for n in (256,65536):
            parent_bundle=candidate.prepare(n)
            b=candidate.prepare(n,enabled=1,feedback_ingress_reg=1,
                auto_correction_ingress_reg=1,c0_admission_direct=1)
            self.assertEqual(len(b['files']),58)
            self.assertEqual(b['geometry']['warm_interval'],parent_bundle['geometry']['warm_interval']+1)
            self.assertEqual(b['geometry']['correction_cache_latency'],78)
            self.assertEqual(b['geometry']['pointwise_accept'],parent_bundle['geometry']['pointwise_accept'])
            meta=b['context_feedback12']
            self.assertTrue(meta['source_ready'])
            self.assertEqual(meta['declared_new_register_bits'],1663)
            self.assertEqual(meta['existing_feedback_fifo_rows'],18 if n==256 else 0)
            self.assertEqual(meta['explicit_feedback_register_rows'],1)
            for name,record in meta['source_edits'].items():
                # Graph namespace reversal precedes content edits.
                final_name=name
                if name.startswith(('genefer_stream27_shared_warm_aw','genefer_stream27_warm_contexts_aw','genefer_stream27_threefield_carry_aw')):
                    final_name=name[:-3]+'_feedback12_v1.sv'
                elif name==parent_bundle['top']+'.sv':final_name=b['top']+'.sv'
                text=b['files'][final_name]
                if name==parent_bundle['top']+'.sv':text=candidate.reverse(text,meta['host_calendar_edits'])
                self.assertEqual(candidate.reverse(text,record['edits']),parent_bundle['files'][name])
            host=b['files'][b['top']+'.sv']
            old_host=parent_bundle['files'][parent_bundle['top']+'.sv']
            for start,end in (('  // Cold-only transaction:', ' wire cold_first_correction'),):
                self.assertEqual(host[host.index(start):host.index(end)],old_host[old_host.index(start):old_host.index(end)])
            warm=next(t for name,t in b['files'].items() if name.startswith('genefer_stream27_warm_contexts_aw'))
            self.assertIn('wire command_bad=raw_command_bad || queued_command_bad;',warm)
            self.assertIn('feedback_index_q<=launched[raw_feedback_context]',warm)
            self.assertIn('auto_epoch_q<=next_epoch;auto_generation_q<=next_generation;',warm)
            self.assertIn('feedback_double_q<=raw_selected_double',warm)
            self.assertIn('if(feedback_start)begin\n    feedback_double_q',warm)
            self.assertIn('wire collision=raw_collision || (cold_slot && delayed_feedback_slot)',warm)
            self.assertIn('if(child_barrier || collision || count_bad || command_bad || cold_request_bad)local_error<=1;',warm)
            self.assertNotIn('fifo_valid[18]',warm)

    def test_pair_required(self):
        with self.assertRaises(ValueError):candidate.prepare(256,enabled=1,feedback_ingress_reg=1)


if __name__=='__main__':unittest.main()
