import unittest
from fpga.reference import a10_upper_sum_generate_v2 as gen


class UpperSumSource(unittest.TestCase):
    def test_measured_source_cone_and_exact_narrow_delta(self):
        ledger = gen.measured_guard()
        self.assertEqual(ledger['setup']['paths'][0]['slack_ns'], -2.522)
        source = gen.cell_source()
        self.assertEqual((gen.ROOT/gen.TARGET).read_text(), source)
        restored = source
        for old, new in reversed(gen.changes()):
            restored = restored.replace(new, old)
        self.assertEqual(restored, (gen.ROOT/gen.PARENT).read_text())
        self.assertEqual(len(gen.changes()), 10)

    def test_engine_only_cell_binding_no_counter_route_change(self):
        self.assertEqual((gen.ROOT/gen.ENGINE).read_text(), gen.engine_source())
        source = gen.engine_source().replace('genefer_a10_canonical_butterfly_sumlaunch_v2 #',
                                             'genefer_a10_canonical_butterfly_v1 #')
        self.assertEqual(source, (gen.ROOT/gen.POINT).read_text())

    def test_latency_alignment_bubbles_reset_symbolic_only(self):
        ledger = gen.ledger()
        self.assertEqual(ledger['old_upper']['alignment_capture'][-1], 5)
        self.assertEqual(ledger['new_upper']['alignment_capture'][-1], 5)
        self.assertEqual(ledger['shared_lower']['output_capture'], 5)
        # Token ledger with irregular gaps; reset cancels ALL prior tokens,
        # including request-specific normalization. This is not RTL execution.
        for reset_edge in range(7):
            requests = {edge: (edge, edge*31+17) for edge in (0,1,3,6,7,10)}
            before = {edge+5: token for edge,token in requests.items() if edge < reset_edge}
            after = {edge+5: token for edge,token in requests.items() if edge > reset_edge}
            committed = {edge: token for edge,token in before.items() if edge < reset_edge}
            committed.update(after)
            self.assertTrue(all(token[0]+5 == edge for edge,token in committed.items()))
        self.assertEqual((ledger['engine_cycle_delta'], ledger['valid_register_count_delta']), (0,0))
        self.assertFalse(ledger['native_verified'])


if __name__ == '__main__':
    unittest.main()
