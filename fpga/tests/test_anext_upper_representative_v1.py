import unittest
from fpga.reference import anext_upper_representative_v1 as m
class Representative(unittest.TestCase):
    def test_exact_top_binding_and_cycle_parser(self):
        for path,text in m.expected().items():self.assertEqual((m.ROOT/path).read_text(),text)
        self.assertIn('anext_point_contract_v1',m.expected()[m.OUTPUT])
        self.assertNotIn('genefer_anext_point_core_v1',m.expected()[m.CPP])
if __name__=='__main__':unittest.main()
