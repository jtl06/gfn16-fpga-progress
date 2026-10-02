"""Selected-clock source/fixture tests; no native/cloud operations."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from cloud import aws_postfit_t5b_selected9668_m8azn_v3 as w
from tests.test_postfit_crtmont_a1_v1 import fixture, path_fixture

a = w.runner
ARCHIVE = a.FPGA/'results/throughput-20260929/core27-t5b-provisional64-aws-fit-v1'


class SelectedAuditTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()

    def test_exact_derivative_no_refit_or_old_output(self):
        raw = (w.HERE/w.FROZEN).read_bytes()
        source = w.adapted_source(raw)
        self.assertIn("selected_clock','9.668'", source)
        self.assertNotIn('quartus_fit', source)
        self.assertNotEqual(a.OUTPUT, 'core27-t5b-100-audit-m8azn-v1')
        with self.assertRaises(ValueError): w.adapted_source(raw+b'\n')
        tcl = a.tcl_source((a.FPGA/'synthesis/postfit_rootfused85_audit_v1.tcl').read_bytes()).decode()
        self.assertIn('($a1_period != 9.668 && $a1_period != 10)', tcl)
        self.assertIn('-snapshot final', tcl)
        self.assertIn('lappend a1_phases selected_clock', tcl)
        self.assertNotIn('execute_flow', tcl)
        for value in ('9.6', '9.667', '9.7', '10.1', 'nan'):
            with self.assertRaises(ValueError): a.a1.period_value(value)

    def test_prepare_exact_source_terminal_closure_and_no_overwrite(self):
        out = self.root/'packet'; result = a.prepare(out)
        p = json.loads((out/'proposal.json').read_text())
        self.assertEqual((p['mode'], p['period_ns'], p['slot']), ('selected_clock', '9.668', 'b'))
        self.assertEqual(len(p['pinned_files']), 40)
        self.assertFalse(p['promotion_allowed'])
        self.assertEqual(p['policy']['cpus'], list(range(6, 12)))
        a.verify_terminal(ARCHIVE, p)
        with patch.object(a, 'HERE', out): a.verify_proposal(out/'proposal.json', result['proposal_sha256'])
        with self.assertRaises(ValueError): a.prepare(out)

    def positive(self):
        proposal, log = fixture(self.root, 'selected_clock')
        proposal['period_ns'] = '9.668'
        proposal['baseline100'].update(setup=dict(slack_ns=.334), hold=dict(slack_ns=.017), mpw=dict(slack_ns=4.337))
        log = log.replace('11.764\t0\t5.882', '9.668\t0\t4.834')
        for phase in ('baseline100', 'selected_clock'):
            period = 10 if phase == 'baseline100' else 9.668
            slacks = dict(setup=.334 if phase == 'baseline100' else .002, hold=.017, mpw=4.337 if phase == 'baseline100' else 4.171)
            for kind, slack in slacks.items():
                for path in self.root.glob(phase+'-*-'+kind+'-summary.rpt'):
                    path.write_text(f'; kernel_clk ; {slack} ; 0 ; 0 ;\n')
            for path in self.root.glob(phase+'-*-setup-paths.rpt'):
                path.write_text(path_fixture(slacks['setup'], period))
            for path in self.root.glob(phase+'-*-effective.sdc'):
                path.write_text(f'set_time_format -unit ns -decimal_places 3\ncreate_clock -name kernel_clk -period {period} [get_ports {{clk}}]\nderive_clock_uncertainty\nset_false_path -from [get_ports {{rst_n}}]\n')
        return proposal, log

    def test_eight_corner_records_and_selected_clock(self):
        proposal, log = self.positive()
        result = a.a1.parse_results(self.root, log, proposal); a.check_timing(result, self.root)
        self.assertEqual(len(result['baseline100']), 4)
        self.assertEqual(len(result['selected_clock']), 4)
        self.assertEqual(result['supported_audit_clock']['period_ns'], 9.668)
        self.assertTrue(result['supported_audit_clock']['not_proven_highest'])

    def test_negative_selected_or_missing_corner_fails(self):
        proposal, log = self.positive()
        path = next(self.root.glob('selected_clock-*-setup-summary.rpt'))
        path.write_text('; kernel_clk ; -0.001 ; -0.001 ; 1 ;\n')
        with self.assertRaises(ValueError): a.a1.parse_results(self.root, log, proposal)
        path.write_text('; kernel_clk ; 0.001 ; 0 ; 0 ;\n')
        with self.assertRaises(ValueError): a.a1.parse_results(self.root, log.replace('\tBEGIN\tselected_clock\t3', '\tBEGIN\tselected_clock\t2'), proposal)

    def test_negative_reset_or_added_exception_fails(self):
        proposal, log = self.positive(); result = a.a1.parse_results(self.root, log, proposal)
        bad = copy.deepcopy(result)
        next(iter(bad['selected_clock'].values()))['recovery'] = dict(status='measured', slack_ns=-.001, tns_ns=-.001, failing_endpoints=1)
        with self.assertRaises(ValueError): a.check_timing(bad, self.root)
        path = next(self.root.glob('selected_clock-*-effective.sdc')); path.write_text(path.read_text()+'set_false_path -to [all_registers]\n')
        with self.assertRaises(ValueError): a.check_timing(result, self.root)


if __name__ == '__main__': unittest.main()
