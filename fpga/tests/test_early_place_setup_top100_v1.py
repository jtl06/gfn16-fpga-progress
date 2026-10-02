"""Finite native-format fixtures and tamper controls; no Quartus on this host."""
import importlib.util
from pathlib import Path
import unittest

FPGA = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('early_place', FPGA/'tools/early_place_setup_top100_v1.py')
q = importlib.util.module_from_spec(spec); spec.loader.exec_module(q)
PIN = 'a'*64
CLOCK = 'kernel_clk'
CORNER = 'Slow 900mV 100C Model'


def hx(value):
    return value.encode().hex()


def fixture():
    rows = [f'QUARTUS_EARLY_SETUP_TOP100_V1\t{PIN}\tplaced\t{hx(CLOCK)}\t10.0\tns',
        'OPTIONS\tsetup\tnpaths:100\tselected_clock_both_ends\tpoints:path_only\tnon_exhaustive',
        f'CORNER\t0\t{hx(CORNER)}\t0\tns\t10.0',
        'QUERY\t0\t100\t2\t-0.25\tcorner-0-setup100.rpt']
    for rank, slack in enumerate((-0.25, 0.125)):
        source = [hx('producer|out'), 'reg', hx('producer|out'), hx('cell'), hx('dffeas')]
        dest = [hx('consumer|in'), 'reg', hx('consumer|in'), hx('cell'), hx('dffeas')]
        rows.append('\t'.join(['PATH', '0', str(rank), str(slack), *source, *dest,
            hx(CLOCK), hx(CLOCK), '0.0', '10.0', '10.0', '1', '1', '0', '0', hx(CORNER), '2']))
        for ordinal, metadata in enumerate((source, dest)):
            rows.append('\t'.join(['POINT', '0', str(rank), str(ordinal), *metadata, hx('REG')]))
        rows.append(f'ENDPATH\t0\t{rank}\t2')
    rows += ['ENDCORNER\t0\t2', f'CORNER\t1\t{hx("Fast hold-only")}\t1\tns\t10.0', 'COMPLETE\t2\t1']
    log = ('Info: Version 26.1.0 Build 110 SC Pro Edition\n'+
        f'EARLY_SETUP\tIDENTITY\t{PIN}\tplaced\t{hx(CLOCK)}\t10.0\tns\n'+
        'EARLY_SETUP\tCOMPLETE\t2\t1\n')
    reports = {'corner-0-setup100.rpt': 'Snapshot:\nplaced\n; Slack ; -0.250 (VIOLATED) ;\n; Slack ; 0.125 (MET) ;\n'}
    return log, '\n'.join(rows)+'\n', reports


