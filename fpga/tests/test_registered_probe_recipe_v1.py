from pathlib import Path
import unittest
from fpga.tools import registered_probe_recipe_v1 as r

ROOT=Path(__file__).resolve().parents[1]/'rtl/kernel'

class ProbeRecipeTests(unittest.TestCase):
    def test_matched_shell_diff_is_only_child_choice(self):
        names=list(r.CHILDREN);products=[r.generate((ROOT/(n+'.sv')).read_bytes(),'matched_probe_v1') for n in names]
        self.assertEqual(products[0][0].replace(names[0],names[1]),products[1][0])
        self.assertEqual(products[0][1]['ports'],products[1][1]['ports'])
        self.assertEqual(len(products[0][1]['source_register_anchors']),24)
        self.assertEqual(len(products[0][1]['destination_register_anchors']),21)
    def test_unconditional_all_ports_reset_and_no_added_handshake(self):
        name=next(iter(r.CHILDREN));source,receipt=r.generate((ROOT/(name+'.sv')).read_bytes(),'probe_v1')
        self.assertEqual(source.count('always_ff'),1);self.assertEqual(source.count('if ('),1)
        self.assertIn('.clk(clk)',source);self.assertIn('.rst_n(rst_n)',source)
        self.assertNotIn('launch_clk_q',source);self.assertNotIn('launch_rst_n_q',source)
        for name in receipt['source_register_anchors']:
            self.assertIn(name+" <= '0;",source)
        for name in receipt['destination_register_anchors']:
            self.assertIn(name+" <= '0;",source);self.assertIn(name+' <= child_'+name+'_d;',source)
        self.assertEqual(receipt['request_added_edges'],1);self.assertEqual(receipt['response_added_edges'],1)
    def test_unknown_modified_source_and_names_refuse(self):
        name=next(iter(r.CHILDREN));raw=(ROOT/(name+'.sv')).read_bytes()
        with self.assertRaises(ValueError):r.generate(raw+b'\n','probe')
        for wrapper in ('bad;endmodule','x y',name):
            with self.assertRaises(ValueError):r.generate(raw,wrapper)

if __name__=='__main__':unittest.main()
