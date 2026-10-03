import unittest
from fpga.reference import stream27_r15_compute_healthy_join as p


class Healthy(unittest.TestCase):
    def test_source_scalar_only(self):
        b,pins=p.source();g=b['geometry']
        c=p.calendar(g,2)
        self.assertEqual(c['warm_edges'],[21224,25454])
        self.assertEqual(c['publication_edges'],[680689,1340153])
        self.assertEqual(c['full_read_completion_cycles'],1405689)
        sample=p.calendar(g,p.K)
        self.assertEqual(sample['pair_completion_cycles'],16177181485)
        self.assertFalse(sample['source_ready'])
        self.assertTrue(sample['conditional_model_only'])


if __name__=='__main__':unittest.main()
