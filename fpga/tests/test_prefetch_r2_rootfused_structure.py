"""Pure source and lane-label mapping tests; never execute an HDL tool."""
import unittest
from pathlib import Path
from fpga.reference import prefetch_r2_rootfused_structure as s

ROOT=Path(__file__).resolve().parents[1]

class RootFusionTests(unittest.TestCase):
    def test_exhaustive_mapping(self):
        # All port-encodable stages/opcodes, both low-stage values, every bank
        # route and lane for every supported power-of-two lane geometry.
        cases=0
        for lanes in (1,2,4,8,16,32,64):
            for stage in range(32):
                for op in range(4):
                    for low in (False,True):
                        for route in range(2*lanes):
                            old,new,formula=s.routes(lanes,stage,op,low,route)
                            self.assertEqual(old,new,(lanes,stage,op,low,route))
                            self.assertEqual(old,formula,(lanes,stage,op,low,route))
                            cases+=lanes
        self.assertEqual(cases,2796032)

    def test_exact_source_delta(self):
        self.assertEqual(len(s.validate_files(ROOT)),3)

    def test_only_combinational_routing_delta(self):
        self.assertNotIn('always_ff',s.NEW)
        self.assertNotIn('generated_roots[(',s.NEW)
        self.assertIn('if(d==0)assign words[j]=generated_roots[j*32+:32];',s.NEW)
        self.assertEqual(s.NEW.count('generated_route[d-1].words'),2)
        self.assertNotIn('<=',s.NEW.replace('d<=LW',''))

    def test_frozen_ancestor_drift_rejected(self):
        original=(ROOT/'rtl/kernel'/(s.ENGINE+'.sv')).read_text()
        with self.assertRaisesRegex(ValueError,'frozen ancestor'):
            s.expected(s.ENGINE,original+'\n')

    def test_wrong_unconditional_xor_is_detectable(self):
        old,new,_=s.routes(64,0,0,True,63)
        self.assertEqual(old,[0]*64)
        self.assertNotEqual(new,[j^63 for j in range(64)])

    def test_wrong_clip_before_routing_order_is_detectable(self):
        old,_,_=s.routes(64,3,0,True,63)
        self.assertNotEqual(old,[(j&7)^63 for j in range(64)])

    def test_non_butterfly_not_clipped(self):
        for op in (1,2,3):
            old,new,_=s.routes(64,0,op,True,63)
            self.assertEqual(old,[j^63 for j in range(64)])
            self.assertEqual(old,new)

if __name__=='__main__':unittest.main()
