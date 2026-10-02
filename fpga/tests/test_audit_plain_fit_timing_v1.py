"""Pure/native-retained-fixture tests. Never execute Quartus or a cloud call."""
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

FPGA = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(FPGA/'tools'))
import audit_plain_fit_timing_v1 as audit

NATIVE = FPGA/'results/throughput-20260929/core27-t5b-selected9668-audit-m8azn-v3'
P8 = FPGA/'results/throughput-20260929/stream27-p8b-aw16-aws-plain-v1'
A4B = FPGA/'results/throughput-20260929/track-a4b-aw16-aws-plain-v1'
TCL = FPGA/'synthesis/postfit_plain_timing_v1.tcl'


def table(title,header,values):
    return '; '+title+' ;\n+---+\n; '+' ; '.join(header)+' ;\n+---+\n'+''.join(
        '; '+' ; '.join(map(str,row))+' ;\n' for row in values)+'+---+\n'


def effective(period):
    return ('set_time_format -unit ns -decimal_places 3\n'
        f'create_clock -name {{kernel_clk}} -period {period} -waveform {{ 0.000 {float(period)/2:.3f} }} [get_ports {{clk}}]\n'+
        ''.join(f'set_clock_uncertainty -{a}_from [get_clocks {{kernel_clk}}] -{b}_to [get_clocks {{kernel_clk}}] 0.030\n'
            for a,b in (('rise','rise'),('rise','fall'),('fall','rise'),('fall','fall')))+
        'set_false_path -from [get_ports {rst_n}]\n')


def clock(period):
    return table('Clocks',['Clock Name','Type','Period','Frequency','Rise','Fall','Duty Cycle','Divide by','Multiply by',
        'Phase','Offset','Edge List','Edge Shift','Inverted','Master','Source','Targets'],
        [['kernel_clk','Base',period,f'{1000/float(period):.2f} MHz',0,f'{float(period)/2:.3f}',*['']*10,'{ clk }']])


def path_report(corner,period,slack):
    return f'Report Timing: Found 2 setup paths ({2 if slack < -.1 else 1 if slack < 0 else 0} violated)\nSnapshot:\n    final\nDelay Model:\n    {corner}\n'+table(
        'Summary of Paths',['Slack','From Node','To Node','Launch Clock','Latch Clock','Relationship','Clock Skew','Data Delay'],
        [[f'{value:.3f}','producer|q[0]','consumer|q[0]','kernel_clk','kernel_clk',period,-.1,6]
            for value in (slack,slack+.1)])+f'Path #1: Setup slack is {slack:.3f}\nPath #2: Setup slack is {slack+.1:.3f}\n'


def fixture(root,negative_baseline=False,selected='9.668',measured_recovery=False):
    spec = dict(baseline_period_ns='10',selected_period_ns=selected,path_limit=1000)
    baseline = dict(setup=dict(slack_ns=-.957 if negative_baseline else .334),hold=dict(slack_ns=.017),
        mpw=dict(slack_ns=4.337),unconstrained={key:[0,0] for key in audit.UCP_KEYS})
    lines = []
    for phase,p in [('baseline','10')]+([('selected',selected)] if selected else []):
        lines.append(f'{audit.MARK}\tCLOCK\t{phase}\tkernel_clk\tbase\tclk\t{p}\t0\t{float(p)/2:.3f}\tns')
        for index,name in enumerate(sorted(audit.CORNERS)):
            lines.append(f'{audit.MARK}\tBEGIN\t{phase}\t{index}\t{name}\t0')
            prefix = f'{phase}-{index}-'
            for suffix in audit.REPORTS: (root/(prefix+suffix)).write_text('retained native artifact\n')
            for kind in audit.TYPES:
                value = baseline[kind]['slack_ns'] if kind in baseline and phase == 'baseline' else dict(setup=.002,hold=.017,mpw=4.171).get(kind)
                if measured_recovery and kind in ('recovery','removal'): value = .932
                text = 'No paths to report.\n' if value is None else f'; kernel_clk ; {value} ; {-1 if value < 0 else 0} ; {2 if value < 0 else 0} ;\n'
                (root/(prefix+kind+'-summary.rpt')).write_text(text)
            slack = baseline['setup']['slack_ns'] if phase == 'baseline' else .002
            (root/(prefix+'setup-paths.rpt')).write_text(path_report(name,p,slack))
            (root/(prefix+'ucp-summary.rpt')).write_text(table('Unconstrained Paths Summary',['Property','Setup','Hold'],
                [[key,0,0] for key in audit.UCP_KEYS]))
            (root/(prefix+'clocks.rpt')).write_text(clock(p))
            (root/(prefix+'effective.sdc')).write_text(effective(p))
            lines.append(f'{audit.MARK}\tEND\t{phase}\t{index}\t{name}\t0')
    lines.append(audit.MARK+'\tCOMPLETE')
    return spec,baseline,'\n'.join(lines)+'\n'


class AuditTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def test_even_picosecond_explicit_periods_and_source_sdc(self):
        for value in ('8','9.3','9.5','9.668','10.958'): self.assertGreater(audit.period(value),0)
        for value in ('9.667','9.5001','1.998','NaN','1e1','9.5;exec x'):
            with self.assertRaises(ValueError): audit.period(value)
        audit.source_sdc((P8/'project/probe.sdc').read_text(),'10')
        for bad in ('set_false_path -to [all_registers]\n','source helper.sdc\n'):
            with self.assertRaises(ValueError): audit.source_sdc((P8/'project/probe.sdc').read_text()+bad,'10')

    def test_full_eight_corner_completion_and_negative_baseline(self):
        spec,baseline,log = fixture(self.root,negative_baseline=True,measured_recovery=True)
        result = audit.parse_results(self.root,log,spec,baseline)
        self.assertFalse(result['baseline']['timing_closes'])
        self.assertTrue(result['selected']['timing_closes'])
        self.assertEqual(len(result['selected']['corners']),4)
        self.assertEqual(result['selected']['observed_setup_paths'],8)
        self.assertEqual(next(iter(result['selected']['corners'].values()))['recovery']['status'],'measured')

    def test_native_violation_is_retained_not_parse_failure(self):
        spec,baseline,log = fixture(self.root)
        path = self.root/'selected-0-hold-summary.rpt'
        path.write_text('; kernel_clk ; -.001 ; -.001 ; 1 ;\n')
        result = audit.parse_results(self.root,log,spec,baseline)
        self.assertFalse(result['selected']['timing_closes'])
        self.assertEqual(next(iter(result['selected']['corners'].values()))['hold']['failing_endpoints'],1)

    def test_truncated_unknown_corner_clock_exception_or_extra_refused(self):
        spec,baseline,log = fixture(self.root)
        for bad in (log.replace(audit.MARK+'\tCOMPLETE',''),log.replace('\tBEGIN\tselected\t3','\tBEGIN\tselected\t2'),
                    log.replace('\tkernel_clk\tbase\tclk\t9.668','\tkernel_clk\tbase\tother\t9.668')):
            with self.assertRaises(ValueError): audit.parse_results(self.root,bad,spec,baseline)
        path = self.root/'selected-0-effective.sdc'; old = path.read_text()
        path.write_text(old+'set_false_path -to [all_registers]\n')
        with self.assertRaises(ValueError): audit.parse_results(self.root,log,spec,baseline)
        path.write_text(old); (self.root/'unclassified-cache.json').write_text('{}')
        with self.assertRaises(ValueError): audit.parse_results(self.root,log,spec,baseline)

    def test_actual_completed_reports_and_clock_scope(self):
        for root,target,slack in ((P8,'10',.691),(A4B,'10',-.957)):
            result = audit.baseline_summary((root/'project/output_files/probe.sta.rpt').read_text(),target)
            self.assertEqual(result['setup']['slack_ns'],slack)
            self.assertEqual(result['clock']['target'],'clk')
        native = (NATIVE/'timing/selected_clock-0-setup-paths.rpt').read_text()
        values = audit.paths(native,'Slow 900mV 100C Model','9.668',1000)
        self.assertEqual(len(values),1000)
        self.assertEqual(values[0]['slack_ns'],.183)
        for bad in (native.replace('    final','    placed',1),native.replace('; 9.668','; 9.667',1),
                    native.replace('Path #1: Setup slack is 0.183','Path #1: Setup slack is 0.182')):
            with self.assertRaises(ValueError): audit.paths(bad,'Slow 900mV 100C Model','9.668',1000)

    def test_actual_eight_corner_retained_native_fixture(self):
        # Byte-preserved actual reports, with ONLY protocol filename/marker renaming.
        for path in (NATIVE/'timing').iterdir():
            name = path.name.replace('baseline100-','baseline-').replace('selected_clock-','selected-')
            shutil.copy2(path,self.root/name)
        log = (NATIVE/'audit.log').read_text().replace('CRTMONT_A1','PLAIN_POSTFIT').replace('baseline100','baseline').replace('selected_clock','selected')
        log = rebind_clock_markers(log)
        baseline = audit.baseline_summary((FPGA/'results/throughput-20260929/core27-t5b-provisional64-aws-fit-v1/output_files/probe.sta.rpt').read_text(),'10')
        result = audit.parse_results(self.root,log,dict(baseline_period_ns='10',selected_period_ns='9.668',path_limit=1000),baseline)
        self.assertTrue(result['baseline']['timing_closes'] and result['selected']['timing_closes'])
        self.assertEqual(result['baseline']['observed_setup_paths'],4000)
        self.assertEqual(result['selected']['observed_setup_paths'],4000)
        self.assertAlmostEqual(min(row['setup']['slack_ns'] for row in result['selected']['corners'].values()),.002)

    def test_strict_copy_deltas_and_unchanged_compiled_input(self):
        before = {'rtl/top.sv':dict(sha256='a'*64,size=12)}
        for name in ('rtl/top.sv','qdb/unknown.hsd','probe.sdc'):
            after = copy.deepcopy(before); after[name] = dict(sha256='b'*64,size=13)
            self.assertFalse(all(row['allowed'] for row in audit.differences(before,after).values()))
        report = next(iter(audit.REPORT_OUTPUTS)); after = {**before,report:dict(sha256='c'*64,size=12)}
        self.assertTrue(audit.differences(before,after)[report]['allowed'])
        final,routed = next(iter(audit.CACHE_PROMOTIONS.items()))
        before[final] = dict(sha256='d'*64,size=12); before[routed] = dict(sha256='e'*64,size=12)
        after = {**before,final:before[routed]}; self.assertTrue(audit.differences(before,after)[final]['allowed'])
        after[routed] = dict(sha256='f'*64,size=12); self.assertFalse(audit.differences(before,after)[final]['allowed'])
        self.assertFalse(audit.differences(before,{})['rtl/top.sv']['allowed'])

    def test_clean_environment_and_native_tcl_no_refit_fallback(self):
        with patch.dict(os.environ,{'HOME':'/home/ubuntu','LD_LIBRARY_PATH':'bad','QUARTUS_ROOTDIR':'bad'}):
            env = audit.clean_environment()
        self.assertEqual(set(env),{'HOME','PATH','LANG','LC_ALL'})
        self.assertNotIn('LD_LIBRARY_PATH',env)
        source = TCL.read_text()
        for required in ('-snapshot final','project_close -dont_export_assignments','set_time_format -unit ns','set count $path_limit'):
            self.assertIn(required,source)
        for forbidden in ('execute_flow','quartus_fit','project_open -force','snapshot placed'):
            self.assertNotIn(forbidden,source)

    def test_actual_native_help_complete_and_unsupported_not_excused(self):
        import re
        source = (NATIVE/'native-help.log').read_text()
        unit_help = (FPGA/'results/throughput-20260929/quartus-time-units-help-v1/time-units-help.log').read_text()
        unit_help = unit_help[unit_help.index('Usage: set_time_format'):unit_help.index('ERROR: Tcl command')]
        records = []
        for command in audit.PREFLIGHT:
            if command == 'set_time_format': body = unit_help
            else:
                body = re.findall(r'^CRTMONT_A1\tHELP_BEGIN\t'+command+r'\n(.*?)^CRTMONT_A1\tHELP_END\t'+command+r'$',source,re.M|re.S)[0]
            records += [audit.MARK+'\tHELP_BEGIN\t'+command,body,audit.MARK+'\tHELP_END\t'+command]
        text = '\n'.join(records+[audit.MARK+'\tPREFLIGHT_COMPLETE'])+'\n'
        audit.parse_preflight(text)
        for bad in (text.replace('-snapshot','-unsupported'),text.replace(audit.MARK+'\tPREFLIGHT_COMPLETE',''),
                    text+'Error: native helper failed\n'):
            with self.assertRaises(ValueError): audit.parse_preflight(bad)

    def test_report_name_alone_does_not_allow_compiled_model(self):
        original = self.root/'original'; copied = self.root/'snapshot'; original.mkdir(); copied.mkdir()
        name = next(value for value in audit.REPORT_OUTPUTS if value.endswith('.model'))
        path = copied/name; path.parent.mkdir(parents=True)
        path.write_text(json.dumps(dict(type='hsd',trait='compiled',signature='a'*32,temp_payload_path='',bak=False)))
        (copied/(name[:-6]+'.rdb')).write_bytes(b'payload')
        receipt = {}
        with self.assertRaises(ValueError): audit.check_copy(receipt,original,copied,{})
        self.assertFalse(receipt['compiled_input_unchanged'])
        self.assertFalse(receipt['snapshot_differences'][name]['allowed'])
        self.assertIn('classification_error',receipt['snapshot_differences'][name])

    def prepared_spec(self):
        project = self.root/'completed'; shutil.copytree(P8/'project',project)
        (project/'qdb').mkdir(); (project/'qdb/compiled.hsd').write_bytes(b'exact compiled fixture')
        database = audit.qdb_inventory(audit.inventory(project))
        (project/'database-inventory-final.json').write_text(json.dumps(database))
        receipt = json.loads((P8/'terminal-collection-v1.json').read_text()); receipt['project'] = str(project)
        terminal = self.root/'terminal.json'; terminal.write_text(json.dumps(receipt))
        tools = self.root/'altera_pro/26.1/quartus'; (tools/'bin').mkdir(parents=True); (tools/'linux64').mkdir()
        for path in (tools/'bin/quartus_sta',tools/'linux64/quartus_sta'): path.write_bytes(b'exact native fixture, never executed')
        tool_pins = {str(path):audit.sha(path) for path in (tools/'bin/quartus_sta',tools/'linux64/quartus_sta')}
        spec = audit.make_spec(project,self.root/'audit',terminal,TCL,tool_pins,scope='component_probe',
            native_seconds=300,maximum_copy_bytes=64<<20,selected_period_ns='9.668',selection_reason='explicit test point')
        return project,spec

    def test_actual_plain_source_spec_and_tamper_or_unknown_selector(self):
        project,spec = self.prepared_spec()
        self.assertEqual(len(spec['pins']),len(json.loads((project/'manifest.json').read_text())['source_sha256'])+11)
        for key,value in [('snapshot','placed'),('clock','other'),('selected_period_ns','9.667'),('tool_version','26.0 Build110')]:
            bad = copy.deepcopy(spec); bad[key] = value
            with self.assertRaises(ValueError): audit.validate_spec(project,bad)
        bad = copy.deepcopy(spec); bad['unexpected_selector'] = True
        with self.assertRaises(ValueError): audit.validate_spec(project,bad)
        qsf = project/'probe.qsf'; qsf.write_bytes(qsf.read_bytes()+b'changed setting\n')
        with self.assertRaises(ValueError): audit.verify_project(project,spec)

    def test_mocked_native_failure_retains_original_copy_and_log(self):
        project,spec = self.prepared_spec(); specification = self.root/'spec.json'
        specification.write_text(json.dumps(spec)); before = audit.inventory(project)
        def fail(command,cwd,log,seconds,receipt):
            log.write_text('Error: native API fixture failure\n')
            receipt.setdefault('native_commands',[]).append(dict(argv=command,returncode=7))
            raise ValueError('actual native fixture failed')
        with patch.object(audit.sys,'platform','linux'),patch.object(audit.os,'geteuid',return_value=1000),\
             patch.object(audit,'run_native',side_effect=fail),patch.object(audit.shutil,'disk_usage',return_value=shutil._ntuple_diskusage(100<<30,0,100<<30)):
            self.assertEqual(audit.execute(project,specification,audit.sha(specification)),2)
        receipt = json.loads((self.root/'audit/receipt.json').read_text())
        self.assertEqual(receipt['native_commands'][0]['returncode'],7)
        self.assertEqual(receipt['status'],'failed_native_or_evidence')
        self.assertTrue(receipt['original_unchanged'] and receipt['compiled_input_unchanged'])
        self.assertFalse(receipt['native_execution_complete'])
        self.assertEqual(audit.inventory(project),before)
        self.assertTrue((self.root/'audit/version.log').is_file())


def rebind_clock_markers(log):
    import re
    return re.sub(r'^(PLAIN_POSTFIT\tCLOCK\t\S+\tkernel_clk)\t([^\n]+)$',
        r'\1\tbase\tclk\t\2\tns',log,flags=re.M)


if __name__ == '__main__': unittest.main()
