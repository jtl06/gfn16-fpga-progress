import unittest
from fpga.reference import anext_writeback_source_v1 as source
from fpga.reference.anext_writeback_contract_v1 import schedule
from fpga.reference.anext_point_contract_v1 import schedule as parent
class Writeback(unittest.TestCase):
    def test_delta(self):
        self.assertEqual(len(source.changes()),10);source.verify()
        text=source.expected()['rtl/kernel/genefer_anext_writeback_block_engine_v1.sv']
        for key in ('block_bad_word','block_external_conflict','block_read_valid','write_launch_row','write_launch_word','bf_writeback_valid','mul_writeback_valid'):self.assertIn(key,text)
        self.assertIn('state==IDLE ? data_we[bank]',text)
    def test_cycle_ledger(self):
        for aw,ntt in ((5,126),(8,211),(16,17743)):
            p=parent(aw);s=schedule(aw);self.assertEqual(s['ntt_controller_cycles'],ntt)
            for k in ('warm_backend','warm_host','cold_cached_backend','cold_loaded_backend'):self.assertEqual(s[k]-p[k],2*aw+1)
            for k in ('post_child_cycles','cold_prefill_child_cycles'):self.assertEqual(s[k],p[k])
    def test_illegal_cycle_contract(self):
        with self.assertRaises(ValueError):schedule(16,block_response_edges=2)
if __name__=='__main__':unittest.main()
