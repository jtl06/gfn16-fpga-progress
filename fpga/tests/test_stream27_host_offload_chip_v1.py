"""Private R14 source/ABI checks; no HDL or full-size numeric execution."""
import re
import unittest

from fpga.reference import stream27_host_offload_chip_v1 as chip


class HostOffloadChip(unittest.TestCase):
    def test_default_off_is_exact_capture(self):
        for n in (256,65536):
            self.assertEqual(chip.prepare(n),chip.capture(n))
        for bad in (True,-1,2):
            with self.assertRaises(ValueError):chip.prepare(host_offload=bad)

    def test_private_graph_reverses_every_byte_and_keeps_all_parent_modules(self):
        for n in (256,65536):
            parent=chip.capture(n);new=chip.prepare(n,host_offload=1)
            self.assertEqual(len(new['files']),66)
            self.assertEqual(len(new['host_offload']['source_edits']),6)
            for name,text in parent['files'].items():self.assertEqual(new['files'][name],text)
            renames={name[:-3]:row['new_file'][:-3] for name,row in new['host_offload']['source_edits'].items()}
            for name,row in new['host_offload']['source_edits'].items():
                changed=new['files'][row['new_file']]
                for old,private in renames.items():changed=re.sub(r'\b'+re.escape(private)+r'\b',old,changed)
                self.assertEqual(chip.reverse(changed,row['edits']),parent['files'][name])
            self.assertEqual(new['geometry'],parent['geometry'])
            self.assertEqual(new['two_context_schedule'],parent['two_context_schedule'])
            self.assertEqual(new['parameters'],dict(parent['parameters'],HOST_OFFLOAD=1))

    def test_runtime_flag_default_off_instantiates_literal_parent(self):
        b=chip.prepare(host_offload=1);t=b['files'][b['top']+'.sv']
        self.assertIn('parameter int HOST_OFFLOAD=0,AW=8',t)
        self.assertIn('if(HOST_OFFLOAD==0)begin: protected_parent',t)
        self.assertIn(b['host_offload']['parent_top']+' #(',t)

    def test_cold_only_latency_permutation_and_no_high_base_multiply(self):
        b=chip.prepare(host_offload=1)
        for f in range(3):
            t=next(t for name,t in b['files'].items() if name.startswith('genefer_stream27_shared_warm_aw8_p16_f'+str(f)) and name.endswith('_host_offload_v1.sv'))
            self.assertIn('off_digit_select[3] ? off_digit_data[3]',t)
            self.assertIn('off_boundary_select[5] ? off_boundary_data[5]',t)
            self.assertIn('off_low[off_reverse(lane)*32+:27]',t)
            self.assertIn('off_high_q[off_reverse(lane)*32+:27]',t)
            self.assertIn('genefer_digit_reduce27_pipe',t)
            self.assertIn('genefer_stream27_signed_boundary_inputreg_v1',t)
        warm=next(t for name,t in b['files'].items() if name.startswith('genefer_stream27_warm_contexts_aw') and name.endswith('_host_offload_v1.sv'))
        self.assertIn('off_cold_slot && !delayed_feedback_slot',warm)
        self.assertIn('off_cold_correction && !delayed_auto_correction',warm)

    def test_profile_and_publication_fail_closed_contract(self):
        b=chip.prepare(host_offload=1)
        t=b['files'][b['host_offload']['parent_top']+'_host_offload_v1.sv']
        self.assertIn('|| !off_profile_good)local_error<=1;',t)
        self.assertIn('off_saved_generation[c*8+:8]!=job_generation[c]+8\'d1',t)
        self.assertIn('off_saved_epoch[c*16+:16]!=next_epoch[c]',t)
        self.assertIn('if(off_transfer_bad || load_we || read_en)local_error<=1;',t)
        self.assertIn('if(raw_rows[c]!=(ROW_W+1)\'(ROWS) || !off_boundary_seen[c])local_error<=1;',t)
        self.assertNotIn(' scratch (',t)
        self.assertNotIn(' shadows (',t)
        self.assertIn('assign shadow_capture_ack=1\'b0;',t)
        self.assertNotIn('(capture_req_d && !shadow_capture_ack)',t)
        arith=next(t for name,t in b['files'].items() if name.startswith('genefer_stream27_threefield') and name.endswith('_host_offload_v1.sv'))
        self.assertIn("reciprocal==off_expected_reciprocal && {19'd0,coefficient_limit}==off_expected_limit",arith)
        self.assertIn('shared_setup (',arith)

    def test_ingress_leaf_never_trim_or_publish_partial_profile(self):
        t=(chip.ROOT/chip.LEAF).read_text()
        self.assertIn('numeric_ok=word_data<selected_prime;',t)
        self.assertIn("count[context_in]!=(AW+3)'(word_index)",t)
        self.assertIn("count[context_in]!=(AW+3)'(WORDS)",t)
        self.assertIn('profile_generation[31:8]!=0',t)
        self.assertIn('profile_limit[95:77]!=0',t)
        self.assertIn('loaded<=0;staging<=0;error<=0;row_valid<=0;',t)
        self.assertIn('!context_busy[context_in] && staging[context_in]',t)
        with self.assertRaises(ValueError):chip.change('duplicate duplicate','duplicate','new',[])


if __name__=='__main__':unittest.main()
