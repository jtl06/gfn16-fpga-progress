"""Exact additive source delta, not native proof of the new acknowledgment."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


class SourceDelta(unittest.TestCase):
    def test_only_acceptance_observation_added(self):
        old=(ROOT/'rtl/kernel/genefer_stream27_host_image_rowwrite_v1.sv').read_text()
        new=(ROOT/'rtl/kernel/genefer_stream27_r15_host_image_ack_v1.sv').read_text()
        edits=[('module genefer_stream27_host_image_rowwrite_v1 #(',
                'module genefer_stream27_r15_host_image_ack_v1 #('),
               ('output logic commit_ack,row_write_ack,rejected',
                'output logic commit_ack,row_write_ack,rejected,\n    output logic host_write_ready,host_write_ack'),
               ('wire scalar_fire=host_fire',
                'assign host_write_ready=host_fire;\n    logic host_write_ack_d;\n'
                '    assign host_write_ack=allow_access && host_write_ack_d;\n'
                '    always_ff @(posedge clk or negedge rst_n)begin\n'
                '        if(!rst_n)host_write_ack_d<=0;\n'
                '        else host_write_ack_d<=host_fire && load_we;\n'
                '    end\n    wire scalar_fire=host_fire')]
        for before,after in edits:
            self.assertEqual(old.count(before),1)
            old=old.replace(before,after)
        self.assertEqual(new,old)

    def test_guard_no_image_array_and_exact_grant(self):
        s=(ROOT/'rtl/kernel/genefer_stream27_r15_direct_write_guard_v1.sv').read_text()
        self.assertIn('bank_grant && !peer_port_busy',s)
        self.assertIn('bank_write=word_valid && word_ready && word_good && core_idle',s)
        self.assertIn('WORDS=N+32',s)
        self.assertIn('held_owner==expected_owner',s)
        self.assertNotIn('image[',s)


if __name__=='__main__': unittest.main()
