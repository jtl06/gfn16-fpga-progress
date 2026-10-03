import unittest
from reference import stream27_r15_qsys_source_v3 as m

class SourceInput(unittest.TestCase):
    def test_exact_single_source_delta(self):
        meta,files=m.inputs()
        self.assertEqual(meta['source_delta']['changed_files'],[m.GUARD])
        self.assertEqual(len(files),74)
        self.assertEqual(meta['system_top'],'r15_pcie_system_v2')
        self.assertEqual(meta['source_delta']['minimum_downstream_response_edges'],1)
        self.assertIn(b'wire response_credit=(rd_expected!=0);',files[m.GUARD])
        self.assertNotIn(b'wire response_credit=(rd_expected!=0) || down_rd_fire;',files[m.GUARD])
    def test_existing_output_refused(self):
        with self.assertRaisesRegex(ValueError,'FRESH_PRIVATE_OUTPUT'):m.prepare(m.PARENT)

if __name__=='__main__':unittest.main()
