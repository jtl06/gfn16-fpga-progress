import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

FPGA = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, FPGA/path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


q = load('tools/quartus_prefit_native_v3.py', 'native_da3')
a = load('cloud/azure_prefit_diagnostic_v3.py', 'azure_da3')
COLLECTION = FPGA/'results/throughput-20260929/quartus-prefit-azure-diag-stage-v4/native-collection'


def inventory():
    return 'PREFIT_DA_RULES_V1\nLNT-30011\thigh\n'+''.join(f'LNT-{10000+i}\tlow\n' for i in range(9))+''.join(f'LNT-{20000+i}\tmedium\n' for i in range(3))


def message_db(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE hierarchy (parent_id INTEGER,child_id INTEGER PRIMARY KEY)')
        connection.execute('CREATE TABLE messages (sequence_id INTEGER PRIMARY KEY,message_id INTEGER,time TEXT NOT NULL,source TEXT NOT NULL,type TEXT NOT NULL,text TEXT NOT NULL,flag INTEGER,suppressible INTEGER,file TEXT,line INTEGER,location TEXT)')
        connection.execute('CREATE TABLE tag_types (tag_type TEXT)')
        connection.execute('CREATE TABLE tags (message_id INTEGER,tag TEXT NOT NULL,value TEXT NOT NULL)')


class NativeSummaryTests(unittest.TestCase):
    def setUp(self):
        self.log = (COLLECTION/'da.log').read_text()
        self.identity = json.loads((COLLECTION/'da-execution-context.json').read_text())['design_sha256']

    def test_actual_native_zero_violation_summary_with_synthetic_inventory_counts(self):
        result = q.parse_da(self.log, inventory(), self.identity, 0)
        self.assertTrue(result['passed'])
        self.assertEqual(result['native_enabled_rules'], 13)

    def test_truncated_rule_inventory_or_severity_summary_blocks(self):
        self.assertFalse(q.parse_da(self.log, inventory().replace('LNT-30011\thigh\n', ''), self.identity, 0)['passed'])
        self.assertFalse(q.parse_da(self.log.replace('0 of 1 High severity', '0 of 0 High severity'), inventory(), self.identity, 0)['passed'])

    def test_high_hit_blocks_and_waiver_unknown_blocks(self):
        failing = self.log.replace('13 of 13 enabled', '12 of 13 enabled').replace('0 of 1 High severity', '1 of 1 High severity')
        result = q.parse_da(failing, inventory(), self.identity, 0)
        self.assertTrue(result['complete']); self.assertFalse(result['passed'])
        self.assertFalse(q.parse_da(self.log.replace('Info: No waiver waived any violations', ''), inventory(), self.identity, 0)['complete'])

    def test_real_private_change_was_only_new_message_output(self):
        context = json.loads((COLLECTION/'da-execution-context.json').read_text())
        before, after = context['database_before_sha256'], context['database_after_sha256']
        self.assertEqual(set(after)-set(before), {a.MESSAGE_PATH})
        self.assertEqual({k: after[k] for k in before}, before)


class NarrowOutputTests(unittest.TestCase):
    def test_actual_native_message_file_matches_classification(self):
        actual = COLLECTION/'generated-probe.cdb.qmsgdb'
        self.assertEqual(a.digest(actual), '40e38f67965e149a74c8df5f68c433a80164f7bccc4261ba50d5940fed53ae74')
        a.validate_message_output(actual)

    def test_only_exact_captured_message_schema_is_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            node = root/'qdb/root/netlist.atom.cdb'; node.parent.mkdir(parents=True)
            node.write_bytes(b'compiled-netlist')
            before = a.database(root)
            message_db(root/a.MESSAGE_PATH)
            self.assertEqual(a.database(root), before)
            node.write_bytes(b'tampered-netlist')
            self.assertNotEqual(a.database(root), before)
            with sqlite3.connect(root/a.MESSAGE_PATH) as connection:
                connection.execute('CREATE TABLE unexpected_design_table (payload BLOB)')
            with self.assertRaises(ValueError):
                a.database(root)

    def test_other_message_basename_is_not_exempt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            message_db(root/'qdb/unexpected.qmsgdb')
            self.assertIn('qdb/unexpected.qmsgdb', a.database(root))


if __name__ == '__main__':
    unittest.main()
