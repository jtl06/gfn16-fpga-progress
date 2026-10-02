import itertools
import unittest
from fpga.reference import stream27_context_term_mlab_bind_v2 as binding
from fpga.reference import stream27_context_term_mlab_native_v4 as native


class TermMlabResetTests(unittest.TestCase):
    def test_write_truth_table_matches_original_reset_else(self):
        differences=[]
        for rst,stop,product,owner in itertools.product((False,True),repeat=4):
            ff_write=rst and not stop and product and owner
            v1_write=not stop and product and owner
            v2_write=rst and not stop and product and owner
            self.assertEqual(ff_write,v2_write)
            if ff_write!=v1_write:differences.append((rst,stop,product,owner))
        self.assertEqual(differences,[(False,False,True,True)])

    def test_guard_only_candidate_source_delta_default_exact(self):
        for stage in ('aw8','full'):
            _,_,p=binding.captured.capture(stage);p=binding.captured.binder.bind(p,enabled=1)
            self.assertEqual(binding.bind(p),p)
            old=binding.parent.bind(p,enabled=1);new=binding.bind(p,enabled=1)
            for name,text in old['files'].items():
                if name==binding.NEW+'.sv':
                    self.assertEqual(new['files'][name].replace('payload_write=rst_n && !stop','payload_write=!stop'),text)
                else:self.assertEqual(new['files'][name],text)
            self.assertTrue(new['term_mlab']['write_reset_else_exact'])

    def test_actual_unit_has_pending_write_and_numeric_retention_check(self):
        m,f=native.role('faults');cpp=f[native.base.parent.CPP].decode()
        self.assertIn('d.rst_n=0;d.clk=1;d.eval()',cpp)
        self.assertIn('d.debug_product_slot&&d.debug_old_write&&d.debug_new_write',cpp)
        self.assertIn('lane_get(d.old_current,lane)==before[lane]&&lane_get(d.new_current,lane)==before[lane]',cpp)
        self.assertIn('simultaneous_reset_write_hold=1',m['steps'][0]['expected_stdout'])
        self.assertTrue(m['term_mlab_unit']['explicit_reset_ELSE_write_guard'])


if __name__=='__main__':unittest.main()
