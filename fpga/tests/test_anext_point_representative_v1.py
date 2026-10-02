import unittest
from fpga.reference import anext_point_representative_v1 as m
class Representative(unittest.TestCase):
    def test_exact_bench_and_parser_delta(self):
        for path,text in m.expected().items():self.assertEqual((m.ROOT/path).read_text(),text)
        self.assertNotIn('genefer_anext_core_v1',m.expected()[m.CPP])
        self.assertIn('anext_point_contract_v1',m.expected()[m.OUTPUT])
if __name__=='__main__':unittest.main()
