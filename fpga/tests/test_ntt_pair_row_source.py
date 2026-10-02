"""Independent source-boundary checks for the row decoder; not RTL simulation."""
import hashlib
from pathlib import Path
import re
import unittest
from reference.ntt_pair_row_source import row_source, BASELINE_SHA256, BENCH_SHA256


class RowSourceBoundary(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]
        self.parent=(root/'rtl/kernel/genefer_ntt_banked27_pair_checked_engine.sv').read_text()
        self.new=(root/'rtl/kernel/genefer_ntt_banked27_pair_row_engine.sv').read_text()
        self.oldbench=(root/'rtl/tb/ntt_banked27_pair_checked_engine.cpp').read_text()
        self.newbench=(root/'rtl/tb/ntt_banked27_pair_row_engine.cpp').read_text()

    def test_source_and_bench_ancestry(self):
        self.assertEqual(hashlib.sha256(self.parent.encode()).hexdigest(),BASELINE_SHA256)
        self.assertEqual(hashlib.sha256(self.oldbench.encode()).hexdigest(),BENCH_SHA256)
        self.assertEqual(self.new,row_source(self.parent))
        self.assertEqual(self.newbench,self.oldbench.replace('pair_checked','pair_row').rstrip()+'\n')

    def test_full_address_expansion_is_only_a_simulation_witness(self):
        synth=re.sub(r'// synthesis translate_off.*?// synthesis translate_on','',self.new,flags=re.S)
        self.assertNotIn('bank_address(',synth)
        self.assertNotIn('bf_address',synth)
        self.assertIn('row-only decode identity mismatch',self.new)
        self.assertIn('data_ra[bank]=transform_row[bank]',synth)
        self.assertIn('row_tag[0][b]<=transform_read ? transform_row[b] : data_ra[b]',synth)

    def test_row_group_comes_from_same_read_descriptor(self):
        for text in (self.parent,self.new):
            self.assertIn("state==PAIR_RUN ? 32'(pair_root_group) : group_index",text)
        self.assertIn("assign row_variable=KW'(bank)^base_bank",self.new)
        self.assertIn("assign transform_row[bank]=RW'(base_addr>>KW)",self.new)
        self.assertIn("row_masks[layer]<=((layer==0 || setup_pair) && s>=KW)",self.new)

    def test_fault_guards_and_writeback_remain(self):
        for anchor in ('fault_drain<=7;',
                       "if((single_write || pair_write) && !fault_reg && !fault_now && 32'(bank)<n)",
                       'row_tag[t][b]<=row_tag[t-1][b];',
                       'for(int t=1;t<7;t=t+1)',
                       'point_type_pipe<={point_type_pipe[4:0],mul_in_valid[lane] && !fault_reg && !fault_now}'):
            self.assertIn(anchor,self.parent)
            self.assertIn(anchor,self.new)


if __name__=='__main__':unittest.main()
