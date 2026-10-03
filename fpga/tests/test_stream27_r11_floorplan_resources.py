import unittest
from fpga.reference.stream27_r11_floorplan_resources import resources


class Rows(unittest.TestCase):
    def test_exact_native35_disjoint_node_join(self):
        result=resources()
        self.assertTrue(result['source_graph_matches_all35_nodes'])
        self.assertEqual(len(result['field_regions']),3)
        self.assertEqual([row['dsp_blocks'] for row in result['field_regions']],[314,314,314])
        self.assertEqual(result['central32_instance_subtotals']['dsp_blocks'],368)
        self.assertEqual(result['central32_instance_subtotals']['dedicated_logic_registers'],101824)
        self.assertEqual(result['disjoint_selected35_node_subtotals']['dsp_blocks'],1310)
        self.assertEqual(result['plan_matching_resource_rows'],0)
        self.assertFalse(result['region_capacity_proven'])
        self.assertFalse(result['baseline_gate'])


if __name__=='__main__':unittest.main()
