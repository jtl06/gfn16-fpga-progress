import copy
import importlib.util
import json
from pathlib import Path
import unittest

FPGA = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_v3_qualified', FPGA/'tools/quartus_prefit_native_v3.py')
native = importlib.util.module_from_spec(spec); spec.loader.exec_module(native)
STAGE = FPGA/'results/throughput-20260929/quartus-prefit-azure-diag-stage-v7'


class ActualNativeQualificationTests(unittest.TestCase):
    def setUp(self):
        self.root = STAGE/'native-collection'
        self.specification = json.loads((STAGE/'payload.json').read_text())['spec']
        self.context = json.loads((self.root/'da-execution-context.json').read_text())
        self.ids = native.identities(self.specification)
        self.raw = dict(self.context['raw_report_sha256'])

    def test_actual_native_inventory_summary_and_unchanged_database(self):
        result = native.receipt(self.root, self.specification, 'da', self.root/'da.log',
                                [self.root/'da/design-assistant-rules.tsv'], 0, self.root/'da-execution-context.json')
        self.assertTrue(result['native_execution_identity_verified'])
        self.assertTrue(result['design_assistant']['passed'])
        self.assertEqual(result['design_assistant']['native_enabled_rules'], 13)
        self.assertEqual(result['design_assistant']['high_severity_findings'], [])
        self.assertIn('LNT-30011', result['design_assistant']['rules_checked'])
        self.assertTrue(self.context['original_tree_unchanged'])
        self.assertFalse(result['cross_block_coverage']['complete'])
        self.assertFalse(result['fit_allowed'])
        self.assertFalse(result['promotion_allowed'])

    def test_actual_context_database_input_and_raw_tampering_block(self):
        cases = []
        database = copy.deepcopy(self.context); database['database_after_sha256'][next(iter(database['database_after_sha256']))] = '0'*64; cases.append(database)
        source = copy.deepcopy(self.context); source['source_after_sha256'][next(iter(source['source_after_sha256']))] = '0'*64; cases.append(source)
        raw = copy.deepcopy(self.context); raw['raw_report_sha256']['da.log'] = '0'*64; cases.append(raw)
        tool = copy.deepcopy(self.context); tool['tool_sha256']['/usr/bin/python3'] = '0'*64; cases.append(tool)
        for context in cases:
            with self.assertRaises(ValueError):
                native.validate_execution(context, self.specification, 'da', self.ids, self.raw, 0)


if __name__ == '__main__':
    unittest.main()
