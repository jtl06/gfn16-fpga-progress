"""r54 post-fit STA only: admitted completed PROJECT -> fresh private copy.

Flat worker CLI: PROJECT --spec ABS_JSON --spec-sha256 PIN. The fit owner
supplies the immutable packet and owns admission/locks/cgroup/budget/runtime.
This helper never launches a service, fits, edits the original, chooses a clock
from Fmax, or grants promotion. No unrelated system-Python fingerprint gate.

Native commands/parser/delta semantics reuse the qualified selected9668 v3
flow (the candidate-specific adapter is not imported): postfit_rootfused85 Tcl02e9ef0e,
aws_postfit_rootfused85 d0a53c22 and crtmont_a1 8bd932e1. Additions are explicit
period/project parameters, ns units, clean environment and retained negatives.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import time

VERSION = '26.1.0 Build 110'
MARK = 'PLAIN_POSTFIT'
SUFFIX = b'set_global_assignment -name LAST_QUARTUS_VERSION "26.1.0 Pro Edition"\n'
CORNERS = {'Slow 900mV 100C Model', 'Slow 900mV 0C Model', 'Fast 900mV 100C Model', 'Fast 900mV 0C Model'}
TYPES = ('setup', 'hold', 'recovery', 'removal', 'mpw')
REPORTS = ['clocks.rpt', 'sdc.rpt', 'ignored.rpt', 'effective.sdc', 'mpw-summary.rpt',
           'mpw-paths.rpt', 'ucp-paths.rpt', 'ucp-summary.rpt', 'checks.rpt'] + [
           f'{kind}-{suffix}.rpt' for kind in TYPES[:-1] for suffix in ('summary','paths','exceptions')]
UCP_KEYS = ('Illegal Clocks', 'Unconstrained Clocks', 'Unconstrained Input Ports',
            'Paths from Unconstrained Input Ports (Pairs-Only)', 'Unconstrained Output Ports',
            'Paths to Unconstrained Output Ports (Pairs-Only)')
# EXACT native-qualified non-circuit outputs, not directory/glob allowances.
REPORT_OUTPUTS = frozenset('qdb/_compiler/probe/_flat/26.1.0/_all/1/'+name for name in
    ('report.cmp.model','report.cmp.rdb','report.taw.model','report.taw.rdb'))
CACHE_PROMOTIONS = {'qdb/_compiler/probe/root_partition/26.1.0/final/1/'+name:
    'qdb/_compiler/probe/root_partition/26.1.0/routed/1/'+name for name in
    ('nightfury_io_sim_cache.900mv_ss_100c_slow.model', '.cache/nightfury_io_sim_cache.900mv_ss_100c_slow.hsd')}
PREFLIGHT = {
    'project_open':['-preserve_revision_order','-revision'], 'create_timing_netlist':['-snapshot','-model'],
    'read_sdc':[], 'create_clock':['-name','-period','-waveform'], 'derive_clock_uncertainty':[],
    'get_available_operating_conditions':[], 'get_operating_conditions_info':['-display_name','-is_hold_only'],
    'set_operating_conditions':[], 'get_clock_info':['-targets','-type','-period','-waveform'],
    'get_node_info':['-name'], 'get_clocks':[], 'get_collection_size':[], 'report_clocks':['-file'],
    'set_time_format':['-unit','-decimal_places'], 'create_timing_summary':['-setup','-hold','-recovery','-removal','-mpw','-file'],
    'report_timing':['-setup','-hold','-recovery','-removal','-show_routing','-file','-npaths','-detail'],
    'report_min_pulse_width':['-type','-nworst','-file'], 'report_ucp':['-summary','-file'],
    'check_timing':['-include','-file'], 'report_sdc':['-ignored','-file'],
    'report_exceptions':['-setup','-hold','-recovery','-removal','-file'], 'write_sdc':['-expand'],
    'update_timing_netlist':[], 'delete_timing_netlist':[], 'project_close':['-dont_export_assignments']}
SPEC_KEYS = {'schema','project','output','scope','pins','original_tree_sha256','qdb_inventory_sha256',
             'baseline_period_ns','selected_period_ns','selection_reason','snapshot','revision','clock','clock_port',
             'tool_version','tool_sha256','helper_sha256','tcl','tcl_sha256','maximum_copy_bytes',
             'native_seconds','path_limit','terminal_receipt','terminal_receipt_sha256'}


def need(ok, why):
    if not ok: raise ValueError(why)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def pin(path):
    path = Path(path)
    need(path.is_absolute() and path.resolve() == path and path.is_file() and path.stat().st_nlink == 1,
         'canonical regular file: '+str(path))
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4<<20),b''): h.update(block)
    return dict(sha256=h.hexdigest(),size=path.stat().st_size)


def sha(path): return pin(path)['sha256']


def save(path, value):
    with path.open('x') as stream:
        json.dump(value,stream,sort_keys=True,indent=2,allow_nan=False); stream.write('\n')


def inventory(root):
    need(root.is_absolute() and root.resolve() == root and root.is_dir(),'canonical existing tree')
    files = {}
    for directory,dirs,names in os.walk(root,followlinks=False):
        for name in dirs+names:
            path = Path(directory)/name; info = path.lstat()
            need(stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode),'link/special node refused: '+str(path))
            if stat.S_ISREG(info.st_mode): files[str(path.relative_to(root))] = pin(path)
    return files


def qdb_inventory(files): return {name:row for name,row in files.items() if name.startswith('qdb/')}


def period(raw):
    need(isinstance(raw,str) and re.fullmatch(r'\d+(?:\.\d{1,3})?',raw),'plain explicit period, <=3 decimal places')
    value = Decimal(raw); ps = value*1000
    need(2 <= value <= 100 and ps == ps.to_integral_value() and int(ps)%2 == 0,'2..100ns and even-picosecond period')
    return float(value)


def source_sdc(text, expected_period):
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')]
    need(len(lines) == 2,'unknown original SDC command/selector')
    match = re.fullmatch(r'create_clock -name kernel_clk -period (\d+(?:\.\d{1,3})?) \[get_ports \{clk\}\]',lines[0])
    need(match and period(match[1]) == period(expected_period),'original clock period/name/port')
    need(lines[1:] == ['derive_clock_uncertainty'],
         'unknown original SDC uncertainty/reset selector')


def effective_sdc(text, expected_period):
    text = re.sub(r'\\\r?\n\s*',' ',text)
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')]
    clocks = [line for line in lines if line.startswith('create_clock ')]
    need(len(clocks) == 1,'effective clock closure')
    match = re.fullmatch(r'create_clock -name \{kernel_clk\} -period (\d+(?:\.\d{1,3})?) -waveform \{\s*([\d.]+) ([\d.]+)\s*\} \[get_ports \{clk\}\]',clocks[0])
    need(match and float(match[1]) == period(expected_period) and float(match[2]) == 0 and
         float(match[3]) == period(expected_period)/2,'effective clock/port/period/waveform')
    stable = []
    uncertainty = []
    for line in lines:
        if line in clocks: continue
        if line.startswith('set_clock_uncertainty '):
            match = re.fullmatch(r'set_clock_uncertainty -(rise|fall)_from \[get_clocks \{kernel_clk\}\] -(rise|fall)_to \[get_clocks \{kernel_clk\}\]\s+([\d.]+)',line)
            need(match and math.isfinite(float(match[3])) and float(match[3]) >= 0,'unknown uncertainty selector/value')
            uncertainty.append((match[1],match[2])); continue
        stable.append(line)
    need(len(uncertainty) == 4 and set(uncertainty) == {('rise','rise'),('rise','fall'),('fall','rise'),('fall','fall')},
         'complete native uncertainty edge-pair coverage')
    need(stable == ['set_time_format -unit ns -decimal_places 3'],
         'unknown/changed effective SDC exception/units/selector')
    return stable


def rows(text):
    return [[value.strip() for value in line.strip().strip(';').split(';')]
            for line in text.splitlines() if line.lstrip().startswith(';')]


def table(text,title,header):
    matches = list(re.finditer(r'^; '+re.escape(title)+r'\s*;\s*$',text,re.M))
    need(len(matches) == 1,'unique table: '+title)
    result = []; begun = False; closed = False
    for line in text[matches[0].end():].splitlines():
        value = rows(line)
        if not begun:
            if value: need(value == [header],'native header: '+title); begun = True
            continue
        if value: result.extend(value)
        elif result:
            need(re.fullmatch(r'\+(?:-+\+)+',line.strip()),'native closing border: '+title)
            closed = True; break
    need(begun and result and closed,'empty/truncated native table: '+title)
    return result


def unconstrained(text):
    values = table(text,'Unconstrained Paths Summary',['Property','Setup','Hold'])
    need(len(values) == len(UCP_KEYS),'UCP row closure')
    result = {}
    for name,row in zip(UCP_KEYS,values):
        need(len(row) == 3 and row[0] == name and all(re.fullmatch(r'\d+',v) for v in row[1:]),'UCP row/selector/count')
        result[name] = list(map(int,row[1:]))
    need(result['Illegal Clocks'] == result['Unconstrained Clocks'] == [0,0],'illegal/unconstrained native clock')
    return result


def summary(text,kind,hold_only=False):
    no_paths = 'No paths to report.' in text
    values = [row for row in rows(text) if row and row[0] == 'kernel_clk']
    if kind in ('recovery','removal') and no_paths and not values:
        return dict(status='excluded_no_paths',slack_ns=None,tns_ns=None,failing_endpoints=None)
    if hold_only and no_paths and not values and kind in ('setup','mpw'):
        return dict(status='unsupported_at_hold_only_corner',slack_ns=None,tns_ns=None,failing_endpoints=None)
    need(not no_paths and len(values) == 1 and len(values[0]) in (4,5,6),'one native '+kind+' summary')
    extra = values[0][4:]
    if kind == 'mpw':
        need(not extra or (extra[0] in ('High Pulse','Low Pulse') and (len(extra) == 1 or extra[1] in CORNERS)),
             'known native MPW pulse type/corner')
    else: need(not extra or (len(extra) == 1 and extra[0] in CORNERS),'known native global worst-case corner')
    slack,tns = map(float,values[0][1:3]); failing = int(values[0][3])
    need(math.isfinite(slack) and math.isfinite(tns) and tns <= 0 and failing >= 0,'native WNS/TNS/failing numeric')
    need((failing == 0 and tns == 0 and slack >= 0) or (failing > 0 and tns < 0 and slack < 0),
         'native WNS/TNS/failing consistency')
    return dict(status='measured',slack_ns=slack,tns_ns=tns,failing_endpoints=failing,
                closes=(slack >= 0 and tns == 0 and failing == 0))


def clock_report(text,expected_period):
    values = table(text,'Clocks',['Clock Name','Type','Period','Frequency','Rise','Fall','Duty Cycle',
        'Divide by','Multiply by','Phase','Offset','Edge List','Edge Shift','Inverted','Master','Source','Targets'])
    need(len(values) == 1 and len(values[0]) == 17,'one native clock property row')
    row = values[0]; value = period(expected_period)
    need(row[:2] == ['kernel_clk','Base'] and row[-1] == '{ clk }' and all(not field for field in row[6:16]),
         'native clock properties/name/type/target/generation')
    need(float(row[2]) == value and float(row[4]) == 0 and float(row[5]) == value/2,'native clock period/waveform')
    need(re.fullmatch(r'\d+(?:\.\d+)? MHz',row[3]) and abs(float(row[3].split()[0])-1000/value) <= .011,'clock frequency readback')
    return dict(name=row[0],type=row[1],target='clk',period_ns=value,waveform_ns=[0,value/2],
                reported_frequency=row[3],raw_properties=row)


def paths(text,corner,expected_period,limit):
    matches = re.findall(r'Report Timing: Found (\d+) setup paths \((\d+) violated\)',text)
    need(len(matches) == 1,'one setup path count')
    count,violated = map(int,matches[0]); need(0 < count <= limit and 0 <= violated <= count,'finite setup count')
    need(re.findall(r'^Snapshot:\s*\n\s*(\S+)',text,re.M) == ['final'],'actual final snapshot required')
    need(re.findall(r'^Delay Model:\s*\n\s*([^\n]+)',text,re.M) == [corner],'actual selected native corner')
    values = table(text,'Summary of Paths',['Slack','From Node','To Node','Launch Clock','Latch Clock',
        'Relationship','Clock Skew','Data Delay'])
    need(len(values) == count,'path summary/count closure')
    result = []
    for rank,row in enumerate(values,1):
        need(len(row) == 8 and row[1] and row[2] and row[3:5] == ['kernel_clk','kernel_clk'],'path names/clocks/columns')
        slack,relationship,skew,delay = map(float,(row[0],row[5],row[6],row[7]))
        need(all(math.isfinite(x) for x in (slack,relationship,skew,delay)) and delay >= 0 and
             abs(relationship-period(expected_period)) < 1e-6,'unknown setup relationship/nonfinite timing')
        result.append(dict(corner=corner,rank_in_corner=rank,slack_ns=slack,from_node=row[1],to_node=row[2],
            launch_clock=row[3],latch_clock=row[4],relationship_ns=relationship,clock_skew_ns=skew,data_delay_ns=delay))
    details = re.findall(r'^Path #(\d+): Setup slack is (-?[\d.]+)',text,re.M)
    need(len(details) == count and [int(rank) for rank,_ in details] == list(range(1,count+1)) and
         all(abs(float(slack)-row['slack_ns']) < 1e-6 for (_,slack),row in zip(details,result)),
         'numbered native detail/slack closure')
    need(sum(row['slack_ns'] < 0 for row in result) == violated and
         [row['slack_ns'] for row in result] == sorted(row['slack_ns'] for row in result),'violated count/path ordering')
    return result


def baseline_summary(text,expected_period):
    need(VERSION in text and 'Multicorner Timing Analysis Summary' in text,'completed native version/MCMM report')
    result = {}
    for kind,title in [('setup','Setup'),('hold','Hold'),('mpw','Minimum Pulse Width')]:
        matches = list(re.finditer(r'^; '+title+r' Summary\s*;\s*$',text,re.M)); need(len(matches) == 1,'global '+kind+' section')
        tail = text[matches[0].end():]; end = tail.find('Delay Models:'); need(end >= 0,'global native model scope')
        result[kind] = summary(tail[:end],kind)
        declared = tail[end:].split('\n\n',1)[0].splitlines()[1:]
        need(len(declared) == 4 and set(declared) == CORNERS,'four global native delay models')
    result['unconstrained'] = unconstrained(text)
    result['clock'] = clock_report(text,expected_period)
    return result


def parse_preflight(text):
    markers = [line for line in text.splitlines() if line.startswith(MARK+'\t')]
    expected = []
    for command,options in PREFLIGHT.items():
        matches = re.findall(r'^'+MARK+r'\tHELP_BEGIN\t'+command+r'\n(.*?)^'+MARK+r'\tHELP_END\t'+command+r'$',text,re.M|re.S)
        need(len(matches) == 1 and command in matches[0] and all(option in matches[0] for option in options),
             'missing/unsupported native help: '+command)
        if command == 'project_open':
            normalized = ' '.join(matches[0].split())
            need('Belongs to ::quartus::project2 1.0' in normalized and
                 'project_open command gives an error when the compilation database version is not compatible' in normalized and
                 'specify the "-force" option to avoid the error and overwrite the database' in normalized,
                 'native DB incompatibility refusal')
        expected += [MARK+'\tHELP_BEGIN\t'+command,MARK+'\tHELP_END\t'+command]
    need(markers == expected+[MARK+'\tPREFLIGHT_COMPLETE'],'ordered full help closure')
    need(not re.search(r'^(?:Error|Fatal)(?:\s|:|\()',text,re.M|re.I),'native help error')


def parse_results(directory,log,spec,baseline):
    phases = [('baseline',spec['baseline_period_ns'])]
    if spec['selected_period_ns'] is not None: phases.append(('selected',spec['selected_period_ns']))
    markers = [line for line in log.splitlines() if line.startswith(MARK+'\t')]
    need(not re.search(r'^(?:Error|Fatal)(?:\s|:|\()',log,re.M|re.I),'native STA error')
    expected_markers = []; expected_files = set(); result = {}; mapping = {}; stable_reference = {}
    for phase,target in phases:
        clocks = re.findall(r'^'+MARK+r'\tCLOCK\t'+phase+r'\tkernel_clk\tbase\tclk\t(\S+)\t(\S+)\t(\S+)\tns$',log,re.M)
        need(len(clocks) == 1 and all(math.isfinite(float(x)) for x in clocks[0]) and
             all(abs(float(x)-v) < 1e-6 for x,v in zip(clocks[0],(period(target),0,period(target)/2))),
             'phase native clock/type/port/units/period/waveform')
        expected_markers.append(MARK+'\tCLOCK\t'+phase+'\tkernel_clk\tbase\tclk\t'+'\t'.join(clocks[0])+'\tns')
        entries = re.findall(r'^'+MARK+r'\tBEGIN\t'+phase+r'\t([0-3])\t([^\t\n]+)\t([01])$',log,re.M)
        need(len(entries) == 4 and [row[0] for row in entries] == list('0123') and {row[1] for row in entries} == CORNERS,'four ordered native corners')
        corners = {}; observed = []
        for index,name,hold_only in entries:
            expected_markers += [MARK+'\t'+kind+'\t'+phase+'\t'+'\t'.join((index,name,hold_only)) for kind in ('BEGIN','END')]
            prefix = phase+'-'+index+'-'
            expected_files.update(prefix+suffix for suffix in REPORTS)
            texts = {}
            for suffix in REPORTS:
                path = directory/(prefix+suffix); need(pin(path)['size'] > 0,'empty timing artifact')
                texts[suffix] = path.read_text()
            values = {kind:summary(texts[kind+'-summary.rpt'],kind,hold_only == '1') for kind in TYPES}
            values['tool_declared_hold_only'] = hold_only == '1'
            values['clock'] = clock_report(texts['clocks.rpt'],target)
            values['unconstrained'] = unconstrained(texts['ucp-summary.rpt'])
            need(values['unconstrained'] == baseline['unconstrained'],'native UCP coverage changed')
            stable = effective_sdc(texts['effective.sdc'],target)
            if phase == 'baseline': mapping[index] = (name,hold_only); stable_reference[name] = stable
            else:
                need(mapping[index] == (name,hold_only) and stable == stable_reference[name],'native corner/constraint coverage changed')
                need(all(values[kind]['status'] == result['baseline']['corners'][name][kind]['status'] for kind in TYPES),
                     'native supported-analysis coverage changed')
            if values['setup']['status'] == 'measured':
                native_paths = paths(texts['setup-paths.rpt'],name,target,spec['path_limit'])
                need(abs(native_paths[0]['slack_ns']-values['setup']['slack_ns']) <= .0011,'setup worst path/summary binding')
                observed.extend(native_paths)
            corners[name] = values
        ordered = sorted(observed,key=lambda row:(row['slack_ns'],row['corner'],row['rank_in_corner']))
        measured = [row[kind] for row in corners.values() for kind in TYPES if row[kind]['status'] == 'measured']
        need(measured and all(any(row[kind]['status'] == 'measured' for row in corners.values()) for kind in ('setup','hold','mpw')),
             'no supported setup/hold/MPW measurement')
        result[phase] = dict(period_ns=period(target),frequency_mhz=1000/period(target),corners=corners,
            timing_closes=all(row['closes'] for row in measured),observed_setup_paths=len(ordered),
            observed_failing_setup_paths=sum(row['slack_ns'] < 0 for row in ordered),worst_setup_observations=ordered[:1000],
            path_scope='Up to requested1000 per supported corner; global worst1000 observations, not unique endpoints or exhaustive graph.')
    need(markers == expected_markers+[MARK+'\tCOMPLETE'],'full ordered native completion')
    need({path.name for path in directory.iterdir()} == expected_files,'exact timing artifact closure')
    for kind in ('setup','hold','mpw'):
        measured = [row[kind]['slack_ns'] for row in result['baseline']['corners'].values() if row[kind]['status'] == 'measured']
        need(abs(min(measured)-baseline[kind]['slack_ns']) <= .0011,'original target MCMM replay '+kind)
    return result


def verify_project(project,spec):
    for name,expected in spec['pins'].items():
        relative = Path(name)
        need(not relative.is_absolute() and '..' not in relative.parts,'closed pinned project path')
        need(sha(project/relative) == expected,'pinned completed project: '+name)
    manifest = json.loads((project/'manifest.json').read_text()); context = json.loads((project/'execution-context.json').read_text())
    execution = json.loads((project/'execution-result.json').read_text()); guard = json.loads((project/'plain-final-source-guard.json').read_text())
    required = {'manifest.json','execution-context.json','execution-result.json','plain-final-source-guard.json',
        'database-inventory-final.json','output_files/probe.fit.summary','output_files/probe.sta.rpt'}
    need(required <= spec['pins'].keys(),'completed evidence pin closure')
    need(execution['quartus_returncode'] == execution['summarize_returncode'] == 0 and execution.get('finished_at') and
         execution['context_sha256'] == sha(project/'execution-context.json'),'successful terminal native context/result')
    need(guard.get('unchanged') is True and guard.get('drift') == [] and guard.get('vendor_returncode') == 0,'terminal source guard')
    need(context['manifest_sha256'] == sha(project/'manifest.json') and context['source_sha256'] == manifest['source_sha256'] and
         context['control_sha256'] == {'manifest.json':sha(project/'manifest.json'),**manifest['control_sha256']},'completed manifest/source/settings context')
    need(manifest['device'] == '10AX115N4F40E3SG' and re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',manifest['top']) and
         period(str(manifest['clock_period_ns'])) == period(spec['baseline_period_ns']),'supported device/top/actual baseline target')
    need(manifest['source_sha256'] and {path.name for path in (project/'rtl').iterdir()} == set(manifest['source_sha256']),
         'exact RTL source closure')
    for name,expected in manifest['source_sha256'].items():
        need(Path(name).name == name and sha(project/'rtl'/name) == expected,'source drift: '+name)
        need(spec['pins'].get('rtl/'+name) == expected,'pinned actual source closure')
    need(set(manifest['control_sha256']) == {'probe.qsf','probe.qpf','probe.sdc','run.tcl'},'known plain control closure')
    for name,expected in manifest['control_sha256'].items():
        raw = (project/name).read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        need(actual == expected or (name == 'probe.qsf' and raw.endswith(SUFFIX) and
             hashlib.sha256(raw[:-len(SUFFIX)]).hexdigest() == expected),'control drift: '+name)
        need(spec['pins'].get(name) == sha(project/name),'actual raw control pin: '+name)
    source_sdc((project/'probe.sdc').read_text(),spec['baseline_period_ns'])
    fit = (project/'output_files/probe.fit.summary').read_text()
    need(re.search(r'^Fitter Status\s*:\s*Successful',fit,re.M) and VERSION in fit and manifest['top'] in fit and manifest['device'] in fit,
         'completed successful version/top/device fit')
    receipt = json.loads(Path(spec['terminal_receipt']).read_text())
    need(sha(Path(spec['terminal_receipt'])) == spec['terminal_receipt_sha256'] and receipt.get('schema') == 'plain-fit-terminal-collection-v1' and
         receipt.get('collection_completed') is True and receipt.get('native_job_succeeded') is True and receipt.get('terminal_proven') is True and receipt.get('project') == str(project) and
         receipt.get('scope') == spec['scope'] and not receipt.get('findings'),'exact original invocation terminal receipt/scope')
    need(receipt['native_journal_proof']['terminal_kind'] == 'deactivated_successfully' and receipt.get('native_result') == execution and
         re.fullmatch('[0-9a-f]{32}',receipt['invocation_id']),'original invocation successful manager/source-bound result')
    return manifest,baseline_summary((project/'output_files/probe.sta.rpt').read_text(),spec['baseline_period_ns'])


def validate_spec(project,spec):
    need(set(spec) == SPEC_KEYS and spec['schema'] == 'plain-fit-postfit-audit-v1','exact audit spec schema/selectors')
    need(spec['project'] == str(project) and spec['scope'] in ('whole_core','component_probe') and
         (spec['snapshot'],spec['revision'],spec['clock'],spec['clock_port'],spec['tool_version']) ==
         ('final','probe','kernel_clk','clk',VERSION),'exact project/snapshot/revision/clock/tool version')
    need(period(spec['baseline_period_ns']) > 0,'baseline period')
    if spec['selected_period_ns'] is not None:
        need(period(spec['selected_period_ns']) != period(spec['baseline_period_ns']) and isinstance(spec['selection_reason'],str) and
             len(spec['selection_reason'].strip()) >= 8,'explicit distinct selected period/reason, never implicit Fmax')
    else: need(spec['selection_reason'] is None,'selection reason without selected clock')
    need(type(spec['path_limit']) is int and 1 <= spec['path_limit'] <= 1000,'setup path cap')
    need(type(spec['native_seconds']) is int and 1 <= spec['native_seconds'] <= 21600 and
         type(spec['maximum_copy_bytes']) is int and 0 < spec['maximum_copy_bytes'] <= 64<<30,'finite native/copy bounds')
    for value in (spec['original_tree_sha256'],spec['qdb_inventory_sha256'],spec['helper_sha256'],spec['tcl_sha256'],spec['terminal_receipt_sha256']):
        need(re.fullmatch('[0-9a-f]{64}',value),'exact evidence digest')
    tool_paths = [Path(path) for path in spec['tool_sha256']]
    need(len(tool_paths) == 2 and {tuple(path.parts[-2:]) for path in tool_paths} == {('bin','quartus_sta'),('linux64','quartus_sta')} and
         len({path.parent.parent for path in tool_paths}) == 1 and tool_paths[0].parent.parent.name == 'quartus' and
         tool_paths[0].parent.parent.parent.name == '26.1','exact installed Quartus26.1 wrapper/payload selectors')
    need(all(re.fullmatch('[0-9a-f]{64}',value) for value in spec['tool_sha256'].values()),'native tool pins')
    output = Path(spec['output'])
    need(project.is_absolute() and project.resolve() == project and project.is_dir() and output.is_absolute() and
         output.resolve() == output and output.parent == project.parent and not output.exists(),'fresh canonical sibling output')
    need(sha(Path(__file__).resolve()) == spec['helper_sha256'] and sha(Path(spec['tcl'])) == spec['tcl_sha256'],'source-pinned helper/Tcl')
    return output


def make_spec(project,output,terminal_receipt,tcl,tool_sha256,*,scope,native_seconds,maximum_copy_bytes,
              selected_period_ns=None,selection_reason=None,path_limit=1000):
    """Data/inventory only; called inside the fit owner's admitted initializer.

    The owner's outer request must already pin manifest/context/result/receipt
    and enforce actual terminal unit/resources/PAUSE/host-hours. This function
    does not grant that admission or execute a native command. Write the result
    OUTSIDE original/output and pass its SHA explicitly to the flat worker CLI.
    """
    project,output,terminal_receipt,tcl = map(Path,(project,output,terminal_receipt,tcl))
    manifest = json.loads((project/'manifest.json').read_text())
    names = {'manifest.json','execution-context.json','execution-result.json','plain-final-source-guard.json',
        'database-inventory-final.json','output_files/probe.fit.summary','output_files/probe.sta.rpt',
        *manifest['control_sha256'],*('rtl/'+name for name in manifest['source_sha256'])}
    before = inventory(project); qdb = qdb_inventory(before)
    need(qdb and json.loads((project/'database-inventory-final.json').read_text()) == qdb,
         'actual QDB matches immutable native final inventory')
    spec = dict(schema='plain-fit-postfit-audit-v1',project=str(project),output=str(output),scope=scope,
        pins={name:sha(project/name) for name in sorted(names)},original_tree_sha256=digest(before),
        qdb_inventory_sha256=digest(qdb),baseline_period_ns=str(manifest['clock_period_ns']),
        selected_period_ns=selected_period_ns,selection_reason=selection_reason,snapshot='final',revision='probe',
        clock='kernel_clk',clock_port='clk',tool_version=VERSION,tool_sha256=tool_sha256,
        helper_sha256=sha(Path(__file__).resolve()),tcl=str(tcl),tcl_sha256=sha(tcl),
        maximum_copy_bytes=maximum_copy_bytes,native_seconds=native_seconds,path_limit=path_limit,
        terminal_receipt=str(terminal_receipt),terminal_receipt_sha256=sha(terminal_receipt))
    validate_spec(project,spec); verify_project(project,spec)
    return spec


def differences(before,after):
    result = {}
    for name in sorted(set(before)|set(after)):
        if before.get(name) == after.get(name): continue
        row = dict(change='added' if name not in before else 'deleted' if name not in after else 'changed',
                   before=before.get(name),after=after.get(name),allowed=False,kind='unreviewed_delta')
        if name in REPORT_OUTPUTS and row['change'] in ('added','changed'):
            row.update(allowed=after[name]['size'] > 0,kind='exact_report_output')
        elif name in CACHE_PROMOTIONS and row['change'] == 'changed':
            source = CACHE_PROMOTIONS[name]
            row.update(kind='exact_cache_promotion',source=source,allowed=(source in before and
                after.get(source) == before[source] and after[name] == before[source]))
        result[name] = row
    return result


def equal_bytes(left,right):
    with left.open('rb') as a,right.open('rb') as b:
        while True:
            x,y = a.read(1<<20),b.read(1<<20)
            if x != y: return False
            if not x: return True


def check_copy(receipt,original,copied,before):
    after = inventory(copied); delta = differences(before,after)
    receipt.update(snapshot_after=after,snapshot_differences=delta,
        compiled_input_unchanged=all(row['allowed'] for row in delta.values()),cache_promotion_byte_comparisons={})
    for name,row in delta.items():
        if row['kind'] == 'exact_report_output' and row['allowed']:
            model_name = name if name.endswith('.model') else name[:-4]+'.model'
            try:
                model = json.loads((copied/model_name).read_text())
                need(set(model) == {'type','trait','temp_payload_path','signature','bak'} and
                     model['type'] == 'rdb' and model['trait'] == 'undefined' and model['temp_payload_path'] == '' and
                     re.fullmatch('[0-9a-f]{32}',model['signature']) and model['bak'] is False,
                     'exact non-circuit native report-model schema')
                payload_name = model_name[:-6]+'.rdb'
                need(pin(copied/payload_name)['size'] > 0,'report model/payload pair')
                row['native_report_model_verified'] = True
            except BaseException as error:
                row.update(allowed=False,native_report_model_verified=False,classification_error=repr(error))
        if row['kind'] == 'exact_cache_promotion' and row['allowed']:
            value = equal_bytes(original/row['source'],copied/name)
            receipt['cache_promotion_byte_comparisons'][name] = value; row['allowed'] = value
    receipt['compiled_input_unchanged'] = all(row['allowed'] for row in delta.values())
    need(receipt['compiled_input_unchanged'],'unreviewed private-copy delta (all changed paths retained)')


def clean_environment():
    return {'HOME':os.environ['HOME'],'PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C'}


def run_native(command,cwd,log,seconds,receipt):
    need(seconds > 0,'native diagnostic runtime exhausted')
    row = dict(argv=command,log=str(log),timeout_seconds=seconds,started_at=datetime.now(timezone.utc).isoformat())
    receipt.setdefault('native_commands',[]).append(row)
    with log.open('x') as stream:
        child = subprocess.Popen(command,cwd=cwd,stdout=stream,stderr=subprocess.STDOUT,
            start_new_session=True,env=clean_environment())
        try: code = child.wait(timeout=seconds)
        except BaseException:
            for sig in (signal.SIGTERM,signal.SIGKILL):
                try: os.killpg(child.pid,sig)
                except ProcessLookupError: pass
                try: child.wait(timeout=5)
                except subprocess.TimeoutExpired: continue
                break
            child.wait(); row['returncode'] = child.returncode; raise
    row.update(returncode=code,finished_at=datetime.now(timezone.utc).isoformat(),log_sha256=sha(log))
    need(code == 0,'native command failed '+str(code))


def execute(project,spec_path,spec_pin):
    need(sys.platform == 'linux' and os.geteuid() != 0,'native audit only on admitted nonroot Linux worker')
    need(sha(spec_path) == spec_pin,'externally pinned audit specification')
    spec = json.loads(spec_path.read_text()); output = validate_spec(project,spec)
    manifest,baseline = verify_project(project,spec)
    before = inventory(project); qdb = qdb_inventory(before)
    need(qdb and digest(before) == spec['original_tree_sha256'] and digest(qdb) == spec['qdb_inventory_sha256'],
         'exact original full-tree/QDB identity')
    need(json.loads((project/'database-inventory-final.json').read_text()) == qdb,'compiled DB matches native final inventory')
    size = sum(row['size'] for row in before.values())
    need(size <= spec['maximum_copy_bytes'] and shutil.disk_usage(project.parent).free >= size+(10<<30),
         'bounded private copy and10GiB additional disk floor')
    for path,expected in spec['tool_sha256'].items(): need(sha(Path(path)) == expected,'exact native tool: '+path)
    output.mkdir(); copied = output/'snapshot'; timing = output/'timing'
    receipt = dict(schema='plain-fit-postfit-audit-result-v1',status='running',project=str(project),scope=spec['scope'],
        spec_sha256=spec_pin,helper_sha256=spec['helper_sha256'],tcl_sha256=spec['tcl_sha256'],
        tool_sha256=spec['tool_sha256'],source_pins=spec['pins'],original_before=before,
        original_tree_sha256=digest(before),qdb_inventory_sha256=digest(qdb),snapshot_bytes=size,
        started_at=datetime.now(timezone.utc).isoformat(),fit_commands=0,promotion_allowed=False,independent_review=False,
        board_io_signoff=False,reset_release_signoff=False,exhaustive_cross_block_coverage=False,
        scope_limitations='Final retained layout internal compute STA only; virtual I/O and reset release excluded. Finite paths are not graph coverage, arithmetic/PRP proof or proof of highest clock.')
    save(output/'context.json',receipt)
    deadline = time.monotonic()+spec['native_seconds']
    tool = next(path for path in spec['tool_sha256'] if Path(path).parent.name == 'bin'); script = spec['tcl']
    previous_term = signal.getsignal(signal.SIGTERM)
    def terminate(signum,frame): raise RuntimeError('audit service terminated; preserve evidence')
    signal.signal(signal.SIGTERM,terminate)
    try:
        shutil.copytree(project,copied,copy_function=shutil.copy2,symlinks=False)
        need(inventory(copied) == before,'private copy bytes')
        need(all(not os.path.samestat((project/name).stat(),(copied/name).stat()) for name in before),'private copy aliases original')
        timing.mkdir()
        run_native([tool,'--version'],output,output/'version.log',min(30,deadline-time.monotonic()),receipt)
        need(VERSION in (output/'version.log').read_text(),'exact native reported Quartus version')
        run_native([tool,'-t',script,'preflight'],output,output/'native-help.log',min(120,deadline-time.monotonic()),receipt)
        parse_preflight((output/'native-help.log').read_text())
        command = [tool,'-t',script,str(copied),str(timing),manifest['top'],manifest['device'],
            spec['baseline_period_ns'],spec['selected_period_ns'] or '-',str(spec['path_limit'])]
        run_native(command,output,output/'audit.log',deadline-time.monotonic(),receipt)
        receipt['timing'] = parse_results(timing,(output/'audit.log').read_text(),spec,baseline)
        audit_phase = 'selected' if spec['selected_period_ns'] is not None else 'baseline'
        closes = receipt['timing'][audit_phase]['timing_closes']
        receipt.update(status='native_scoped_timing_closes_pending_independent_review' if closes else 'native_timing_violation',
            native_execution_complete=True,timing_closes=closes,assessed_phase=audit_phase,audited_clock_promotion=False)
    except BaseException as error:
        receipt.update(status='failed_native_or_evidence',error=repr(error),native_execution_complete=False,timing_closes=False)
    finally:
        errors = []
        for check in ('original','copy','sources_tools_spec'):
            try:
                if check == 'original':
                    after = inventory(project); receipt.update(original_after=after,original_unchanged=after == before)
                    need(after == before,'ORIGINAL project/source/QDB mutated')
                elif check == 'copy':
                    if copied.is_dir(): check_copy(receipt,project,copied,before)
                else:
                    need(sha(spec_path) == spec_pin and sha(Path(__file__).resolve()) == spec['helper_sha256'] and
                         sha(Path(script)) == spec['tcl_sha256'],'helper/Tcl/spec drift')
                    for path,expected in spec['tool_sha256'].items(): need(sha(Path(path)) == expected,'native tool drift')
                    verify_project(project,spec)
            except BaseException as error: errors.append(check+': '+repr(error))
        if errors: receipt.update(status='failed_native_or_evidence',timing_closes=False)
        receipt.update(final_verification_errors=errors,finished_at=datetime.now(timezone.utc).isoformat(),
            audit_files={str(path.relative_to(output)):pin(path) for path in output.rglob('*') if path.is_file() and not path.is_relative_to(copied)})
        save(output/'receipt.json',receipt)
        signal.signal(signal.SIGTERM,previous_term)
    return 0 if receipt['status'] == 'native_scoped_timing_closes_pending_independent_review' else 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project',type=Path); parser.add_argument('--spec',type=Path,required=True)
    parser.add_argument('--spec-sha256',required=True); args = parser.parse_args()
    raise SystemExit(execute(args.project,args.spec,args.spec_sha256))

