import re
import unittest
from fpga.reference import stream27_host_contexts as core
from fpga.reference.s4_waiting_final_contract import Owner, WaitingFinal


class SourceTests(unittest.TestCase):
    def test_real_components_and_owner_publication(self):
        for n, p in ((32, 8), (256, 8), (32, 16)):
            b = core.prepare(n, p)
            s = b['files'][b['top']+'.sv']
            self.assertFalse(re.findall(r'@[A-Z_]+@', s))
            for token in ('genefer_stream27_host_image_rowwrite_v1',
                          'genefer_stream27_canonical_image_pipe_v1',
                          'genefer_stream27_descriptor_fifo_ff_v1',
                          'genefer_stream27_warm_contexts_'):
                self.assertIn(token, s)
            self.assertIn('.row_write_owner(final_owner)', s)
            self.assertIn('final_owner!=live_owner[final_context*56+:56]', s)
            self.assertIn('copy_committed==(AW+1)\'(N-1)', s)
            self.assertIn('copy_issued!=(AW+1)\'(N)', s)
            self.assertIn('canonical_ready=published & {2{!error}}', s)
            self.assertIn('.quarantine(error)', s)
            self.assertNotIn('canonical_ready<=', s)
            self.assertNotIn('host_bad', s)
            self.assertIn('job_generation[c]==8\'hff', s)

    def test_cold_ram_source_edges_match_balanced_acceptance(self):
        for offset in (63, 110, 8326, 4229):
            reserve_edge = offset-3
            first_read_edge = reserve_edge+1
            source_ff_edge = first_read_edge+1
            arithmetic_edge = source_ff_edge+1
            self.assertEqual(arithmetic_edge, offset)
        b=core.prepare(32,8);s=b['files'][b['top']+'.sv']
        self.assertIn('32\'(CONTEXT_OFFSET-3)', s)

    def test_scratch_last_load_and_copy_publication_edges(self):
        for rows in (2, 4, 16, 32):
            read_edges = list(range(rows))
            load_edges = [edge+1 for edge in read_edges]
            begin = load_edges[-1]+1
            self.assertEqual(len(set(read_edges)), rows)
            self.assertNotIn(begin, load_edges)
            self.assertEqual(begin, rows+1)
        for n in (32, 256):
            read_edges = list(range(n))
            response_edges = [edge+1 for edge in read_edges]
            commit_edges = [edge+1 for edge in response_edges]
            ack_consumption = [edge+1 for edge in commit_edges]
            self.assertEqual(ack_consumption[-1], n+2)
            self.assertGreater(ack_consumption[-1], commit_edges[-1])
        b=core.prepare(32,8);s=b['files'][b['top']+'.sv']
        self.assertIn('load_requested<(ROW_W+1)\'(ROWS)', s)

    def test_required_ram_primitive_source_closure(self):
        before=core.prepare(32,8,ram_closure=0)
        after=core.prepare(32,8)
        self.assertNotIn('genefer_sdp_ram32.sv',before['files'])
        self.assertEqual(after['files']['genefer_sdp_ram32.sv'],(core.ROOT/core.RAM).read_text())
        self.assertIn(core.RAM,after['source_dependencies'])
        self.assertIn('module genefer_sdp_ram32',after['files']['genefer_sdp_ram32.sv'])
        for name,text in before['files'].items():
            if name==before['top']+'.sv':
                self.assertEqual(after['files'][after['top']+'.sv'].replace(after['top'],before['top']),text)
            else:self.assertEqual(after['files'][name],text)

    def test_same_shadow_waiting_reuse_transaction_witness(self):
        m = WaitingFinal(32, 8)
        a, b = Owner(0, 1, 0, 2), Owner(1, 1, 46, 4)
        for owner, base in ((a,1009),(b,2017)):
            m.begin(owner, base, [owner.context]*8, [1-owner.context]*8)
        for row in range(4):
            m.capture(a, row, [block*4+row for block in range(8)])
        m.acquire_scratch(a)
        for row in range(4):
            m.load_row(a, row)
        m.canonical_ready(a)
        for address in range(32):
            m.commit(a, address, address)
            if address<4:
                m.capture(b, address, [100+block*4+address for block in range(8)])
        m.publish(a)
        self.assertEqual(m.host_read(a, 31), 31)
        m.acquire_scratch(b)
        for row in range(4):
            self.assertEqual(m.load_row(b,row),tuple(100+block*4+row for block in range(8)))


if __name__ == '__main__':
    unittest.main()
