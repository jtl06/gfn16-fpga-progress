import unittest
from fpga.reference import anext_hostcut_source_v1 as s
class Hostcut(unittest.TestCase):
    def test_exact_binding(self):
        s.verify();t=s.expected()['rtl/kernel/genefer_anext_hostcut_core_v1.sv']
        self.assertIn('genefer_anext_upper_square_backend_v1',t)
        self.assertIn('genefer_anext_cancel_host_shell_v1',t)
        self.assertNotIn('writeback',t)
    def test_no_cycle_contract_delta(self):
        for name in ('reference/anext_upper_output_v1.py','reference/anext_upper_representative_output_v1.py'):
            self.assertEqual(s.expected()[s.rename(name)].replace("candidate='A-next-hostcut-v1'","candidate='A-next-upper-v1'"),(s.ROOT/name).read_text())
    def test_caller_immediate_kill_unchanged(self):
        t=(s.ROOT/'rtl/kernel/genefer_anext_upper_square_backend_v1.sv').read_text()
        for n in ('compute_write_en=image_write_valid[1] && !fault && !child_cancel;','compute_boundary_commit=image_boundary_valid[1] && !fault && !child_cancel;'):self.assertIn(n,t)
        seq=(s.ROOT/'rtl/kernel/genefer_anext_upper_ntt_sequencer_v1.sv').read_text();self.assertIn('wire children_rst_n=rst_n && !cancel && state!=FAILED;',seq)
if __name__=='__main__':unittest.main()
