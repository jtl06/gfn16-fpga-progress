import unittest
from fpga.reference.anext_writeback_contract_v2 import schedule
from fpga.reference.anext_writeback_contract_v1 import schedule as old
class ExactStageLedger(unittest.TestCase):
    def test_counts(self):
        for aw,transform,point in ((5,55,10),(8,96,13),(16,8352,1033)):
            r=schedule(aw);p=old(aw)
            self.assertEqual((r['transform_engine_cycles'],r['point_engine_cycles']),(transform,point))
            self.assertEqual(r['ntt_controller_cycles'],2*transform+point+6)
            for k in p:
                if k!='transform_engine_cycles':self.assertEqual(r[k],p[k])
if __name__=='__main__':unittest.main()
