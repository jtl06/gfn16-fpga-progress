import unittest
from fpga.reference.stream27_p16a_native_v1 import CALENDAR,footer_counts,verify_parent
from fpga.reference.stream27_field_probe_variants_v1 import compile_probe
from fpga.reference.stream27_field_compile_param_v1 import topology


class P16aNativeSourceTests(unittest.TestCase):
    def test_exact_existing_parent(self):
        parent=verify_parent()
        self.assertEqual(parent['calendar']['first_physical_output'],8417)
        self.assertEqual(parent['calendar']['last_terminal_sample'],12513)
        self.assertIn('legacy P2 same-edge',parent['fault_contract'])

    def test_distinct_calendar_and_structure(self):
        bundle=compile_probe(64,0,16,False)
        self.assertEqual(topology(64,16)['first_output_edge'],40)
        self.assertEqual(topology(64,16,inverse=True)['first_output_edge'],40)
        self.assertEqual(bundle['calendar'],CALENDAR)
        self.assertEqual(len(bundle['files']),10)
        text=bundle['files'][bundle['top']+'.sv']
        self.assertIn('T=4,ROW_W=2,COUNT_W=3',text)
        self.assertIn('[431:0] data_in',text)
        self.assertIn('fused_untwist_normalize',text)
        self.assertNotIn('lean',text)
        self.assertEqual(bundle['resource_basis']['small_M20K_arrays_replaced'],0)

    def test_independent_event_counts(self):
        self.assertEqual(footer_counts(),dict(events=33463,physical=830,eligible=66,
                                             resets=406,aborts=99,faults=4))


if __name__=='__main__':unittest.main()
