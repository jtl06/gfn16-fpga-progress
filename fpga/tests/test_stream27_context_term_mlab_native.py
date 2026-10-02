import unittest
from fpga.reference import stream27_context_term_mlab_native as native


class TermMlabNativeTests(unittest.TestCase):
    def test_paired_parent_and_candidate_actual_dependencies(self):
        m,files=native.role()
        self.assertEqual(len(m['build']['sv_sources']),6)
        self.assertIn('rtl/'+native.binding.TERM+'.sv',m['build']['sv_sources'])
        self.assertIn('rtl/'+native.binding.NEW+'.sv',m['build']['sv_sources'])
        self.assertEqual(m['build']['parameters'],{})
        self.assertIn('old_leaf.current_term',files['rtl/'+native.TOP+'.sv'].decode())
        self.assertIn('new_leaf.current_term',files['rtl/'+native.TOP+'.sv'].decode())
        self.assertFalse(m['term_mlab_unit']['inferred_MLAB_credit'])

    def test_scalar_identity_and_actual_pre_post_collision_contract(self):
        m,files=native.role()
        cpp=files[native.CPP].decode()
        self.assertIn('paired(d,d.pointwise_slot)',cpp)
        self.assertIn('bypass==480',cpp)
        self.assertIn('TERM_MLAB_PRE_INDEPENDENT_VALUE',cpp)
        self.assertIn('TERM_MLAB_POST_INDEPENDENT_VALUE',cpp)
        self.assertIn('65534+frame_index/2',cpp)
        self.assertEqual(m['steps'][0]['expected_stdout'],native.NORMAL)

    def test_fault_contract_separate_and_default_source_exact(self):
        normal,files=native.role()
        fault,other=native.role('faults')
        self.assertEqual(normal['build'],fault['build'])
        self.assertEqual(files,other)
        self.assertEqual(normal['test_role'],'normal')
        self.assertEqual(fault['test_role'],'deliberate_fault')
        self.assertIn('--faults',fault['steps'][0]['argv'])
        self.assertIn('raw_pending_lockstep=1',fault['steps'][0]['expected_stdout'])
        with self.assertRaises(ValueError):native.role(True)

    def test_exact_actual_factored_import_not_uninstantiated_sparse(self):
        from fpga.reference import stream27_context_term_mlab_native_v2 as fixed
        m,files=fixed.role()
        row='rtl/genefer_stream27_row_arithmetic_param_v1.sv'
        self.assertIn('genefer_stream27_montgomery_factored_v1 #',files[row].decode())
        self.assertIn('rtl/genefer_stream27_montgomery_factored_v1.sv',m['build']['sv_sources'])
        self.assertNotIn('rtl/genefer_montgomery_mul27_sparse_pipe.sv',m['build']['sv_sources'])
        for name in (native.CPP,'rtl/'+native.binding.TERM+'.sv','rtl/'+native.binding.NEW+'.sv','rtl/'+native.binding.RAM+'.sv'):
            self.assertEqual(files[name],native.role()[1][name])

    def test_pending_post_not_sampled_registered_error_still_fatal(self):
        from fpga.reference import stream27_context_term_mlab_native_v3 as fixed
        m,files=fixed.role();cpp=files[native.CPP].decode()
        self.assertIn('need(!(d.old_status&24u),"TERM_MLAB_NORMAL_PRE_FAULT")',cpp)
        self.assertIn('need(!(d.old_status&8u),"TERM_MLAB_NORMAL_POST_REGISTERED_FAULT")',cpp)
        self.assertIn('d.old_status==d.new_status',cpp)
        self.assertIn('paired(d,d.pointwise_slot)',cpp)
        self.assertIn('TERM_MLAB_PRE_INDEPENDENT_VALUE',cpp)
        self.assertIn('TERM_MLAB_POST_INDEPENDENT_VALUE',cpp)
        self.assertTrue(m['term_mlab_unit']['POST_pending_not_sampled'])


if __name__=='__main__':unittest.main()
