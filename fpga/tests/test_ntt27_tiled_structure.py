"""Static wiring/attribute checks; these do not assert physical preservation."""
from pathlib import Path
import unittest
from reference.ntt27_tiled_structure import validate,geometry,validate_files


class TileStructure(unittest.TestCase):
    def setUp(self):
        self.root=Path(__file__).resolve().parents[1]
        self.ancestor=(self.root/'rtl/kernel/genefer_ntt_banked27_folded_engine.sv').read_text()
        self.candidate=(self.root/'rtl/kernel/genefer_ntt_banked27_tiled_engine.sv').read_text()

    def test_exact_control_only_clone(self):
        self.assertEqual(validate_files(self.root)['status'],'passed')

    def test_tile_counts(self):
        self.assertEqual(geometry(64)['declared_register_bits'],112)
        self.assertEqual(geometry(64)['added_register_bits'],98)
        self.assertEqual(geometry(16)['added_register_bits'],12)
        for n in (1,2,4,8,16,32,64):
            g=geometry(n)
            self.assertEqual(g['tile_lanes']*g['tiles'],n)
            self.assertEqual(g['tile_banks']*g['tiles'],2*n)
            self.assertEqual(g['latency_delta'],0)
        for n in (0,3,128,True,16.0):
            with self.assertRaises(ValueError):geometry(n)

    def test_nonfunctional_physical_intent_mutants_are_rejected(self):
        # These can be arithmetic-equivalent, so an RTL oracle alone cannot
        # prove that every destination uses its intended independent replica.
        changes=[('preserve, dont_merge','preserve'),
                 ('preserve, dont_merge','dont_merge'),
                 ('control_tiles[lane/TILE_LANES]','control_tiles[0]'),
                 ('control_tiles[b/TILE_BANKS]','control_tiles[0]'),
                 ('TILE_LANES=LANES<8 ? LANES : 8','TILE_LANES=LANES'),
                 ('pairing_e<=0;orientation_e<=0;',"pairing_e<='1;orientation_e<=0;")]
        for old,new in changes:
            self.assertIn(old,self.candidate)
            with self.subTest(old=old),self.assertRaises(ValueError):
                validate(self.ancestor,self.candidate.replace(old,new))

    def test_timing_and_data_mutations_rejected(self):
        for old,new in [('pairing_e<=pairing_d','pairing_e<=pairing'),
                        ('rotation_d<=rotation','rotation_d<=0'),
                        ('data_route_q[b]<=data_q[b]','data_route_q[b]<=data_q[b^1]'),
                        ('row_tag[7][bank]','row_tag[6][bank]')]:
            self.assertIn(old,self.candidate)
            with self.subTest(old=old),self.assertRaises(ValueError):
                validate(self.ancestor,self.candidate.replace(old,new))


if __name__=='__main__':unittest.main()
