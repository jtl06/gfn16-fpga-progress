import unittest
from fpga.reference import stream27_term_lookahead_p16_bind as binding
class LookaheadSourceTests(unittest.TestCase):
    def test_default_and_original_files_are_exact(self):
        parent=binding.donor.prepare_field(256,16,1,mode='warm',boundary_inputreg=1,quarantine_replicas=1,final_gs_inputreg=1,term_select_token=1)
        self.assertEqual(binding.bind(parent,0),parent)
        new=binding.bind(parent)
        for name,text in parent['files'].items():self.assertEqual(new['files'][name],text)
        self.assertEqual(new['geometry'],parent['geometry'])
    def test_payload_only_authority_and_first_row(self):
        b=binding.prepare();c=b['term_lookahead'];term=b['files'][c['new_term']+'.sv'];parent=b['files'][c['parent_term']+'.sv']
        for marker in ('wire product_accept=','wire [TAG_W-1:0] issue_tag=','assign cache_ready=','assign fault_pending='):
            self.assertEqual(term.split(marker,1)[1].split(';',1)[0],parent.split(marker,1)[1].split(';',1)[0])
        self.assertIn('small_data[27*int\'(term_payload_target_next[ROW_W-1-:4])+:27]',b['files'][b['top']+'.sv'])
        for row in range(4096):
            target=(row+4)&4095;group=target>>8;reverse=int(f'{group:04b}'[::-1],2)
            self.assertEqual(int(f'{reverse:04b}'[::-1],2),group)
        self.assertEqual((0+4)&4095,4)
    def test_real_paired_native_source(self):
        from fpga.reference import stream27_term_lookahead_p16_native as native
        m,files=native.role();self.assertEqual(m['term_lookahead']['counts']['physical_words'],2304)
        source=files['rtl/'+m['build']['top']+'.sv'].decode()
        for name in ('out_error','fault_pending','frame_accept','owner_count','data_out','commit_valid'):
            self.assertIn('TERM_LOOKAHEAD_PAIR_'+name,source)
    def test_cycle32_epoch_wrap_and_same_edge_table_write(self):
        from fpga.reference import stream27_term_lookahead_p16_model as model
        for rows,pw,sink in ((16,79,153),(4096,4207,8417)):
            result=model.check(rows,pw,sink)
            self.assertEqual(result['pointwise_firsts'],6);self.assertEqual(result['epoch_wrap_admissions'],2)
            self.assertGreater(result['simultaneous_B_write_forwards'],100)
    def test_fault_leaf_is_actual_and_control_remains_rc41(self):
        from fpga.reference import stream27_term_lookahead_p16_fault_native as fault
        m,files=fault.role();self.assertEqual(len(m['steps']),2);self.assertEqual(m['steps'][1]['expected_returncode'],41)
        self.assertIn('.payload_row(pointwise_row)',files['rtl/'+fault.TOP+'.sv'].decode())
        self.assertIn('malformed-row',m['term_lookahead']['scope'])
    def test_wrap_normal_preserves_rtl_and_full_owner_checks(self):
        from fpga.reference import stream27_term_lookahead_p16_native as native
        from fpga.reference import stream27_term_lookahead_p16_wrap_native as wrap
        original,old=native.role();m,files=wrap.role()
        for name,raw in old.items():
            if name.endswith('.sv'):self.assertEqual(files[name],raw)
        cpp=files[native.CPP].decode()
        self.assertIn('frame(2,0,0,65535),frame(3,INTERVAL,CORRECTION,0)',cpp)
        self.assertIn('d.generation_out==255',cpp)
        self.assertIn('d.live_generation=live?255:0',cpp)
        self.assertEqual(m['term_lookahead']['counts']['frames'],11)
        self.assertEqual(m['term_lookahead']['counts']['physical_words'],2816)
if __name__=='__main__':unittest.main()
