"""Source/fixture/mock-Tcl tests only: no Quartus or RTL simulation."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from cloud import aws_postfit_core85_v4 as a

FPGA=Path(__file__).resolve().parents[1]
SCRIPT=FPGA/'synthesis/postfit_core85_audit_v4.tcl'
PROPOSAL=FPGA/'synthesis/postfit_core85_proposal.json'
ARCHIVE=FPGA/'results/throughput-20260929/core27-stream-ntt16-fit/project'
PROJECT_HELP='Belongs to ::quartus::project2 1.0. The project_open command gives an error when the compilation database version is not compatible. You may specify the "-force" option to avoid the error and overwrite the database.'


def ucp_fixture():
    return ('+---+\n; Unconstrained Paths Summary ;\n+---+---+---+\n'
            '; Property ; Setup ; Hold ;\n+---+---+---+\n'+
            '\n'.join(f'; {k} ; {v} ; {v} ;' for k,v in a.UCP.items())+
            '\n+---+---+---+\n\n; Unconstrained Input Ports ;\n'
            '; Input Port ; Comment ;\n; start ; No input delay ;\n'
            '; Unconstrained Output Ports ;\n')


def fixture(root):
    names=sorted(a.CORNERS);log=[]
    for phase,period in [('baseline100',10.0),('audit85',a.AUDIT_PERIOD_NS)]:
        log.append(f'CORE85\tCLOCK\t{phase}\tkernel_clk\t{period}\t0\t{period/2}')
        for i,name in enumerate(names):
            log.append(f'CORE85\tBEGIN\t{phase}\t{i}\t{name}\t0')
            prefix=f'{phase}-{i}-'
            for n in a.REPORTS:(root/(prefix+n)).write_text('Report fixture\n')
            for kind in a.TYPES:
                if kind in ('recovery','removal'):text='No paths to report.\n'
                else:
                    slack=a.BASELINE[kind] if phase=='baseline100' else dict(setup=.358,hold=.017,mpw=5.231)[kind]
                    text=f'; Clock ; Slack ; End Point TNS ; Failing End Points ;\n; kernel_clk ; {slack} ; {0 if slack>=0 else -771.703} ; {0 if slack>=0 else 1972} ;\n'
                (root/(prefix+kind+'-summary.rpt')).write_text(text)
            (root/(prefix+'ucp-summary.rpt')).write_text(ucp_fixture())
            (root/(prefix+'effective.sdc')).write_text(f'create_clock -name kernel_clk -period {period} [get_ports {{clk}}]\nderive_clock_uncertainty\nset_false_path -from [get_ports {{rst_n}}]\n')
            log.append(f'CORE85\tEND\t{phase}\t{i}\t{name}\t0')
    log.append('CORE85\tCOMPLETE')
    return '\n'.join(log)+'\n'


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.log=fixture(self.root)

    def test_full_fixture_passes_and_exclusions_are_not_pass(self):
        r=a.parse_results(self.root,self.log)
        self.assertEqual(r['audit85'][sorted(a.CORNERS)[0]]['recovery']['status'],'excluded_no_paths')
        self.assertIn('not board signoff',r['claim'])

    def test_tool_footer_after_complete_allowed(self):
        a.parse_results(self.root,self.log+'Info: Quartus Timing Analyzer was successful\n')

    def test_missing_corner_rejected(self):
        with self.assertRaisesRegex(ValueError,'corner'):
            a.parse_results(self.root,'\n'.join(l for l in self.log.splitlines() if '\taudit85\t3\t' not in l))

    def test_truncated_completion_rejected(self):
        with self.assertRaisesRegex(ValueError,'completion'):a.parse_results(self.root,self.log.replace('CORE85\tCOMPLETE',''))

    def test_nested_begin_end_rejected(self):
        lines=self.log.splitlines();lines[2],lines[3]=lines[3],lines[2]
        with self.assertRaisesRegex(ValueError,'marker'):a.parse_results(self.root,'\n'.join(lines))

    def test_negative_hold_not_hidden_by_positive_setup(self):
        p=self.root/'audit85-0-hold-summary.rpt';p.write_text(p.read_text().replace('0.017','-0.001'))
        with self.assertRaisesRegex(ValueError,'timing failure'):a.parse_results(self.root,self.log)

    def test_missing_measurement_is_not_pass(self):
        (self.root/'audit85-0-setup-summary.rpt').write_text('No paths to report.\n')
        with self.assertRaisesRegex(ValueError,'setup'):a.parse_results(self.root,self.log)

    def test_tool_declared_hold_only_is_explicitly_unsupported(self):
        corner=sorted(a.CORNERS)[0]
        log=self.log.replace(corner+'\t0',corner+'\t1')
        for phase in ('baseline100','audit85'):
            for kind in ('setup','mpw'):
                (self.root/f'{phase}-0-{kind}-summary.rpt').write_text('No paths to report.\n')
        r=a.parse_results(self.root,log)
        self.assertEqual(r['audit85'][corner]['setup']['status'],'unsupported_at_hold_only_corner')
        self.assertEqual(r['audit85'][corner]['hold']['status'],'measured')

    def test_hold_only_never_excuses_missing_hold(self):
        corner=sorted(a.CORNERS)[0];log=self.log.replace(corner+'\t0',corner+'\t1')
        (self.root/'audit85-0-hold-summary.rpt').write_text('No paths to report.\n')
        with self.assertRaisesRegex(ValueError,'hold'):a.parse_results(self.root,log)

    def test_nan_and_positive_tns_inconsistent_rejected(self):
        p=self.root/'audit85-0-setup-summary.rpt';original=p.read_text()
        for bad in (original.replace('0.358','nan'),original.replace('; 0 ; 0 ;','; -1 ; 0 ;')):
            p.write_text(bad)
            with self.assertRaises(ValueError):a.parse_results(self.root,self.log)

    def test_wrong_period_rejected(self):
        with self.assertRaisesRegex(ValueError,'period'):
            a.parse_results(self.root,self.log.replace(str(a.AUDIT_PERIOD_NS),'11.765'))

    def test_changed_or_missing_exception_rejected(self):
        p=self.root/'audit85-0-effective.sdc';original=p.read_text()
        for bad in (original.replace('rst_n','*'),original+'set_false_path -to [all_registers]\n',original.replace(' -from ',' -rise_from ')):
            p.write_text(bad)
            with self.assertRaises(ValueError):a.parse_results(self.root,self.log)

    def test_missing_uncertainty_rejected(self):
        p=self.root/'audit85-0-effective.sdc';p.write_text(p.read_text().replace('derive_clock_uncertainty\n',''))
        with self.assertRaisesRegex(ValueError,'uncertainty'):a.parse_results(self.root,self.log)

    def test_ucp_count_reduction_not_accepted_as_improvement(self):
        p=self.root/'audit85-0-ucp-summary.rpt';p.write_text(p.read_text().replace('84 ; 84','0 ; 0'))
        with self.assertRaisesRegex(ValueError,'unconstrained'):a.parse_results(self.root,self.log)

    def test_baseline_replay_must_match(self):
        for i in range(4):
            p=self.root/f'baseline100-{i}-setup-summary.rpt';p.write_text(p.read_text().replace('-1.406','-1.300'))
        with self.assertRaisesRegex(ValueError,'baseline100'):a.parse_results(self.root,self.log)

    def test_missing_detail_and_unexpected_output_rejected(self):
        p=self.root/'audit85-0-mpw-paths.rpt';p.unlink()
        with self.assertRaisesRegex(ValueError,'missing/empty'):a.parse_results(self.root,self.log)
        p.write_text('report');(self.root/'stale-old.rpt').write_text('old')
        with self.assertRaisesRegex(ValueError,'closure'):a.parse_results(self.root,self.log)

    def test_native_preflight_requires_every_command_and_option(self):
        text=''.join(f'CORE85\tHELP_BEGIN\t{k}\n{k} '+ ' '.join(v)+(PROJECT_HELP if k=='project_open' else '')+f'\nCORE85\tHELP_END\t{k}\n' for k,v in a.PREFLIGHT.items())+'CORE85\tPREFLIGHT_COMPLETE\n'
        a.parse_preflight(text)
        with self.assertRaisesRegex(ValueError,'unsupported'):a.parse_preflight(text.replace('-preserve_revision_order',''))
        with self.assertRaisesRegex(ValueError,'truncated'):a.parse_preflight(text.replace('CORE85\tPREFLIGHT_COMPLETE',''))

    def test_actual_native26_help_and_default_refusal_guard(self):
        text=(FPGA/'results/throughput-20260929/core85-audit/v2/native-help.log').read_text()
        a.parse_preflight(text)
        with self.assertRaisesRegex(ValueError,'incompatibility refusal'):
            a.parse_preflight(text.replace('gives an error when','does not error when'))

    def test_exact_conservative_clock_and_no_tolerance_relaxation(self):
        self.assertEqual(a.AUDIT_PERIOD_NS,11.764)
        self.assertEqual(a.AUDIT_HALF_PERIOD_NS,5.882)
        self.assertAlmostEqual(a.AUDIT_FREQUENCY_MHZ,85.00510030601836,places=12)
        self.assertGreater(a.AUDIT_FREQUENCY_MHZ,85)
        for bad in ('11.765','11.764705882352942','11.764002'):
            with self.assertRaisesRegex(ValueError,'period'):
                a.parse_results(self.root,self.log.replace('11.764',bad))
        with self.assertRaisesRegex(ValueError,'period'):
            a.parse_results(self.root,self.log.replace('\t5.882','\t5.882002'))

    def test_real_v3_ucp_tables_parse_later_repeated_headings(self):
        archive=FPGA/'results/throughput-20260929/core85-audit/v3/timing'
        for i in range(4):
            text=(archive/f'baseline100-{i}-ucp-summary.rpt').read_text()
            self.assertGreater(text.count('; Unconstrained Input Ports'),1)
            self.assertEqual(a.ucp(text),{k:(v,v) for k,v in a.UCP.items()})

    def test_ucp_exact_table_header_rows_and_end_required(self):
        text=ucp_fixture()
        mutations=(text.replace('Property ; Setup ; Hold','Property ; Hold ; Setup'),
                   text.replace('; 84 ; 84 ;','; 84 ;'),
                   text.replace('; 84 ; 84 ;','; 84 ; 83 ;'),
                   text.replace('; 84 ; 84 ;','; +84 ; 84 ;'),
                   text.replace('; 84 ; 84 ;','; 84 ; nan ;'),
                   text.replace('; Illegal Clocks ; 0 ; 0 ;','; Illegal Clocks ; 0 ; 0 ;\n; Illegal Clocks ; 0 ; 0 ;'),
                   text.replace('2332 ; 2332 ;\n+---+---+---+','2332 ; 2332 ;\n; unexpected ; 0 ; 0 ;\n+---+---+---+'),
                   text.split('; Paths to Unconstrained Output Ports')[0],
                   text+'; Unconstrained Paths Summary ;\n')
        for i,bad in enumerate(mutations):
            with self.subTest(index=i),self.assertRaises(ValueError):a.ucp(bad)
        # A later single-cell detail heading is not a summary count row.
        self.assertEqual(a.ucp(text+'; Unconstrained Clocks ;\n'),a.ucp(text))


class SnapshotPolicyTests(unittest.TestCase):
    def make_trees(self,directory):
        original=Path(directory).resolve()/'original';original.mkdir()
        names={name:b'old report' for name in a.REPORT_OUTPUTS if '/report.cmp.' in name}
        names.update({name:b'old final cache' for name in a.CACHE_PROMOTIONS})
        names.update({name:('routed '+name).encode() for name in a.CACHE_PROMOTIONS.values()})
        names.update({'probe.sdc':b'original constraints','rtl/core.sv':b'original source',
                      'qdb/circuit.model':b'protected circuit'})
        for name,data in names.items():
            path=original/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        before=a.inventory(original);copied=original.parent/'snapshot'
        a.snapshot(original,copied,before)
        return original,copied,before

    def apply_observed_changes(self,original,copied):
        for name in a.REPORT_OUTPUTS:
            (copied/name).write_bytes(b'new report data')
        for destination,source in a.CACHE_PROMOTIONS.items():
            (copied/destination).write_bytes((original/source).read_bytes())

    def test_only_observed_reports_and_source_matched_promotions_pass(self):
        with tempfile.TemporaryDirectory() as d:
            original,copied,before=self.make_trees(d);self.apply_observed_changes(original,copied)
            receipt={};a.record_snapshot_check(receipt,original,copied,before)
            self.assertEqual(len(receipt['snapshot_differences']),6)
            self.assertEqual(sum(row['kind']=='exact_report_output' for row in receipt['snapshot_differences'].values()),4)
            self.assertTrue(all(row['allowed'] for row in receipt['snapshot_differences'].values()))
            self.assertEqual(receipt['cache_promotion_byte_comparisons'],{name:True for name in a.CACHE_PROMOTIONS})
            self.assertEqual(a.inventory(original),before)
            self.assertEqual(a.file_differences(before,a.inventory(original)),{})

    def test_actual_v3_six_deltas_fit_exact_policy_without_promoting_failed_run(self):
        receipt=json.loads((FPGA/'results/throughput-20260929/core85-audit/v3/receipt.json').read_text())
        self.assertEqual(receipt['status'],'failed')
        self.assertEqual(receipt['original_before'],receipt['original_after'])
        changes=a.snapshot_differences(receipt['original_before'],receipt['snapshot_after'])
        self.assertEqual(set(changes),a.REPORT_OUTPUTS|set(a.CACHE_PROMOTIONS))
        self.assertTrue(all(row['allowed'] for row in changes.values()))
        for destination,source in a.CACHE_PROMOTIONS.items():
            self.assertEqual(changes[destination]['after'],receipt['original_before'][source])
        self.assertNotIn('timing',receipt)  # No audit85 corner was completed.

    def test_changed_deleted_or_added_unlisted_file_rejects_and_records_all(self):
        for name,operation in (('probe.sdc','change'),('rtl/core.sv','change'),
                ('qdb/circuit.model','change'),('qdb/circuit.model','delete'),
                ('qdb/_compiler/probe/_flat/26.1.0/_all/1/report.cmp.model','delete'),('qdb/report.other.rdb','add'),
                ('qdb/_compiler/probe/_flat/26.1.0/_all/1/report.taw.extra','add')):
            with self.subTest(name=name,operation=operation),tempfile.TemporaryDirectory() as d:
                original,copied,before=self.make_trees(d);self.apply_observed_changes(original,copied)
                path=copied/name
                if operation=='delete':path.unlink()
                else:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'bad')
                receipt={}
                with self.assertRaisesRegex(ValueError,'unreviewed copied'):a.record_snapshot_check(receipt,original,copied,before)
                self.assertFalse(receipt['snapshot_differences'][name]['allowed'])
                self.assertGreaterEqual(len(receipt['snapshot_differences']),6)

    def test_empty_report_or_wrong_cache_bytes_rejected(self):
        for name,value in ((next(iter(a.REPORT_OUTPUTS)),b''),(next(iter(a.CACHE_PROMOTIONS)),b'bad cache')):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as d:
                original,copied,before=self.make_trees(d);self.apply_observed_changes(original,copied)
                (copied/name).write_bytes(value);receipt={}
                with self.assertRaises(ValueError):a.record_snapshot_check(receipt,original,copied,before)
                self.assertFalse(receipt['snapshot_differences'][name]['allowed'])

    def test_changing_routed_source_and_promotion_together_cannot_pass(self):
        with tempfile.TemporaryDirectory() as d:
            original,copied,before=self.make_trees(d);self.apply_observed_changes(original,copied)
            destination,source=next(iter(a.CACHE_PROMOTIONS.items()))
            (copied/source).write_bytes(b'new mutually matching content');(copied/destination).write_bytes(b'new mutually matching content')
            receipt={}
            with self.assertRaises(ValueError):a.record_snapshot_check(receipt,original,copied,before)
            self.assertFalse(receipt['snapshot_differences'][source]['allowed'])
            self.assertFalse(receipt['snapshot_differences'][destination]['allowed'])

    def test_promotion_requires_existing_destination_and_source_before(self):
        with tempfile.TemporaryDirectory() as d:
            original,copied,before=self.make_trees(d);self.apply_observed_changes(original,copied)
            destination,source=next(iter(a.CACHE_PROMOTIONS.items()));after=a.inventory(copied)
            for absent in (source,destination):
                reduced=dict(before);del reduced[absent]
                self.assertFalse(a.snapshot_differences(reduced,after)[destination]['allowed'])

    def test_byte_comparison_independent_of_hash_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            original,copied,before=self.make_trees(d);self.apply_observed_changes(original,copied)
            receipt={}
            with patch.object(a,'equal_bytes',return_value=False),self.assertRaisesRegex(ValueError,'routed bytes'):
                a.record_snapshot_check(receipt,original,copied,before)
            self.assertIn(False,receipt['cache_promotion_byte_comparisons'].values())

    def test_unmodified_snapshot_and_no_deletion_policy(self):
        with tempfile.TemporaryDirectory() as d:
            original,copied,before=self.make_trees(d);receipt={}
            a.record_snapshot_check(receipt,original,copied,before)
            self.assertEqual(receipt['snapshot_differences'],{})
            self.assertEqual(receipt['cache_promotion_byte_comparisons'],{})

    def test_frozen_helpers_untouched_and_exact_tcl_delta(self):
        old=FPGA/'synthesis/postfit_core85_audit.tcl'
        self.assertEqual(a.sha(old),'4e5eb8d6c942851280197f764e0b90347c840e524bdf3163bb764798cce81d7c')
        self.assertEqual(a.sha(FPGA/'cloud/aws_postfit_core85.py'),
                         '7d88768949767a34612642a5d5fe3892f31981a6c357b626a5a4678338169465')
        expected=old.read_text().replace('aws_postfit_core85.py','aws_postfit_core85_v4.py')
        expected=expected.replace('set period [expr {1000.0/85.0}]','set period 11.764')
        expected=expected.replace('-waveform [list 0.0 [expr {$period/2.0}]]','-waveform {0.0 5.882}')
        self.assertEqual(SCRIPT.read_text(),expected)


class ProvenanceTests(unittest.TestCase):
    def test_proposal_and_archive_pins(self):
        self.assertEqual(a.sha(PROPOSAL),a.PROPOSAL_SHA)
        proposal=json.loads(PROPOSAL.read_text())
        for n,h in proposal['pinned_files'].items():self.assertEqual(a.sha(ARCHIVE/n),h)
        for n,h in json.loads((ARCHIVE/'manifest.json').read_text())['source_sha256'].items():
            self.assertEqual(a.sha(ARCHIVE/'rtl'/n),h)

    def test_missing_db_refuses_report_only_archive(self):
        with self.assertRaisesRegex(ValueError,'DB missing'):a.verify_project(ARCHIVE,json.loads(PROPOSAL.read_text()))

    def test_byte_snapshot_no_original_alias_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();original=root/'original';original.mkdir();(original/'db').mkdir()
            (original/'db/data').write_bytes(b'\0routed\xff');before=a.inventory(original)
            a.snapshot(original,root/'snapshot',before)
            self.assertEqual(a.inventory(original),before)
            (root/'snapshot/db/data').write_bytes(b'changed')
            self.assertEqual(a.inventory(original),before)
            with self.assertRaisesRegex(ValueError,'already exists'):a.snapshot(original,root/'snapshot',before)

    def test_symlinks_and_hardlinks_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d).resolve();(p/'data').write_text('data');(p/'alias').symlink_to(p/'data')
            with self.assertRaisesRegex(ValueError,'link/special'):a.inventory(p)
            (p/'alias').unlink();os.link(p/'data',p/'alias')
            with self.assertRaisesRegex(ValueError,'hard-linked'):a.inventory(p)

    def test_snapshot_rejects_wrong_source_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d).resolve();src=p/'src';src.mkdir();(src/'one').write_text('old');before=a.inventory(src)
            (src/'one').write_text('new')
            with self.assertRaisesRegex(ValueError,'bytes differ'):a.snapshot(src,p/'copy',before)


@unittest.skipUnless(shutil.which('tclsh'),'Tcl interpreter required')
class TclLifecycleTests(unittest.TestCase):
    def run_script(self,extra='',preflight=False):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'snapshot').mkdir();(root/'timing').mkdir()
            shutil.copyfile(ARCHIVE/'probe.sdc',root/'snapshot/probe.sdc')
            mock=r'''
proc load_package {args} {}
proc project_open {args} {puts "MOCK_OPEN $args"}
proc project_close {args} {puts "MOCK_CLOSE $args"}
proc create_timing_netlist {args} {puts "MOCK_NETLIST $args"}
proc delete_timing_netlist {} {puts MOCK_DELETE}
proc read_sdc {} {puts MOCK_READ_SDC}
proc derive_clock_uncertainty {} {puts MOCK_DERIVE}
proc update_timing_netlist {} {puts MOCK_UPDATE}
proc get_ports {args} {return T}
proc get_clocks {args} {return C}
proc get_collection_size {value} {return [llength $value]}
proc foreach_in_collection {var items body} {uplevel 1 [list foreach $var $items $body]}
proc get_node_info {args} {return clk}
proc get_global_assignment {args} {
    return [dict get {TOP_LEVEL_ENTITY genefer_square_core27_stream DEVICE 10AX115N4F40E3SG SDC_FILE probe.sdc} [lindex $args 1]]
}
set period 10.0
proc get_clock_info {flag clock} {
    global period
    switch -- $flag {
      -name {return kernel_clk} -type {return base} -targets {return T}
      -period {return $period} -waveform {return [list 0 [expr {$period/2}]]}
    }
    error "unexpected clock flag $flag"
}
proc create_clock {args} {global period;set period [lindex $args [expr {[lsearch $args -period]+1}]];puts "MOCK_OVERRIDE $period"}
proc get_available_operating_conditions {} {return {S100 S0 F100 F0}}
proc get_operating_conditions_info {flag op} {
    if {$flag eq "-is_hold_only"} {return 0}
    return [dict get {S100 {Slow 900mV 100C Model} S0 {Slow 900mV 0C Model} F100 {Fast 900mV 100C Model} F0 {Fast 900mV 0C Model}} $op]
}
proc set_operating_conditions {op} {puts "MOCK_CORNER $op"}
proc report_stub {args} {puts "MOCK_REPORT $args"}
foreach name {report_clocks report_sdc report_exceptions write_sdc report_timing report_min_pulse_width report_ucp check_timing create_timing_summary} {interp alias {} $name {} report_stub}
'''
            mock+=extra+'\n'
            if preflight:
                mock+='set quartus(args) preflight\n'
                mock+='proc unknown {args} {puts "MOCK_UNKNOWN $args"}\n'
            else:mock+='set quartus(args) [list {'+str(root/'snapshot')+'} {'+str(root/'timing')+'}]\n'
            mock+='if {[catch {source {'+str(SCRIPT)+'}} err]} {puts "MOCK_FAILURE $err"}\n'
            return subprocess.run(['tclsh'],input=mock,text=True,capture_output=True,check=True).stdout

    def test_order_all_corners_and_cleanup(self):
        out=self.run_script()
        self.assertNotIn('MOCK_FAILURE',out)
        self.assertEqual(out.count('MOCK_READ_SDC'),1)
        self.assertEqual(out.count('CORE85\tBEGIN'),8)
        self.assertEqual(out.count('MOCK_OVERRIDE'),1)
        self.assertLess(out.index('CORE85\tEND\tbaseline100\t3'),out.index('MOCK_OVERRIDE'))
        self.assertIn('MOCK_OVERRIDE 11.764\nMOCK_DERIVE\nMOCK_UPDATE',out)
        self.assertIn('MOCK_NETLIST -model slow -snapshot final',out)
        self.assertTrue(out.endswith('MOCK_DELETE\nMOCK_CLOSE -dont_export_assignments\nCORE85\tCOMPLETE\n'))

    def test_preflight_prints_returned_help_without_opening_project(self):
        # Real26.1 v1 returned help as a Tcl value; it did not print it.
        extra=''
        for cmd,options in a.PREFLIGHT.items():
            extra+='rename '+cmd+' {}\n'
            body='if {$args ne "-long_help"} {error unexpected_native_execution}; return {'+cmd+' '+ ' '.join(options)+(PROJECT_HELP if cmd=='project_open' else '')+'}'
            extra+='proc '+cmd+' {args} {'+body+'}\n'
        out=self.run_script(extra,preflight=True)
        self.assertNotIn('MOCK_FAILURE',out)
        self.assertNotIn('MOCK_OPEN',out)
        self.assertNotIn('MOCK_NETLIST',out)
        a.parse_preflight(out)

    def test_native_compatibility_changes_do_not_relax_constraints(self):
        out=self.run_script()
        self.assertIn('MOCK_OPEN -preserve_revision_order -revision probe probe',out)
        self.assertNotIn('MOCK_OPEN -force',out)
        self.assertNotIn('-ucp-setup.rpt',out)
        self.assertNotIn('-ucp-hold.rpt',out)
        self.assertEqual(out.count('-ucp-paths.rpt'),8)
        self.assertEqual(out.count('-ucp-summary.rpt'),8)

    def test_query_error_cleans_up_without_complete(self):
        out=self.run_script('proc update_timing_netlist {} {error injected}')
        self.assertIn('MOCK_DELETE\nMOCK_CLOSE -dont_export_assignments\nMOCK_FAILURE injected',out)
        self.assertNotIn('CORE85\tCOMPLETE',out)

    def test_extra_clock_aborts_before_reports(self):
        out=self.run_script('proc get_clocks {args} {return {C D}}')
        self.assertIn('MOCK_FAILURE Clock count changed',out)
        self.assertNotIn('CORE85\tBEGIN',out)

    def test_missing_corner_aborts(self):
        out=self.run_script('proc get_available_operating_conditions {} {return {S100 S0 F100}}')
        self.assertIn('Expected four supported corners',out)
        self.assertNotIn('CORE85\tCOMPLETE',out)

    def test_wrong_type_rejected(self):
        out=self.run_script('rename get_clock_info orig_clock_info\nproc get_clock_info {flag clock} {if {$flag eq "-type"} {return generated};return [orig_clock_info $flag $clock]}')
        self.assertIn('Wrong clock identity/type/targets',out)


if __name__=='__main__':unittest.main()
