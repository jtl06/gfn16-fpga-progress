import importlib.util
from pathlib import Path
import unittest

FPGA = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('quartus_prefit_cdb', FPGA/'tools/quartus_prefit_native_v2.py')
q = importlib.util.module_from_spec(spec); spec.loader.exec_module(q)


class CdbAdapterTests(unittest.TestCase):
    def test_cdb_only_changes_da_loader_executable(self):
        command = q.native_argv('da', '/opt/quartus/bin', '/tmp/private/probe', 'probe', '/tmp/private/da', 'a'*64)
        self.assertEqual(command[0], '/opt/quartus/bin/quartus_cdb')
        self.assertEqual(command[1], '-t')
        self.assertEqual(q.sha(q.SCRIPTS['da'].read_bytes()), 'd46d35cfd37e93879a7ed7c9d1539e61a5a0abe0abfd8889e2229e8bfbb638e1')

    def test_real_native_failure_is_never_design_rule_pass(self):
        log = (FPGA/'results/throughput-20260929/quartus-prefit-azure-diag-stage-v1/native-collection/da.log').read_text()
        result = q.parse_da(log, '', 'a'*64, 2)
        self.assertFalse(result['passed'])
        self.assertFalse(result['complete'])
        self.assertIn('native_returncode_2', result['blockers'])

    def test_vendor_cdb_package_help_is_captured(self):
        log = (FPGA/'results/throughput-20260929/quartus-prefit-azure-diag-stage-v1/cdb-api-help.log').read_text()
        self.assertIn('Running Quartus Prime Compiler Database Interface', log)
        self.assertIn('Usage: design::load_design', log)
        self.assertIn('Usage: drc::check_design', log)
        self.assertNotRegex(log, r'(?m)^ERROR:')


if __name__ == '__main__':
    unittest.main()
