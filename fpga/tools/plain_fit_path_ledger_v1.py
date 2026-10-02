"""Pure report-only r54 ledger for the finite paths of a collected plain fit.

No native tool or host action. Native route/cell/uTco statistics and full data
cone elements are retained, not inferred from endpoints or source intentions.
Coarse family labels aid triage; they are not register-cut/graph coverage.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re


def need(ok,why):
    if not ok: raise ValueError(why)


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(text):
    return [[value.strip() for value in line.strip().strip(';').split(';')]
            for line in text.splitlines() if line.lstrip().startswith(';')]


def table(text,title,header):
    match = list(re.finditer(r'^; '+re.escape(title)+r'\s*;\s*$',text,re.M))
    need(len(match) == 1,'one native table: '+title)
    values = []; begun = False; closed = False
    for line in text[match[0].end():].splitlines():
        value = rows(line)
        if not begun:
            if value: need(value == [header],'native header: '+title); begun = True
            continue
        if value: values.extend(value)
        elif values:
            need(re.fullmatch(r'\+(?:-+\+)+',line.strip()),'closing native table border')
            closed = True; break
    need(begun and values and closed,'full native table closure')
    return values


def family(node):
    if node.startswith('host|image|banks['): return 'host digit-image RAM'
    if node.startswith('host|image|'): return 'host digit-image arithmetic/gating'
    if 'cold_prefill|' in node: return 'cold-prefill admission/legality/fault'
    if node.startswith('host|'): return 'host control/arbitration'
    if 'upper_normalizer|' in node or 'lower_normalizer|' in node: return 'butterfly normalizer'
    if re.search(r'memories\[\d+\]\.data_ram\|',node): return 'NTT data RAM'
    if 'carry_lanes[' in node or 'carry_unit|' in node: return 'carry'
    if 'arithmetic[' in node or 'butterfly|' in node: return 'NTT butterfly'
    if '|row_tag[' in node: return 'NTT row-tag pipeline'
    return 'unclassified:'+re.sub(r'\[\d+\]','[*]',node.split('|')[0])


def parse(text,kind,period):
    sections = re.findall(r'Report Timing: Found \d+ '+kind+r' paths[\s\S]+?(?=Report Timing: Found|\Z)',text)
    need(len(sections) == 1,'one finite native '+kind+' query')
    section = sections[0]
    count,violated = map(int,re.findall(r'Report Timing: Found (\d+) '+kind+r' paths \((\d+) violated\)',section)[0])
    need(0 < count <= 1000 and 0 <= violated <= count,'bounded native path sample')
    need(re.findall(r'^Snapshot:\s*\n\s*(\S+)',section,re.M) == ['final'],'actual final snapshot')
    values = table(section,'Summary of Paths',['Slack','From Node','To Node','Launch Clock','Latch Clock',
        'Relationship','Clock Skew','Data Delay','Worst-Case Operating Conditions'])
    need(len(values) == count,'finite summary/count closure')
    detail = list(re.finditer(r'^Path #(\d+): '+kind.title()+r' slack is (-?[\d.]+)',section,re.M))
    need(len(detail) == count and [int(row[1]) for row in detail] == list(range(1,count+1)),'full ordered detail count')
    result = []
    for rank,(row,marker) in enumerate(zip(values,detail),1):
        need(len(row) == 9 and row[3:5] == ['kernel_clk','kernel_clk'],'native endpoint/clock columns')
        numbers = list(map(float,(row[0],row[5],row[6],row[7])))
        need(all(math.isfinite(value) for value in numbers) and numbers[3] >= 0 and
             numbers[1] == (period if kind == 'setup' else 0) and float(marker[2]) == numbers[0],'native timing/detail relationship')
        body = section[marker.end():detail[rank].start() if rank < count else len(section)]
        properties = dict(table(body,'Path Summary',['Property','Value']))
        need(properties['From Node'] == row[1] and properties['To Node'] == row[2] and
             properties['Worst-Case Operating Conditions'] == row[8],'native endpoint/detail/corner binding')
        stats = table(body,'Statistics',['Property','Value','Count','Total Delay','% of Total','Min','Max'])
        arrival = False; data = False; split = {}
        for entry in stats:
            need(len(entry) == 7,'native statistics row')
            if entry[0] == 'Arrival Path': arrival = True
            elif entry[0] == 'Required Path': arrival = False
            elif arrival and entry[0] == 'Data': data = True
            elif arrival and data and entry[0] in ('IC','Cell','uTco'):
                need(entry[0] not in split,'unique native data-delay statistic')
                split[entry[0]] = dict(count=int(entry[2]),total_delay_ns=float(entry[3]),
                    native_percent=int(entry[4]),minimum_ns=float(entry[5]),maximum_ns=float(entry[6]))
        need('Cell' in split,'native data cell-delay statistic')
        # Zero/interconnect-absent native rows are not manufactured from delay totals.
        split.setdefault('IC',None)
        elements = table(body,'Data Arrival Path',['Total','Incr','RF','Type','Fanout','Location','HS/LP','Element'])
        markers = [index for index,entry in enumerate(elements) if entry[-1] == 'data path']
        need(len(markers) == 1,'native data path boundary')
        cone = []
        for entry in elements[markers[0]+1:]:
            need(len(entry) == 8,'native data-cone columns')
            cone.append(dict(element=entry[7],family=family(entry[7]),type=entry[3],
                incremental_ns=float(entry[1]),arrival_ns=float(entry[0]),location=entry[5],
                fanout=entry[4],routing_class=entry[6]))
        families = list(dict.fromkeys(value['family'] for value in cone))
        required = table(body,'Data Required Path',['Total','Incr','RF','Type','Fanout','Location','HS/LP','Element'])
        required_constraints = [dict(element=entry[-1],type=entry[3],incremental_ns=float(entry[1]),
            total_ns=float(entry[0])) for entry in required if entry[3] in ('uTsu','uTh','uncertainty')]
        logic = [entry[2] for entry in stats if entry[0] == 'Number of Logic Levels']
        need(len(logic) == 1 and re.fullmatch(r'\d+',logic[0]),'native logic-level count')
        result.append(dict(rank=rank,slack_ns=numbers[0],source=row[1],destination=row[2],
            source_family=family(row[1]),destination_family=family(row[2]),relationship_ns=numbers[1],
            clock_skew_ns=numbers[2],data_delay_ns=numbers[3],native_corner=row[8],
            native_sdc_exception=properties['SDC Exception'],native_data_statistics=split,native_logic_levels=int(logic[0]),
            native_required_constraints=required_constraints,
            observed_data_cone_families=families,observed_data_cone=cone))
    need(sum(value['slack_ns'] < 0 for value in result) == violated and
         [value['slack_ns'] for value in result] == sorted(value['slack_ns'] for value in result),'violated count/worst-path ordering')
    counts = {}
    for value in result:
        label = value['source_family']+' -> '+value['destination_family']; counts[label] = counts.get(label,0)+1
    return dict(native_sample_count=count,native_violated_count=violated,endpoint_family_counts=counts,paths=result)


def collect(root,receipt_pin):
    root = root.resolve(); receipt_path = root/'terminal-collection-v1.json'
    need(sha(receipt_path) == receipt_pin,'original-inv terminal collection pin')
    receipt = json.loads(receipt_path.read_text())
    need(receipt['native_job_succeeded'] and receipt['terminal_proven'] and not receipt['findings'],'source-bound completed native fit')
    inventory = root/'collection-inventory-v1.json'
    need(sha(inventory) == receipt['inventory_sha256'] and sha(root/'native-reports.tar.gz') == receipt['archive']['sha256'],'raw downloaded inventory/archive identity')
    files = json.loads(inventory.read_text())['files']
    for name in ('project/manifest.json','project/output_files/probe.sta.rpt'):
        need(sha(root/name) == files[name]['sha256'],'source/report identity')
    manifest = json.loads((root/'project/manifest.json').read_text())
    text = (root/'project/output_files/probe.sta.rpt').read_text()
    return dict(schema='plain-fit-path-ledger-v1',scope=receipt['scope'],top=manifest['top'],
        target_period_ns=manifest['clock_period_ns'],native_collection_receipt_sha256=receipt_pin,
        report_sha256=files['project/output_files/probe.sta.rpt']['sha256'],parser_sha256=sha(Path(__file__).resolve()),
        setup=parse(text,'setup',manifest['clock_period_ns']),hold=parse(text,'hold',manifest['clock_period_ns']),
        generated_at_utc=datetime.now(timezone.utc).isoformat(),promotion_allowed=False,
        exhaustive_graph_coverage=False,registered_stage_count_proof=False,audited_clock=False,
        limitation='Final native finite MCMM worst-path observations only. Printed native route/cell/uTco totals omit negative contributions as noted by the report. Endpoint/cone labels are triage, not proof of missing registers or exhaustive crossings. Virtual I/O and source reset exceptions remain outside sign-off.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path); parser.add_argument('--receipt-sha256',required=True)
    args = parser.parse_args(); result = collect(args.root,args.receipt_sha256)
    with (args.root/'path-ledger-v1.json').open('x') as stream:
        json.dump(result,stream,indent=2,allow_nan=False); stream.write('\n')
    print(json.dumps({kind:result[kind]['endpoint_family_counts'] for kind in ('setup','hold')},indent=2))
