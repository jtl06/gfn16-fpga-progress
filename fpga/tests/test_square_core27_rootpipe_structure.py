from pathlib import Path
import unittest
from reference.square_core27_rootpipe_structure import core_source, host_source, bench_source, ntt_cycles

ROOT = Path(__file__).resolve().parents[1]


class RootpipeIntegrationStructure(unittest.TestCase):
    def test_exact_core_clone_preserves_outer_controller(self):
        old = (ROOT/'rtl/kernel/genefer_square_core27_stream.sv').read_text()
        new = core_source(old)
        self.assertEqual(new, (ROOT/'rtl/kernel/genefer_square_core27_stream_rootpipe.sv').read_text())
        self.assertEqual(old.removesuffix('\n').split('    always_ff @(posedge clk or negedge rst_n) begin')[1:],
                         new.split('    always_ff @(posedge clk or negedge rst_n) begin')[1:])

    def test_exact_adapter_clone_keeps_host_timing(self):
        old = (ROOT/'rtl/kernel/genefer_ntt_banked27_host_engine.sv').read_text()
        new = host_source(old)
        self.assertEqual(new, (ROOT/'rtl/kernel/genefer_ntt_banked27_host_rootpipe_engine.sv').read_text())
        self.assertEqual(old.split('    localparam int HLW=')[1].split('    genefer_ntt_banked27_engine #')[0],
                         new.split('    localparam int HLW=')[1].split('    genefer_ntt_banked27_rootpipe_engine #')[0])

    def test_bench_keeps_oracle_and_updates_exact_latency(self):
        old = (ROOT/'rtl/tb/square_core27_stream.cpp').read_text()
        new = bench_source(old)
        self.assertEqual(new, (ROOT/'rtl/tb/square_core27_stream_rootpipe.cpp').read_text())
        self.assertIn('d.crt_cycles!=98', new)
        self.assertIn('d.ntt_cycles!=expected_ntt', new)
        self.assertIn('if(!abort_reached || !d.busy || d.done)', new)
        self.assertEqual(old.split('                if(verify)for')[1], new.split('                if(verify)for')[1])

    def test_full_size_delta_is70_not35_against_cached_core(self):
        self.assertEqual(ntt_cycles(16, drain=7), 19743)
        self.assertEqual(ntt_cycles(16), 19813)
        for aw in range(1,17):
            self.assertEqual(ntt_cycles(aw)-ntt_cycles(aw,drain=7),2*(2*aw+3))

    def test_tiny_warm_reservation_keeps_same_combined_latency(self):
        self.assertEqual(ntt_cycles(1,drain=7),52)
        self.assertEqual(ntt_cycles(1),62)
        self.assertEqual(52+108,62+98)

    def test_ancestor_drift_rejected(self):
        old = (ROOT/'rtl/kernel/genefer_square_core27_stream.sv').read_text()
        with self.assertRaises(ValueError):core_source(old.replace('32\'d45971250','32\'d1'))
        with self.assertRaises(ValueError):ntt_cycles(16,lanes=16)


if __name__ == '__main__':unittest.main()