class ParseTests(unittest.TestCase):
    def parse(self, log=None, table=None, reports=None, rc=0):
        original = fixture()
        return q.parse(log if log is not None else original[0], table if table is not None else original[1],
            reports if reports is not None else original[2], PIN, CLOCK, 10, rc)

    def test_complete_finite_capture_preserves_registered_negative_positive(self):
        result = self.parse()
        self.assertTrue(result['complete'], result['blockers'])
        self.assertEqual(len(result['paths']), 2)
        self.assertEqual([path['slack_ns'] for path in result['paths']], [-.25, .125])
        self.assertEqual(result['paths'][0]['source']['type'], 'reg')
        self.assertEqual(result['paths'][0]['clock_relationship_ns'], 10)
        self.assertEqual(len(result['paths'][0]['arrival_points']), 2)
        for flag in ('exhaustive_cross_block_coverage', 'native_execution_identity_verified', 'fit_allowed', 'promotion_allowed', 'whole_core_clock_claim'):
            self.assertFalse(result[flag])

    def test_actual_native_final_report_cannot_be_relabelled(self):
        reports = dict(fixture()[2]); reports['corner-0-setup100.rpt'] = reports['corner-0-setup100.rpt'].replace('\nplaced\n', '\nfinal\n')
        self.assertFalse(self.parse(reports=reports)['complete'])

    def test_table_clock_period_units_scope_or_identity_tamper_blocks(self):
        table = fixture()[1]
        for bad in (table.replace(PIN, 'b'*64), table.replace('\tplaced\t', '\tfinal\t'),
            table.replace('\t10.0\tns', '\t8.0\tns'), table.replace('\tns', '\tps'),
            table.replace('npaths:100', 'npaths:20'), table.replace(hx(CLOCK), hx('wrong_clock'))):
            with self.subTest(change=bad[:70]): self.assertFalse(self.parse(table=bad)['complete'])

    def test_truncation_duplicate_extra_and_counts_block(self):
        table = fixture()[1]
        for bad in (table.replace('COMPLETE\t2\t1\n', ''), table+'COMPLETE\t2\t1\n',
            table.replace('ENDPATH\t0\t0\t2', 'ENDPATH\t0\t0\t3'),
            table.replace('QUERY\t0\t100\t2', 'QUERY\t0\t100\t101'),
            table.replace('ENDCORNER\t0\t2', 'ENDCORNER\t0\t1'),
            table.replace('CORNER\t1\t', 'CORNER\t2\t'),
            table.replace('POINT\t0\t0\t0', 'POINT\t0\t0\t1')):
            with self.subTest(change=bad[-100:]): self.assertFalse(self.parse(table=bad)['complete'])

    def test_missing_report_wrong_slack_error_and_native_timeout_block(self):
        log, table, reports = fixture()
        for result in (self.parse(reports={}), self.parse(reports={'corner-0-setup100.rpt': reports['corner-0-setup100.rpt'].replace('-0.250', '-0.350')}),
            self.parse(log=log+'Error (1): native failure\n'), self.parse(rc=124),
            self.parse(log=log.replace('EARLY_SETUP\tCOMPLETE\t2\t1\n', ''))):
            self.assertFalse(result['complete'])

    def test_unknown_node_type_nonfinite_and_native_row_block(self):
        table = fixture()[1]
        for bad in (table.replace('\treg\t', '\tunknown\t'), table.replace('PATH\t0\t0\t-0.25', 'PATH\t0\t0\tNaN'),
            table+'UNSUPPORTED\n', table.replace('corner-0-setup100.rpt', 'corner-1-setup100.rpt')):
            self.assertFalse(self.parse(table=bad)['complete'])


class ExecutionTests(unittest.TestCase):
    def test_exact_native_identity_and_compiled_snapshot_required(self):
        specification = dict(scope='component_probe', sources={'rtl/p.sv': 'b'*64}, settings={'probe.qsf': 'c'*64},
            identity=dict(top='p', device='d', parameters={}, seed=1, clock_period_ns=10), selected_clock=CLOCK,
            vendor_tool_sha256={'quartus_sta': 'd'*64})
        raw = {'native.log': 'e'*64}
        context = dict(schema='quartus-earlyplace-execution-v1', platform='Linux', **q.base.identities(specification),
            phase='post_place', snapshot='placed', returncode=0, helper_sha256=q.sha(q.__file__), native_script_sha256=q.sha(q.SCRIPT),
            dependency_helper_sha256={'quartus_prefit_native_v3.py': q.sha(q.BASE_PATH)}, tool_sha256=specification['vendor_tool_sha256'],
            raw_report_sha256=raw, selected_clock=CLOCK, owner_admission_passed=True,
            source_before_sha256=specification['sources'], source_after_sha256=specification['sources'],
            settings_before_sha256=specification['settings'], settings_after_sha256=specification['settings'],
            database_before_sha256={'qdb/placed.cdb': 'f'*64}, database_after_sha256={'qdb/placed.cdb': 'f'*64},
            placement_stage_receipt_sha256='1'*64)
        q.validate_execution(context, specification, raw, 0)
        for name, bad in (('owner_admission_passed', False), ('snapshot', 'final'), ('helper_sha256', '0'*64),
            ('raw_report_sha256', {}), ('source_after_sha256', {}), ('database_after_sha256', {}), ('placement_stage_receipt_sha256', '')):
            with self.subTest(field=name), self.assertRaises(ValueError):
                q.validate_execution(dict(context, **{name: bad}), specification, raw, 0)


if __name__ == '__main__':
    unittest.main()
