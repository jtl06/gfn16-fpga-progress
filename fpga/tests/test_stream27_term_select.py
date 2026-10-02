import copy
import itertools
import unittest
from fpga.reference import stream27_shared_field_flags as donor
from fpga.reference import stream27_shared_field_contexts as contexts
from fpga.reference import stream27_term_select_bind as bind
from fpga.reference import stream27_term_select_native as native
from fpga.reference import stream27_term_select_fault_native as faults


class TermSelectTests(unittest.TestCase):
    def check_bundle(self,parent):
        before=copy.deepcopy(parent);after=bind.bind(parent)
        self.assertEqual(parent,before);self.assertEqual(bind.bind(parent,enabled=0),parent)
        info=after['term_select'];root=after['files'][after['top']+'.sv']
        self.assertEqual(bind.reverse_root(root,parent['top'],after['top'],info['parent_term'],
                                          info['new_term'],parent['parameters']['CONTEXTS']),
                         parent['files'][parent['top']+'.sv'])
        self.assertEqual(bind.reverse_term(info['new_term'],after['files'][info['new_term']+'.sv']),
                         (info['parent_term'],parent['files'][info['parent_term']+'.sv']))
        for name,text in parent['files'].items():
            if name not in (parent['top']+'.sv',info['parent_term']+'.sv'):
                self.assertEqual(after['files'][name],text)
        self.assertEqual(after['geometry'],parent['geometry'])
        term=after['files'][info['new_term']+'.sv']
        self.assertEqual(term.count('bypass_data'),3)
        self.assertIn("if(bypass)consumer_missing=1'b0;",term)
        self.assertIn('wire product_accept=(seed_slot || update_slot) && !stop;',term)
        self.assertIn('if(product_slot && bank_owner[prod_bank]==product_owner)',term)
        return after

    def test_exact_reverse_all_fields_lanes_term_versions_and_full_owner_widths(self):
        for p,field in itertools.product((8,16),range(3)):
            self.check_bundle(donor.prepare(256,p,field,mode='warm_signed'))
            self.check_bundle(donor.prepare(32,p,field,mode='warm_signed'))
        b=self.check_bundle(contexts.prepare(32,8,1,mode='warm_signed',contexts=2))
        self.assertIn('TAG_W=27+ROW_W',b['files'][b['term_select']['new_term']+'.sv'])

    def test_exact_control_fail_closed_and_composable_boundary(self):
        parent=donor.prepare(256,8,1,mode='warm_signed',boundary_inputreg=1)
        after=self.check_bundle(parent)
        with self.assertRaisesRegex(ValueError,'ALREADY_BOUND'):bind.bind(after)
        broken=copy.deepcopy(parent);name='genefer_stream27_term_context_param_v1.sv'
        broken['files'][name]=broken['files'][name].replace('wire bypass=product_slot','wire bypass=product_pending')
        with self.assertRaisesRegex(ValueError,'SOURCE_ANCHOR'):bind.bind(broken)

    def test_exhaustive_live_data_selection_and_stopped_sampling_invariance(self):
        # Exact combinational theorem, not a native timing or arithmetic claim.
        for slot,lanes,error,stop,tag in itertools.product((False,True),repeat=5):
            qualified=slot and lanes and not error and not stop
            select=slot and lanes and not error
            before=qualified and tag;after=select and tag
            if not stop:self.assertEqual(before,after)
            for fallback,product in itertools.product((0,17,1234567),repeat=2):
                old=product if before else fallback;new=product if after else fallback
                old_sample=old if not stop else None;new_sample=new if not stop else None
                self.assertEqual(old_sample,new_sample)

    def test_normal_role_exact_independent_reference_counts(self):
        m,files,snapshot=native.role()
        self.assertEqual(m['test_role'],'normal');self.assertEqual(m['build']['parameters']['TERM_SELECT_TOKEN'],1)
        self.assertIn(b'ref_self_check();',files[native.CPP])
        self.assertEqual(m['steps'][0]['expected_stdout'],
            'S4_TERM_SELECT_NORMAL aw=8 p=8 field=1 cases=9 frames=9 physical_rows=288 physical_words=2304 eligible_rows=224 commits=224 peak_owners=1\n')
        self.assertTrue(all(m['sources'][name]==pin for name,pin in snapshot.items()))

    def test_actual_p16_serial2_calendar_and_full_root_sources(self):
        m,files,_=native.role(8,16,1,corr_serial_bfs=2)
        g=m['term_select']['geometry'];params=m['build']['parameters']
        self.assertEqual(params['CORR_SERIAL_BFS'],2)
        self.assertEqual(g['correction_pair_interval'],60)
        self.assertEqual(m['term_select']['counts']['physical_words'],2304)
        self.assertIn(b'genefer_stream27_correction_serial_v1',
                      files['rtl/genefer_stream27_correction_serial_v1.sv'])
        b=native.field_bundle(16,16,1,corr_serial_bfs=2)
        self.assertEqual(b['geometry']['rows'],4096)
        root=[text for name,text in b['files'].items() if 'shared_term_roots_aw16_p16_f1' in name]
        self.assertEqual(len(root),1);self.assertIn('ramstyle="M20K"',root[0])
        self.assertEqual(b['term_select']['product_capture_edges'],4)

    def test_actual_p16_term_root_pair_and_full_baseline_typed_mutant(self):
        m,files=faults.role();self.assertEqual(m['test_role'],'deliberate_fault')
        self.assertEqual([s['expected_returncode'] for s in m['steps']],[0,41])
        self.assertEqual(m['steps'][0]['expected_stdout'],m['steps'][1]['expected_stdout'])
        self.assertIn(b'genefer_stream27_term_context_param_v1 #',files['rtl/'+faults.TOP+'.sv'])
        self.assertIn(b'.pw_row(pointwise_row)',files['rtl/'+faults.TOP+'.sv'])
        cpp=files[faults.CPP].decode()
        for token in ('footer(c);','if(negative)','expected(row,lane,salt)',
                      'S4_TERM_SELECT_REGISTERED_FAULT_EDGE','S4_TERM_SELECT_STOPPED_RAW_SELECTION_ACTUALLY_OBSERVED',
                      'S4_TERM_SELECT_RESET_STALE_TAIL','S4_TERM_SELECT_DIRECT_OWNER_ROW_START'):
            self.assertIn(token,cpp)


if __name__=='__main__':unittest.main()
