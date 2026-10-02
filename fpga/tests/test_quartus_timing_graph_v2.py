import importlib.util
from pathlib import Path
import unittest

FPGA = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('timing_graph_v1', FPGA/'tools/quartus_timing_graph_v2.py')
native = importlib.util.module_from_spec(spec); spec.loader.exec_module(native)
DESIGN = 'a'*64


def fixture():
    rows = [f'QUARTUS_NODE_EDGE_V1\tfinal\t{DESIGN}',
            'OPTIONS\tget_nodes:*:include_duplicates\tfanout_edges,fanout_synch_edges,fanout_asynch_edges,fanout_clock_edges\tread_sdc:unchanged\tnode_cap:250000\tedge_cap:1000000',
            'BEGIN\t3\t2\t3', 'NODE\t0\tport\t636c6b', 'NODE\t1\treg\t7231', 'NODE\t2\treg\t7232']
    for node in ('0', '1', '2'):
        for query in ('fanout_edges', 'fanout_synch_edges', 'fanout_asynch_edges', 'fanout_clock_edges'):
            rows.append(f'QUERY\t{node}\t{query}\t'+('1' if query == 'fanout_edges' and node in ('0', '1') else '0'))
    rows += ['EDGE\te0\t0\t1\tclock\t1', 'EDGE\te1\t1\t2\tasynchronous\t0',
             'REGISTER\t1', 'REGISTER\t2', 'KEEPER\t0', 'KEEPER\t1', 'KEEPER\t2', 'END\t3\t2\t0']
    log = f'Info: {native.base.VERSION} Pro Edition\nNODE_GRAPH\tIDENTITY\t{DESIGN}\tfinal\nNODE_GRAPH\tCOLLECTION_COUNT\tnodes\t3\nNODE_GRAPH\tCOLLECTION_COUNT\tregisters\t2\nNODE_GRAPH\tCOLLECTION_COUNT\tkeepers\t3\nNODE_GRAPH\tCOMPLETE\t3\t2\n'
    return log, '\n'.join(rows)+'\n'


class GraphParserTests(unittest.TestCase):
    def test_complete_synthetic_graph_retains_disabled_clock_async_and_nonreg_keeper(self):
        log, report = fixture(); graph = native.parse(log, report, DESIGN, 'final', 0)
        self.assertTrue(graph['complete'], graph['blockers'])
        self.assertEqual(graph['disabled_edges'], 1)
        self.assertEqual(graph['edge_type_counts']['clock'], 1)
        self.assertEqual(graph['edge_type_counts']['asynchronous'], 1)
        self.assertIn('0', graph['keepers'])
        self.assertEqual(graph['nodes']['0']['type'], 'port')
        self.assertFalse(graph['cross_block_coverage_complete'])
        self.assertFalse(graph['fit_allowed'])

    def test_missing_endpoint_duplicate_edge_and_truncation_block(self):
        log, report = fixture()
        for bad in (report.replace('e1\t1\t2', 'e1\t1\tUNKNOWN'), report.replace('END\t3\t2\t0', 'EDGE\te1\t1\t2\tclock\t0\nEND\t3\t2\t0'),
                    report.rsplit('END', 1)[0], report.replace('QUERY\t2\tfanout_edges\t0\n', '')):
            self.assertFalse(native.parse(log, bad, DESIGN, 'final', 0)['complete'])

    def test_register_membership_disagreement_reported_not_assumed_away(self):
        log, report = fixture(); graph = native.parse(log, report.replace('NODE\t2\treg', 'NODE\t2\tpin'), DESIGN, 'final', 0)
        self.assertEqual(graph['register_membership_discrepancy']['register_not_node_reg'], ['2'])
        self.assertFalse(graph['cross_block_coverage_complete'])

    def test_wrong_snapshot_native_error_and_missing_completion_block(self):
        log, report = fixture()
        self.assertFalse(native.parse(log, report, DESIGN, 'synthesized', 0)['complete'])
        self.assertFalse(native.parse(log+'Error (1): Unsupported\n', report, DESIGN, 'final', 2)['complete'])
        self.assertFalse(native.parse(log.replace('NODE_GRAPH\tCOMPLETE\t3\t2', ''), report, DESIGN, 'final', 0)['complete'])


if __name__ == '__main__':
    unittest.main()
