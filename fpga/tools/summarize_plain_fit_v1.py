"""Scoped interpretation of a collected plain fit; no native/host operations.

Not independent promotion review. Packing-adjusted ALM needs, raw placement,
actual MCMM slack and finite native path samples stay distinct. Unconstrained
virtual I/O and reset exceptions are reported, never silently signed off.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def need(ok, why):
    if not ok: raise ValueError(why)


def unique(text, pattern):
    result = re.findall(pattern, text, re.M)
    need(len(result) == 1, 'one native value required: '+pattern)
    return result[0]


def resources(text):
    labels = {'ALMs needed [=A-B+C]':'alms_needed', '[A] ALMs used in final placement [=a+b+c+d]':'alms_placed',
        '[B] Estimate of ALMs recoverable by dense packing':'alms_recoverable', '[C] Estimate of ALMs unavailable [=a+b+c+d]':'alms_unavailable',
        'M20K blocks':'m20k', 'DSP Blocks Needed [=A+B+C-D]':'dsp_needed', '[A] Total Fixed Point DSP Blocks':'dsp_fixed_point',
        '[B] Total Floating Point DSP Blocks':'dsp_floating_point', '[C] Total DSP_PRIME Blocks':'dsp_prime',
        '[D] Estimate of DSP Blocks recoverable by dense merging':'dsp_recoverable', 'Total block memory bits':'block_memory_bits'}
    result = {key:int(unique(text, r'^;\s*'+re.escape(label)+r'\s*;\s*([0-9,]+)').replace(',','')) for label,key in labels.items()}
    need(result['alms_needed'] == result['alms_placed']-result['alms_recoverable']+result['alms_unavailable'], 'native ALM accounting equation')
    result['dsp_placed'] = sum(result[key] for key in ('dsp_fixed_point','dsp_floating_point','dsp_prime'))
    need(result['dsp_needed'] == result['dsp_placed']-result['dsp_recoverable'], 'native DSP accounting equation')
    result['basis'] = 'Native Fitter Resource Usage Summary generated after Place. Needed totals include explicitly estimated packing recovery; placed counts are separate.'
    return result


def timing(text):
    result = {}
    for kind in ('Setup','Hold','Minimum Pulse Width'):
        section = unique(text, r'; '+kind+r' Summary\s*;([\s\S]+?)Delay Models:\n')
        result[kind.lower().replace(' ','_')+'_slack_ns'] = float(unique(section, r'^;\s*kernel_clk\s*;\s*(-?[0-9.]+)\s*;'))
    need('Multicorner Timing Analysis Summary' in text, 'actual multicorner analysis required')
    expected = ['Slow 900mV 100C Model','Slow 900mV 0C Model','Fast 900mV 100C Model','Fast 900mV 0C Model']
    need(all(corner in text for corner in expected), 'four native delay models required')
    result['native_delay_models'] = expected
    result['selected_clock_period_ns'] = float(unique(text, r'^;\s*kernel_clk\s*;\s*Base\s*;\s*([0-9.]+)\s*;'))
    result['reported_internal_fmax_mhz'] = float(unique(text, r'^;\s*([0-9.]+) MHz\s*;\s*[0-9.]+ MHz\s*;\s*kernel_clk\s*;'))
    for kind in ('setup','hold'):
        info = unique(text, r'Tcl Command:\n\s*(report_timing -'+kind+r' [^\n]+)')
        result[kind+'_native_query'] = info
        sections = re.findall(r'Report Timing: Found [0-9]+ '+kind+r' paths[\s\S]+?(?=Report Timing: Found|\Z)', text)
        need(len(sections) == 1, 'one native finite '+kind+' query')
        section = sections[0]
        result[kind+'_sample_snapshot'] = unique(section, r'^Snapshot:\s*\n\s*(\S+)')
        result[kind+'_sample_count'] = int(unique(section, r'Report Timing: Found ([0-9]+) '+kind+r' paths'))
        row = re.search(r'^;\s*(-?[0-9.]+)\s*;\s*([^;]+?)\s*;\s*([^;]+?)\s*;\s*kernel_clk\s*;\s*kernel_clk\s*;\s*([0-9.]+)\s*;\s*(-?[0-9.]+)\s*;\s*([0-9.]+)\s*;\s*([^;]+?)\s*;', section, re.M)
        need(row is not None, 'native first critical path row')
        result[kind+'_first_path'] = dict(slack_ns=float(row[1]), source=row[2].strip(), destination=row[3].strip(),
            clock_relationship_ns=float(row[4]), clock_skew_ns=float(row[5]), data_delay_ns=float(row[6]), native_corner=row[7].strip())
        need(abs(result[kind+'_first_path']['slack_ns']-result[kind+'_slack_ns']) < .0011, 'finite first path and MCMM summary agree')
    for label in ('Unconstrained Input Ports','Unconstrained Output Ports'):
        pair = unique(text, r'^;\s*'+label+r'\s*;\s*([0-9]+)\s*;\s*([0-9]+)\s*;')
        result[label.lower().replace(' ','_')] = dict(setup=int(pair[0]), hold=int(pair[1]))
    result['unconstrained_panel_status'] = unique(text, r'^;\s*Unconstrained Paths\s*;\s*(\S+)\s*;')
    result.update(exhaustive_cross_block_coverage=False, registered_stage_count_proof=False,
        board_io_signoff=False, reset_release_signoff=False, audited_clock=False)
    return result


def summarize(root, receipt_pin):
    root = Path(root).resolve(); receipt_path = root/'terminal-collection-v1.json'
    need(sha(receipt_path) == receipt_pin, 'exact collected native receipt')
    receipt = json.loads(receipt_path.read_text())
    need(receipt['terminal_proven'] and receipt['collection_completed'] and receipt['native_job_succeeded'] and not receipt['findings'], 'actual successful collected fit required')
    need(sha(root/'native-reports.tar.gz') == receipt['archive']['sha256'], 'downloaded archive identity')
    need(sha(root/'collection-inventory-v1.json') == receipt['inventory_sha256'], 'native inventory identity')
    inventory = json.loads((root/'collection-inventory-v1.json').read_text())['files']
    names = ['project/manifest.json','project/output_files/probe.fit.place.rpt','project/output_files/probe.sta.rpt',
             'project/probe.sdc','root/'+Path(receipt['project']).name+'-fit.log']
    for name in names: need(sha(root/name) == inventory[name]['sha256'], 'selected source/raw-report identity')
    manifest = json.loads((root/'project/manifest.json').read_text())
    resource = resources((root/names[1]).read_text()); sta = timing((root/names[2]).read_text()); log = (root/names[4]).read_text()
    need(sta['selected_clock_period_ns'] == manifest['clock_period_ns'], 'actual report/manifest clock period')
    wall = unique(log, r'^\s*Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): ([0-9:.]+)$')
    wall_seconds = 0.0
    for piece in wall.split(':'): wall_seconds = 60*wall_seconds+float(piece)
    command_usage = dict(wall_seconds=wall_seconds,
        user_seconds=float(unique(log,r'^\s*User time \(seconds\): ([0-9.]+)$')),
        system_seconds=float(unique(log,r'^\s*System time \(seconds\): ([0-9.]+)$')),
        percent_cpu=int(unique(log,r'^\s*Percent of CPU this job got: ([0-9]+)%$')),
        command_maximum_resident_kib=int(unique(log,r'^\s*Maximum resident set size \(kbytes\): ([0-9]+)$')))
    journal_resources = receipt['native_journal_proof']['resource_journal']
    need(len(journal_resources) == 1, 'one actual native cgroup resource event')
    measured = journal_resources[0]
    runtime = dict(**command_usage, manager_elapsed_seconds=receipt['native_journal_proof']['manager_elapsed_seconds'],
        cgroup_cpu_seconds=int(measured['CPU_USAGE_NSEC'])/1e9, cgroup_memory_peak_bytes=int(measured['MEMORY_PEAK']),
        cgroup_memory_swap_peak_bytes=int(measured['MEMORY_SWAP_PEAK']), allocation=receipt['native_context_resources'],
        comparison='Different P8/P16 candidates and four/six-worker hosts are not a matched host-slowdown benchmark.')
    return dict(schema='plain-fit-scoped-summary-v1', scope=receipt['scope'], top=manifest['top'],
        geometry=manifest.get('probe_geometry',manifest.get('geometry')), target_period_ns=manifest['clock_period_ns'], seed=manifest['seed'],
        source_manifest_sha256=sha(root/'project/manifest.json'), native_collection_receipt_sha256=receipt_pin,
        native_archive_sha256=receipt['archive']['sha256'], selected_report_sha256={name:inventory[name]['sha256'] for name in names},
        tool_version='26.1.0 Build 110 SC Pro Edition (native reports; not an exact fresh binary fingerprint)',
        parser_sha256=sha(Path(__file__)), resources=resource, timing=sta, runtime=runtime,
        compiled_db_files=receipt['compiled_db_files'], compiled_db_bytes=receipt['compiled_db_bytes'], raw_qdb_transferred=False,
        generated_at_utc=datetime.now(timezone.utc).isoformat(), independent_review=False, promotion_allowed=False,
        whole_core_clock_claim=False, production_warm_interval_claim=False,
        limitation='Exploratory scoped interpretation only. One-field virtual-pin probes are not three-field integrated-core fits, warm-controller qualification or full-size numerical PRP results. Unconstrained I/O and reset exceptions remain explicit.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('root',type=Path)
    parser.add_argument('--receipt-sha256',required=True); args = parser.parse_args()
    result = summarize(args.root,args.receipt_sha256)
    with (args.root/'scoped-summary-v1.json').open('x') as stream: json.dump(result,stream,indent=2,allow_nan=False); stream.write('\n')
    print(json.dumps(result,indent=2,allow_nan=False))
