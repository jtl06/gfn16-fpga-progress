"""Pure parser/negative-control tests; no vendor tool executes on the Mac."""
import importlib.util
from pathlib import Path
import unittest

FPGA = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('quartus_prefit', FPGA/'tools/quartus_prefit_native_v1.py')
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)
PIN = 'a'*64
VERSION = 'Info: Version 26.1.0 Build 110 SC Pro Edition\n'


def da_log(extra=''):
    return VERSION+f'PREFIT_DA\tREQUIRED\tLNT-30011\thigh\nPREFIT_DA\tIDENTITY\t{PIN}\tsynthesized\tArria10\nPREFIT_DA\tCOMPLETE\t1\n'+extra


def da_report(severity='High', violations=0, waived=0):
    failed = int(violations > waived)
    return f'; Design Assistant (Synthesized) Results - {failed} of 1 Rules Failed ;\n; Rule ; Severity ; Violations ; Waived ; Tags ;\n; LNT-30011 - Design Contains Combinational Loops ; {severity} ; {violations} ; {waived} ; synthesis ;\n'


def timing_report(slack, snapshot='placed'):
    return f'Snapshot:\n    {snapshot}\n; Slack ; {slack:.3f} ;\n'


def timing_log(setup=0.25, hold=0.01):
    corner = 'Slow 900mV 100C Model'.encode().hex()
    return VERSION+f'POSTPLACE\tIDENTITY\t{PIN}\tplaced\tkernel_clk\t10.0\nPOSTPLACE\tCORNER\t0\t{corner}\t0\nPOSTPLACE\tTIMING\t0\tsetup\t1\t{setup}\tcorner-0-setup.rpt\nPOSTPLACE\tTIMING\t0\thold\t1\t{hold}\tcorner-0-hold.rpt\nPOSTPLACE\tCOMPLETE\t1\n'


class DesignAssistantTests(unittest.TestCase):
    def test_clean_synthetic_rule_table(self):
        result = q.parse_da(da_log(), da_report()+'Status:\tPASS\nSeverity:\tHigh\n; LNT-30011 - Design Contains Combinational Loops ;\n', PIN, 0)
        self.assertTrue(result['passed'])
        self.assertEqual(result['rules_checked'], ['LNT-30011'])

    def test_new_high_hit_blocks_even_with_warning_message(self):
        result = q.parse_da(da_log('Warning (1): Rule hit\n'), da_report(violations=1), PIN, 0)
        self.assertTrue(result['complete'])
        self.assertFalse(result['passed'])
        self.assertEqual(result['new_high_severity_findings'][0]['violations'], 1)

    def test_high_waiver_and_unknown_severity_fail_closed(self):
        self.assertFalse(q.parse_da(da_log(), da_report(violations=1, waived=1), PIN, 0)['complete'])
        self.assertFalse(q.parse_da(da_log(), da_report(severity='UNKNOWN'), PIN, 0)['complete'])

    def test_missing_rule_demotion_error_or_truncation_blocks(self):
        cases = [('', da_report(), 0), (da_log(), da_report(severity='Low'), 0),
                 (da_log('ERROR: native error despite rc0\n'), da_report(), 0),
                 (da_log(), da_report().splitlines()[0], 0), (da_log(), da_report(), 124)]
        for log, report, rc in cases:
            with self.subTest(log=log[:10], report=report[:30], rc=rc):
                self.assertFalse(q.parse_da(log, report, PIN, rc)['passed'])

    def test_archived_elaboration_report_is_not_synthesis_gate(self):
        report = (FPGA/'results/audit-opt-20260929/vendor/crt/probe.drc.partitioned.rpt').read_text()
        result = q.parse_da(da_log(), report, PIN, 0)
        self.assertFalse(result['complete'])
        self.assertIn('missing_or_ambiguous_synthesis_rule_summary', result['blockers'])

    def test_native_api_capture_preserves_missing_default_record(self):
        raw = (FPGA/'results/throughput-20260929/quartus-prefit-native-synthesis-rules-v1/synthesis-rules.log').read_text()
        self.assertIn('PREFIT_RECORD\tLNT-30011\t656e61626c65\t31', raw)
        self.assertIn("ERROR: Invalid DRC object 'rule_record:default:LNT-50007", raw)
        self.assertIn('native_error_message', q.native_errors(raw, 0))


