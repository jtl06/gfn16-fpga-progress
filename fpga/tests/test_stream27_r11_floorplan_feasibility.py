import unittest
from fpga.reference.stream27_r11_floorplan_feasibility import audit


class SourceFloorplan(unittest.TestCase):
    def test_three_fields_and_generated_spine_source(self):
        result=audit()
        self.assertEqual(result['production_rtl_count'],58)
        self.assertEqual(len(result['three_field_instances']),3)
        self.assertEqual(len(result['central_instance_members']),32)
        self.assertIn('crt_transport_data',result['central_transport_register_bases'])
        self.assertFalse(result['baseline_gate'])
        self.assertFalse(result['DRC_smoke_pass'])
        self.assertFalse(result['optional_ticket_submitted'])
        self.assertIsNone(result['region_shapes'])


if __name__=='__main__':unittest.main()
