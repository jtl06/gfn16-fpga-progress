"""Read-only architectural summary of collected finite TimeQuest path reports."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import tarfile


def parse(text):
    count = re.search(r'Report Timing: Found (\d+) setup paths', text)
    if not count:
        raise ValueError('Missing native setup-path count')
    model = re.search(r'Delay Model:\s*\n\s*([^\n]+)', text)
    if not model and int(count[1]):
        raise ValueError('Missing delay model for nonempty setup report')
    corner = model[1].strip() if model else None
    result = []
    for part in re.split(r'(?m)^Path #', text)[1:]:
        rank = int(part.split(':', 1)[0])
        def property(name):
            return re.search(r'; '+re.escape(name)+r'\s*;\s*([^;]+)', part)[1].strip()
        data = part.split(';   Data ', 1)[1].split(';  Required Path', 1)[0]
        delays = {}
        for line in data.splitlines():
            fields = [x.strip() for x in line.strip().strip(';').split(';')]
            if len(fields) == 7 and fields[0] in ('Cell', 'IC', 'Routing Element', 'uTco'):
                delays[fields[0]] = float(fields[3])
        row = dict(corner=corner, rank=rank,
                   slack_ns=float(re.search(r'Setup slack is (-?[\d.]+)', part)[1]),
                   from_node=property('From Node'), to_node=property('To Node'),
                   clock_skew_ns=float(property('Clock Skew')),
                   data_delay_ns=float(re.search(r'; Data Delay\s*;\s*([\d.]+)', part)[1]),
                   logic_levels=int(re.search(r'; Number of Logic Levels\s*;\s*;\s*(\d+)', part)[1]),
                   cell_ns=delays.get('Cell', 0), source_tco_ns=delays.get('uTco', 0),
                   wire_ns=delays.get('Routing Element', 0)+delays.get('IC', 0))
        if abs(row['cell_ns']+row['source_tco_ns']+row['wire_ns']-row['data_delay_ns']) >= .004:
            raise ValueError('Setup delay components do not sum to data delay')
        row['wire_fraction'] = round(row['wire_ns']/row['data_delay_ns'], 4)
        row['sdc_exception'] = property('SDC Exception')
        result.append(row)
    if len(result) != int(count[1]):
        raise ValueError('Setup report is truncated or path count differs')
    return result


def architecture(row):
    source, target = row['from_node'], row['to_node']
    def hierarchy(node):
        for pattern,label in (('inverse_transform','inverse_ntt'),('forward_transform','forward_ntt'),('final_image','canonical_write'),
                              ('.carry|','carry'),('|carry|','carry'),('.crt|','crt'),('|crt|','crt'),('term_producer','term'),('term_context','term')):
            if pattern in node:return label
        return 'other_unclassified'
    if source.startswith('feed_index'):
        start = 'feed_index_ram'
    elif '|remaining[' in source:
        start = 'recurrence_remaining'
    elif 'error' in source or 'fault_q' in source:
        start = 'field_fault'
    else:
        start = hierarchy(source)
    if '|magnitude_path|' in target:
        end = 'boundary_magnitude'
    elif target.endswith('arithmetic|out_error'):
        end = 'arithmetic_error'
    elif 'error' in target:
        end = 'field_error'
    else:
        end = hierarchy(target)
    return start+' -> '+end


def summary(rows):
    if not rows:
        return dict(observations=0, status='no_retained_paths', worst=None)
    worst = min(rows, key=lambda x:x['slack_ns'])
    return dict(observations=len(rows), unique_endpoint_pairs=len({(r['from_node'],r['to_node']) for r in rows}),
                corners=dict(Counter(r['corner'] for r in rows)), worst=worst)


def compact_table(result):
    lines=[f"{result['design_scope']}, {result['period_ns']:g} ns; retained setup sample, not clock closure.",
           '', '| Class | Setup ns | Wire % | Levels |', '|---|---:|---:|---:|']
    for row in result['top5_classes']:
        worst=row['worst'];label=row['architectural_class'].replace('|','/').replace(' -> ',' → ')
        lines.append(f"| {label} | {worst['slack_ns']:+.3f} | {100*worst['wire_fraction']:.1f} | {worst['logic_levels']} |")
    if not result['top5_classes']:lines.append('No retained setup paths; no timing conclusion.')
    text='\n'.join(lines)
    if len(text.encode())>1024:raise ValueError('Compact setup table exceeds1KiB')
    return text


def analyze(receipt_path, archive_path, phase='baseline'):
    if phase not in ('baseline', 'selected'):
        raise ValueError('Choose baseline or selected timing phase')
    receipt = json.loads(receipt_path.read_text())
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if digest != receipt['archive']['sha256']:
        raise ValueError('Archive hash differs from source receipt')
    if not all(receipt.get(k) is True for k in ('terminal_proven', 'original_unchanged', 'compiled_input_unchanged')) or receipt.get('fit_commands') != 0:
        raise ValueError('Requires a completed, unchanged saved-layout audit receipt')
    corners = receipt.get('timing', {}).get(phase, {}).get('corners', {})
    periods = {c.get('clock', {}).get('period_ns') for c in corners.values()}
    if not corners or len(periods) != 1:
        raise ValueError('Missing or inconsistent audited clock periods')
    period = next(iter(periods))
    if isinstance(period, bool) or not isinstance(period, (int, float)) or not math.isfinite(period) or period <= 0:
        raise ValueError('Invalid audited clock period')
    global_rows, selected, reports = [], {}, []
    with tarfile.open(archive_path) as archive:
        for member in archive:
            if member.isfile() and re.fullmatch(r'audit/timing/'+phase+r'-\d+-setup-paths.rpt', member.name):
                rows = parse(archive.extractfile(member).read().decode())
                reports.append(dict(name=member.name, observations=len(rows)))
                global_rows.extend(rows)
            elif phase == 'baseline' and member.isfile() and re.fullmatch(r'audit/path-classes/\d+-[a-z_]+.rpt', member.name):
                key=Path(member.name).stem.split('-',1)[1]
                selected.setdefault(key,[]).extend(parse(archive.extractfile(member).read().decode()))
    if not reports:
        raise ValueError('No matching setup reports; missing evidence is not a pass')
    if len({r['name'] for r in reports}) != len(reports):
        raise ValueError('Duplicate setup report in archive')
    observed_corners = set(r['corner'] for r in global_rows)
    if not observed_corners.issubset(corners):
        raise ValueError('Report delay models do not match audit receipt')
    top = sorted(global_rows,key=lambda r:(r['slack_ns'],r['corner'],r['rank']))[:1000]
    groups=defaultdict(list)
    for row in global_rows: groups[architecture(row)].append(row)
    classes = {k:summary(v) for k,v in sorted(groups.items(),key=lambda p:min(r['slack_ns'] for r in p[1]))}
    result = dict(scope='Finite retained setup observations; overlapping hierarchy selectors, not exhaustive graph or clock promotion',
                design_scope=receipt.get('scope', 'unknown'), timing_phase=phase, period_ns=period,
                coverage=dict(reports=reports, expected_corner_count=len(corners), observed_corners=sorted(observed_corners),
                              observations=len(global_rows), complete_nonempty_corner_coverage=observed_corners == set(corners)),
                source_receipt=str(receipt_path), archive_sha256=digest,
                original_tree_sha256=receipt['original_tree_sha256'], qdb_inventory_sha256=receipt['qdb_inventory_sha256'],
                global_top1000=dict(Counter(architecture(row) for row in top)),
                global_classes=classes, top5_classes=[dict(architectural_class=k, **v) for k,v in list(classes.items())[:5]],
                targeted_hierarchies={k:summary(v) for k,v in selected.items()})
    if len(global_rows) == 4000:
        result['global4000_classes'] = classes  # Existing r75 consumers only.
    result['top5_table']=compact_table(result)
    return result


def analyze_verified_fit(receipt_path,evidence):
    """Called after standing queue's source/resource/journal terminal verification.

    Standard STA retains global worst ten across corners, not 1000 per corner.
    Never report that limited sample as exhaustive all-corner path coverage.
    """
    receipt=json.loads(receipt_path.read_text())
    if receipt.get('schema')!='plain-fit-terminal-collection-v1' or not receipt.get('terminal_proven') or receipt.get('findings')!=[]:
        raise ValueError('Requires verified native fit terminal, not arbitrary reports')
    manifest=json.loads((evidence/'project/manifest.json').read_text())
    report=evidence/'project/output_files/probe.sta.rpt'
    if not report.exists():
        return dict(status='missing_sta_report',design_scope=receipt['scope'],period_ns=manifest['clock_period_ns'],top5_classes=[],source_receipt=str(receipt_path))
    text=report.read_text()
    count=re.search(r'Report Timing: Found (\d+) setup paths',text)
    if not count:raise ValueError('Missing native fit setup-path count')
    block=text.split(count[0],1)[1].split('Report Timing: Found',1)[0]
    rows=[]
    for part in re.split(r'(?m)^Path #',block)[1:]:
        if not re.match(r'\d+: Setup slack',part):continue
        corner=re.search(r'; Worst-Case Operating Conditions\s*;\s*([^;]+)',part)
        if not corner:raise ValueError('Missing worst-case corner on native fit path')
        rows.extend(parse('Delay Model:\n'+corner[1].strip()+'\nReport Timing: Found 1 setup paths\nPath #'+part))
    if len(rows)!=int(count[1]):raise ValueError('Truncated fit setup paths')
    groups=defaultdict(list)
    for row in rows:groups[architecture(row)].append(row)
    ordered=sorted(groups.items(),key=lambda p:min(r['slack_ns'] for r in p[1]))
    result=dict(status='finite_retained_fit_paths',design_scope=receipt['scope'],period_ns=manifest['clock_period_ns'],
                coverage=dict(observations=len(rows),sample='native worst setup paths across corners',exhaustive=False),
                top5_classes=[dict(architectural_class=k,**summary(v)) for k,v in ordered[:5]],source_receipt=str(receipt_path),
                source_request_sha256=receipt['source_request_sha256'],archive_sha256=receipt['archive']['sha256'],
                manifest_sha256=hashlib.sha256((evidence/'project/manifest.json').read_bytes()).hexdigest(),report_sha256=hashlib.sha256(report.read_bytes()).hexdigest())
    result['top5_table']=compact_table(result)
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipt',type=Path); parser.add_argument('archive',type=Path)
    parser.add_argument('--phase', choices=('baseline', 'selected'), default='baseline')
    args=parser.parse_args()
    print(json.dumps(analyze(args.receipt,args.archive,args.phase),indent=2,allow_nan=False))