class TimingTests(unittest.TestCase):
    def result(self, log=None, setup=0.25, hold=0.01, snapshot='placed'):
        reports = {'corner-0-setup.rpt': timing_report(setup, snapshot),
                   'corner-0-hold.rpt': timing_report(hold, snapshot)}
        return q.parse_postplace(log or timing_log(setup, hold), reports, PIN, 'kernel_clk', 10, 0, 'component_probe')

    def test_clean_diagnostic_stays_scoped(self):
        result = self.result()
        self.assertTrue(result['complete'])
        self.assertTrue(result['selected_clock_setup_hold_nonnegative'])
        for key in ('whole_core_clock_claim', 'routed_clock_qualification', 'pulse_width_checked', 'cross_block_coverage_complete'):
            self.assertFalse(result[key])

    def test_negative_slack_is_complete_but_not_passing(self):
        result = self.result(setup=-5.292)
        self.assertTrue(result['complete'])
        self.assertFalse(result['selected_clock_setup_hold_nonnegative'])

    def test_raw_final_snapshot_cannot_be_relabeled_placed(self):
        self.assertFalse(self.result(snapshot='final')['complete'])

    def test_missing_corner_completion_or_changed_period_blocks(self):
        for log in (timing_log().replace('POSTPLACE\tCOMPLETE\t1\n', ''),
                    timing_log().replace('\tkernel_clk\t10.0', '\tkernel_clk\t8.0'),
                    timing_log().replace('\tkernel_clk\t10.0', '\tkernel_clk\tNaN'),
                    timing_log().replace('POSTPLACE\tTIMING\t0\thold\t1\t0.01\tcorner-0-hold.rpt\n', '')):
            self.assertFalse(self.result(log=log)['complete'])

    def test_real_native_routed_paths_parser_only(self):
        report = (FPGA/'results/throughput-20260929/rootfused85-aws-audit-v1/timing/baseline100-0-setup-paths.rpt').read_text()
        result = q.parse_timing_paths(report)
        self.assertEqual(result['reported_paths'], 1000)
        self.assertEqual(result['worst_slack_ns'], -1.534)
        self.assertEqual(result['snapshot'], 'final')

    def test_explicit_native_command(self):
        command = q.native_argv('postplace', '/opt/quartus/bin', '/tmp/private/probe', 'probe', '/tmp/private/timing', PIN, 'kernel_clk')
        self.assertEqual(command[0], '/opt/quartus/bin/quartus_sta')
        self.assertEqual(command[-2:], [PIN, 'kernel_clk'])
        with self.assertRaises(ValueError):
            q.native_argv('postplace', '/opt/quartus/bin', '/tmp/p', 'probe', '/tmp/o', PIN, '*')


class ExecutionIdentityTests(unittest.TestCase):
    def fixture(self):
        spec = dict(sources={'rtl/probe.sv': 'b'*64}, settings={'probe.qsf': 'c'*64},
                    identity={'top': 'probe', 'device': 'device', 'parameters': {}, 'clock_period_ns': 10, 'seed': 1},
                    vendor_tool_sha256={'quartus_syn': 'd'*64})
        ids = q.identities(spec)
        raw = {'run.log': 'e'*64, 'design-assistant.rpt': 'f'*64}
        context = dict(schema='quartus-prefit-execution-v1', platform='Linux', **ids,
                       tool_sha256=spec['vendor_tool_sha256'], helper_sha256=q.sha(Path(q.__file__).read_bytes()),
                       native_script_sha256=q.sha(q.SCRIPTS['da'].read_bytes()), returncode=0,
                       source_before_sha256=spec['sources'], source_after_sha256=spec['sources'],
                       settings_before_sha256=spec['settings'], settings_after_sha256=spec['settings'],
                       database_before_sha256={'qdb/synthesized.qdb': '9'*64},
                       database_after_sha256={'qdb/synthesized.qdb': '9'*64},
                       raw_report_sha256=raw, owner_admission_passed=True)
        return spec, ids, raw, context

    def test_complete_caller_context_is_required(self):
        spec, ids, raw, context = self.fixture()
        q.validate_execution(context, spec, 'da', ids, raw, 0)
        for key, wrong in [('owner_admission_passed', False), ('platform', 'Darwin'),
                           ('database_after_sha256', {'qdb/synthesized.qdb': '8'*64}),
                           ('source_after_sha256', {}), ('raw_report_sha256', {}),
                           ('tool_sha256', {}), ('helper_sha256', '0'*64)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                q.validate_execution(dict(context, **{key: wrong}), spec, 'da', ids, raw, 0)


if __name__ == '__main__':
    unittest.main()
