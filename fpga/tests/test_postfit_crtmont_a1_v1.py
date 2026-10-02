"""A1 source and report-fixture tests: no native or cloud execution."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from cloud import aws_postfit_crtmont_a1_v1 as a
from tests.test_postfit_rootfused85_v1 import ucp_fixture

FPGA=Path(__file__).resolve().parents[1]
ARCHIVE=FPGA/'results/throughput-20260929/core27-r2-rootfused64-aws-fit-v1'
PLACE=FPGA/'results/throughput-20260929/core27-rootfused-crtmont64-fit-stage-v1/placement-observed-v1.rpt'


def path_fixture(slack,period=10):
    values=[slack,slack+.1]
    rows='\n'.join(f'; {s:.3f} ; field_lane[0].engine|child|memories[0].data_ram|q[0] ; coefficient_lane[0].crt|r1_raw[0] ; kernel_clk ; kernel_clk ; {period} ; 0.0 ; 8.0 ;' for s in values)
    return (f'Report Timing: Found 2 setup paths ({sum(s<0 for s in values)} violated)\n; Summary of Paths ;\n'
        '; Slack ; From Node ; To Node ; Launch Clock ; Latch Clock ; Relationship ; Clock Skew ; Data Delay ;\n'+rows+'\n'+
        '\n'.join(f'Path #{i}: Setup slack is {s:.3f}' for i,s in enumerate(values,1))+'\n')


def fixture(root,mode='diagnosis'):
    proposal=dict(mode=mode,period_ns='11.764' if mode=='selected_clock' else '10',baseline100=dict(
        setup=dict(slack_ns=-1.534),hold=dict(slack_ns=.015),mpw=dict(slack_ns=4.337),
        unconstrained={k:[v,v] for k,v in a.base.UCP.items()}))
    lines=[]
    for phase,period in [('baseline100',10.0)]+([('selected_clock',11.764)] if mode=='selected_clock' else []):
        lines.append(f'{a.MARK}\tCLOCK\t{phase}\tkernel_clk\t{period}\t0\t{period/2}')
        for index,corner in enumerate(sorted(a.base.CORNERS)):
            lines.append(f'{a.MARK}\tBEGIN\t{phase}\t{index}\t{corner}\t0')
            prefix=f'{phase}-{index}-'
            for name in a.base.REPORTS:(root/(prefix+name)).write_text('report\n')
            for kind in a.base.TYPES:
                slack=a.base.BASELINE.get(kind) if phase=='baseline100' else dict(setup=.358,hold=.017,mpw=5.231).get(kind)
                text='No paths to report.\n' if slack is None else f'; kernel_clk ; {slack} ; {0 if slack>=0 else -965.229} ; {0 if slack>=0 else 2813} ;\n'
                (root/(prefix+kind+'-summary.rpt')).write_text(text)
            (root/(prefix+'setup-paths.rpt')).write_text(path_fixture(-1.534 if phase=='baseline100' else .358,period))
            (root/(prefix+'ucp-summary.rpt')).write_text(ucp_fixture())
            (root/(prefix+'effective.sdc')).write_text(f'create_clock -name kernel_clk -period {period} [get_ports {{clk}}]\nderive_clock_uncertainty\nset_false_path -from [get_ports {{rst_n}}]\n')
            lines.append(f'{a.MARK}\tEND\t{phase}\t{index}\t{corner}\t0')
    lines.append(a.MARK+'\tCOMPLETE')
    return proposal,'\n'.join(lines)+'\n'


class NativeReportTests(unittest.TestCase):
    def test_final_resources_and_fanout(self):
        text=(ARCHIVE/'output_files/probe.fit.rpt').read_text()
        r=a.resources(text);self.assertEqual((r['needed_alm'],r['raw_placed_alm'],r['labs'],r['m20k'],r['needed_dsp'],r['raw_placed_dsp'],r['stage']),(299306,349941,41004,1435,802,819,'Finalize'))
        f=a.fanout(text);self.assertEqual(len(f['top20']),20)
        self.assertEqual(f['top20'][0],dict(net='double_reg',logical_fanout=5193,physical_fanout=3639))
        with self.assertRaises(ValueError):a.fanout(text.replace('; 5193    ; 3639','; 5193    ; 9999'))

    def test_placement_stage_is_not_final(self):
        if not PLACE.exists():self.skipTest('new live placement fixture not collected')
        r=a.resources(PLACE.read_text());self.assertEqual(r['stage'],'Place')
        self.assertEqual((r['needed_alm'],r['raw_placed_alm'],r['labs'],r['m20k'],r['needed_dsp'],r['raw_placed_dsp'],r['registers']),(251117,300018,36064,987,738,755,279922))

    def test_congestion_150_percent_is_not_failure_threshold(self):
        text=(ARCHIVE/'output_files/probe.fit.route.rpt').read_text();r=a.congestion(text)
        self.assertEqual((r['short_peak_estimate_percent'],r['long_peak_estimate_percent']),(118.043,150.0))
        self.assertEqual(r['hotspot_status'],'native_suppressed_below_threshold')
        self.assertIn('7 grid unit',r['hotspot_native_text']);self.assertEqual(r['wire_utilization_map'],'unavailable_in_plain_text')
        with self.assertRaises(ValueError):a.congestion(text.replace('150.000 %','nan %'))

    def test_raw_timing_separate_from_audited_clock(self):
        r=a.raw_timing((ARCHIVE/'output_files/probe.sta.rpt').read_text())
        self.assertEqual((r['reported_fmax_mhz'],r['setup']['slack_ns'],r['hold']['slack_ns'],r['mpw']['slack_ns']),(86.7,-1.534,.015,4.337))
        self.assertNotIn('supported_audit_clock',r)

    def test_missing_fanout_explicit_unavailable(self):
        self.assertEqual(a.fanout('absent')['status'],'unavailable_native_table_absent')


class SourceAndParserTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name).resolve()

    def test_exact_tcl_derivative_retains_safety_and_is_separate(self):
        raw=(FPGA/'synthesis/postfit_rootfused85_audit_v1.tcl').read_bytes();text=a.tcl_source(raw).decode()
        for required in (a.TOP,'-snapshot final','project_close -dont_export_assignments','foreach phase $a1_phases',
                         'set a1_phases {baseline100}','lappend a1_phases selected_clock','set path_count 1000','HELP_BEGIN','PREFLIGHT_COMPLETE'):
            self.assertIn(required,text)
        self.assertNotIn('11.764',text);self.assertNotIn('execute_flow',text);self.assertNotIn('project_open -force',text)
        with self.assertRaises(ValueError):a.tcl_source(raw+b'\n')

    def test_pristine_diagnosis_and_fewer_than1000_failures(self):
        p,log=fixture(self.root);r=a.parse_results(self.root,log,p)
        self.assertEqual(r['path_groups']['baseline100']['worst_failing']['selected_count'],8)
        self.assertEqual(r['path_groups']['baseline100']['worst_failing']['family_counts'],{'NTT data RAM -> CRT raw input capture':8})
        self.assertNotIn('supported_audit_clock',r)

    def test_pristine_selected_and_zero_failures(self):
        p,log=fixture(self.root,'selected_clock');r=a.parse_results(self.root,log,p)
        self.assertEqual(r['path_groups']['selected_clock']['worst_failing']['selected_count'],0)
        self.assertEqual(r['supported_audit_clock']['period_ns'],11.764)
        self.assertTrue(r['supported_audit_clock']['not_proven_highest'])

    def test_hold_failure_is_not_excused(self):
        p,log=fixture(self.root,'selected_clock');(self.root/'selected_clock-0-hold-summary.rpt').write_text('; kernel_clk ; -.001 ; -1 ; 1 ;\n')
        with self.assertRaisesRegex(ValueError,'timing failure hold'):a.parse_results(self.root,log,p)

    def test_changed_ucp_and_exception_fail(self):
        p,log=fixture(self.root,'selected_clock');f=self.root/'selected_clock-0-ucp-summary.rpt';f.write_text(f.read_text().replace('84 ; 84','83 ; 83'))
        with self.assertRaisesRegex(ValueError,'UCP'):a.parse_results(self.root,log,p)
        f.write_text(ucp_fixture());f=self.root/'selected_clock-0-effective.sdc';f.write_text(f.read_text()+'set_false_path -to [all_registers]\n')
        with self.assertRaises(ValueError):a.parse_results(self.root,log,p)

    def test_completion_order_corner_and_extra_artifact_fail(self):
        p,log=fixture(self.root)
        for bad in (log.replace(a.MARK+'\tCOMPLETE',''),log.replace('\tBEGIN\tbaseline100\t3','\tBEGIN\tbaseline100\t2'),log.replace('\t10.0\t0\t5.0','\t11.0\t0\t5.5')):
            with self.assertRaises(ValueError):a.parse_results(self.root,bad,p)
        (self.root/'extra.rpt').write_text('stale')
        with self.assertRaisesRegex(ValueError,'artifact closure'):a.parse_results(self.root,log,p)

    def test_detail_slack_and_relationship_tampering_fail(self):
        text=path_fixture(-1.534)
        for bad in (text.replace('Path #1: Setup slack is -1.534','Path #1: Setup slack is -1.000'),text.replace('; 10 ;','; 11 ;'),text.replace('(2 violated)','(1 violated)')):
            with self.assertRaises(ValueError):a.parse_paths(bad,'corner',10)

    def test_baseline_replay_must_match_actual_terminal_pin(self):
        p,log=fixture(self.root);p=copy.deepcopy(p);p['baseline100']['setup']['slack_ns']=-1.4
        with self.assertRaisesRegex(ValueError,'native replay'):a.parse_results(self.root,log,p)

    def test_period_is_explicit_plain_bounded_and_live_stage_rejected(self):
        for raw in (None,'nan','9.99','10;exit','1e1','11.7640001','101'):
            with self.assertRaises(ValueError):a.period_value(raw)
        with self.assertRaises(ValueError):a.verified_terminal((FPGA/'results/throughput-20260929/core27-rootfused-crtmont64-fit-stage-v1/project').resolve(),require_db=False)

    def test_actual_native_help_still_covers_all_commands(self):
        text=(FPGA/'results/throughput-20260929/core85-audit/v2/native-help.log').read_text().replace('CORE85','ROOTFUSED85')
        a.base.parse_preflight(text)

    def test_source_only_bundle_has_no_clock_or_execution_proposal(self):
        destination=self.root/'tools';receipt=a.prepare_tools(destination)
        self.assertEqual(receipt['status'],'source_tools_prepared_not_executed_await_terminal_fit')
        self.assertIsNone(receipt['selected_clock']);self.assertEqual(receipt['native_tool_runs'],0)
        for name,pin in receipt['source_sha256'].items():self.assertEqual(a.sha(destination/name),pin)
        self.assertTrue((destination/'source.tar.gz').is_file())
        self.assertFalse((destination/'proposal.json').exists())
        with self.assertRaises(ValueError):a.prepare_tools(destination)

    def test_terminal_source_controls_execution_and_proposal_pins(self):
        project=self.root/'project'
        shutil.copytree(FPGA/'results/throughput-20260929/core27-rootfused-crtmont64-fit-stage-v1/project',project)
        with (project/'probe.qsf').open('ab') as f:f.write(b'set_global_assignment -name LAST_QUARTUS_VERSION "26.1.0 Pro Edition"\n')
        (project/'output_files').mkdir()
        for name in ('probe.fit.summary','probe.fit.rpt','probe.fit.route.rpt','probe.fit.finalize.rpt','probe.sta.rpt'):
            text=(ARCHIVE/'output_files'/name).read_text().replace('genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused',a.TOP)
            (project/'output_files'/name).write_text(text)
        manifest=json.loads((project/'manifest.json').read_text())
        context=dict(manifest_sha256=a.MANIFEST_SHA,source_sha256=manifest['source_sha256'],mode='physical',quartus_workers=4,launcher_sha256=a.V6_SHA)
        context.update(control_sha256={'manifest.json':a.MANIFEST_SHA,**manifest['control_sha256']},
            shell_launcher_sha256='a819f56f1743027083ed1fe304909ad2655f8dcc90377dc24ab2057392984111')
        (project/'execution-context.json').write_text(json.dumps(context))
        result=dict(quartus_returncode=0,summarize_returncode=0,finished_at='fixture',context_sha256=a.sha(project/'execution-context.json'))
        (project/'execution-result.json').write_text(json.dumps(result))
        (self.root/'postfit_crtmont_a1_v1.tcl').write_bytes(a.tcl_source((FPGA/'synthesis/postfit_rootfused85_audit_v1.tcl').read_bytes()))
        p=a.prepare_terminal(project,self.root/'proposal.json','diagnosis')
        a.verified_terminal(project,p,require_db=False)
        for key in ('quartus_returncode','summarize_returncode'):
            bad=dict(result);bad[key]=1;(project/'execution-result.json').write_text(json.dumps(bad))
            with self.assertRaises(ValueError):a.verified_terminal(project,p,require_db=False)
        (project/'execution-result.json').write_text(json.dumps(result))
        bad=copy.deepcopy(p);bad['pinned_files'].pop('output_files/probe.sta.rpt')
        with self.assertRaisesRegex(ValueError,'pin closure'):a.verified_terminal(project,bad,require_db=False)
        with self.assertRaisesRegex(ValueError,'DB unavailable'):a.verified_terminal(project,p)
        with self.assertRaisesRegex(ValueError,'selected-clock'):a.prepare_terminal(project,self.root/'clock.json','selected_clock')
        with (project/'probe.qsf').open('ab') as f:f.write(b'set_global_assignment -name SEED 99\n')
        with self.assertRaisesRegex(ValueError,'control identity'):a.verified_terminal(project,p,require_db=False)


if __name__=='__main__':unittest.main()
