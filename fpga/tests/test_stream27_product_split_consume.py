import unittest
from fpga.reference import stream27_product_split as s
from fpga.reference import stream27_product_split_consume as c

class PackingConsumeTests(unittest.TestCase):
    def test_actual_scalar_result_and_refusal(self):
        path=s.ROOT/'queue/standing-fit-state/terminal/s4-product-split-scalar-packing-f0-v1/evidence/project/output_files/probe.fit.rpt'
        raw=path.read_text();v=c.extract(raw)
        self.assertEqual(v['split_lazy']['DSP_output_bits'],54)
        self.assertEqual(v['parent_lazy']['DSP_output_bits'],0)
        self.assertEqual(v['lazy_delta']['dedicated_fabric_registers'],-27)
        self.assertAlmostEqual(v['lazy_delta']['needed_ALM'],2.4)
        self.assertEqual(v['canonical_delta']['dedicated_fabric_registers'],0)
        with self.assertRaises(ValueError):c.extract(raw.replace('split_lazy|core','unknown_lazy|core'))
        with self.assertRaises(ValueError):c.extract(raw.replace('Fixed Point DSP Register Packing Details','unknown panel'))
    def test_actual_matched_parent_mapping_not_uniform(self):
        path=s.ROOT/'queue/standing-fit-state/terminal/s4-l3b-ct-composed-field-parent-f0-v1/evidence/project/output_files/probe.fit.rpt'
        v=c.field_extract(path.read_text())
        self.assertEqual(v['DSP_rows'],314);self.assertEqual(v['parent_ab_s1_DSP_output_rows'],74)
        self.assertEqual(v['parent_ab_s1_DSP_output_bits'],74*54)
        self.assertEqual(v['unregistered_DSP_output_rows'],240)
        self.assertEqual(v['leaf_entities']['genefer_stream27_montgomery_factored_core_v1']['instances'],314)
        with self.assertRaises(ValueError):c.output_bits('unrecognized native format')

if __name__=='__main__':unittest.main()
