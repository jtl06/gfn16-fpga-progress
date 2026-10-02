import unittest
from fpga.reference import stream27_two_context_native as native
from fpga.reference import stream27_two_context_whole_programs as whole

class TwoContextNativeTests(unittest.TestCase):
    def test_unequal_frames_wrap_and_independent_bank_allocator(self):
        manifest,_=native.role(5,8,0);plan=manifest['two_context']['calendar']
        a=[f for f in plan['frames'] if f['context']==0];b=[f for f in plan['frames'] if f['context']==1]
        self.assertEqual([len(a),len(b)],[3,5]);self.assertEqual([f['epoch'] for f in a],[65534,65535,0])
        self.assertEqual([f['bank'] for f in a],[0,0,0]);self.assertEqual([f['bank'] for f in b],[1,1,1,0,0])
        self.assertEqual(plan['peak'],2);self.assertEqual(plan['used_bank_mask'],3)
        self.assertEqual(plan['lease_edges'][-1]['post_owners'],0)
    def test_cache_precedes_pointwise_and_normal_is_not_fault_coupled(self):
        manifest,_=native.role(5,8,0)
        self.assertTrue(all(row['cache_capture']<row['pointwise_first'] for row in manifest['two_context']['calendar']['corrections']))
        self.assertEqual(len(manifest['steps']),1);self.assertEqual(manifest['steps'][0]['argv'],['{exe}'])
        self.assertEqual(manifest['build']['parameters']['CONTEXTS'],2)
        self.assertFalse(manifest['two_context']['full_N_numeric_locally_performed'])
    def test_native_independent_reference_is_pinned(self):
        manifest,files=native.role(5,8,0)
        self.assertEqual(manifest['sources'][native.REFERENCE],native.REFERENCE_PIN)
        self.assertIn(b'ref_self_check()',files[native.CPP]);self.assertIn(b'S4_TWO_PHYSICAL_FULL_TAG',files[native.CPP])
    def test_edge_phase_keeps_actual_fault_and_dense_continuation(self):
        _,files=native.role(5,8,0);cpp=files[native.CPP]
        self.assertIn(b'!d.fault_pending&&!d.out_error,"S4_TWO_PRE_PENDING',cpp)
        self.assertIn(b'!d.out_error,"S4_TWO_POST_ERROR',cpp)
        self.assertIn(b'd.frame_start=0;d.correction_valid=0;',cpp)
        self.assertIn(b'd.in_slot_valid=incoming && tick+1<incoming->start+T;',cpp)
        self.assertIn(b'S4_TWO_QUIESCENT_PENDING',cpp)
        diagnostic=(native.ROOT/'rtl/tb/stream27_two_context_start_diag.cpp').read_bytes()
        self.assertIn(b'S4_TWO_DUPLICATE_LATCHED',diagnostic)
        self.assertIn(b'S4_TWO_DUPLICATE_OTHER_CONTEXT_STOP',diagnostic)
    def test_true_small_dependent_programs_and_final_signed_sentinel(self):
        plan=whole.programs()
        for ctx in plan['contexts']:
            steps=ctx['dependent_steps'];self.assertEqual(len(steps),ctx['frame_count'])
            self.assertEqual(steps[-1]['canonical_signed32'],[-1]+[0]*31)
            for previous,current in zip(steps,steps[1:]):self.assertEqual(previous['output_residue_hex'],current['input_residue_hex'])
            self.assertEqual(whole.expand(ctx['initial_digits'],ctx['initial_c0'],ctx['initial_c1'],ctx['base'],8),int(ctx['initial_residue_hex'],16))
        self.assertNotEqual(plan['contexts'][0]['initial_c0'],plan['contexts'][1]['initial_c0'])
        self.assertNotEqual(plan['contexts'][0]['initial_c1'],plan['contexts'][1]['initial_c1'])
        self.assertFalse(plan['dispatch_allowed'])
if __name__=='__main__':unittest.main()
