"""Read-only, physical-only association/replay; never invokes vendor tools.

Reviewer authored unchanged RTL/native ancestors, not primary physical controls,
snapshot constructors or the generic operator/audit runner. Functional semantics,
arithmetical references, owner/fault correctness and numerical gates are excluded.
"""
import argparse
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tarfile

ROOT=Path(__file__).resolve().parents[1]
AUDITOR=ROOT/'tools/audit_plain_fit_timing_noexceptions_v1.py'
AUDITOR_PIN='549041beeeb991f22d04a985bf040ed82393d48c737ce76d5eed90b3a11102b4'


def need(value,why):
    if not value:raise ValueError(why)


def sha(raw):return hashlib.sha256(raw).hexdigest()
def pin(path):return sha(Path(path).read_bytes())
def read(path):return json.loads(Path(path).read_text())


def reader():
    need(pin(AUDITOR)==AUDITOR_PIN,'auditor parser identity')
    spec=importlib.util.spec_from_file_location('physical_only_raw_parser',AUDITOR)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def archive_files(path,expected,accept):
    path=Path(path);need(pin(path)==expected,'actual archive pin')
    result={};seen=set()
    with tarfile.open(path,'r:gz') as t:
        for m in t:
            need(m.name not in seen,'duplicate archive member');seen.add(m.name)
            need(not m.name.startswith('/') and '..' not in Path(m.name).parts,'unsafe archive name')
            if m.isfile() and accept(m.name):
                need(m.size<100*1024*1024,'bounded individual report')
                result[m.name]=t.extractfile(m).read()
    return result


def controls(project):
    project=Path(project);m=read(project/'manifest.json');q=(project/'probe.qsf').read_text()
    need(m['device']=='10AX115N4F40E3SG' and len(m['source_sha256'])==58,'exact part/source58')
    for n,h in m['source_sha256'].items():need(pin(project/'rtl'/n)==h,'literal physical source '+n)
    for n,h in m['control_sha256'].items():
        raw=(project/n).read_bytes()
        suffix=b'set_global_assignment -name LAST_QUARTUS_VERSION "26.1.0 Pro Edition"\n'
        need(sha(raw)==h or (n=='probe.qsf' and raw.endswith(suffix) and sha(raw[:-len(suffix)])==h),'control identity '+n)
    p={k:int(v) for k,v in re.findall(r'^set_parameter -name (\w+) (\d+)$',q,re.M)}
    need(p==m['core_parameters'],'actual compiled parameter closure')
    need({k:p[k] for k in ('AW','P','CONTEXTS','EPOCH_SEED0','EPOCH_SEED1')}==dict(AW=16,P=16,CONTEXTS=2,EPOCH_SEED0=65534,EPOCH_SEED1=42),'full geometry and explicit epoch seeds')
    names=re.findall(r'^set_global_assignment -name SYSTEMVERILOG_FILE rtl/(\S+)$',q,re.M)
    need(len(names)==len(set(names))==58 and set(names)==set(m['source_sha256']),'actual QSF source closure')
    need(re.findall(r'^set_global_assignment -name TOP_LEVEL_ENTITY (\w+)$',q,re.M)==[m['top']],'actual top')
    need(re.findall(r'^set_global_assignment -name SEED (\d+)$',q,re.M)==[str(m['seed'])],'actual seed')
    need(not re.search(r'PLACE_REGION|ROUTE_REGION|PARTITION|PRESERVE|FALSE_PATH|MULTICYCLE',q),'no unused optional floorplan/partition/exception')
    reader().source_sdc((project/'probe.sdc').read_text(),str(m['clock_period_ns']))
    virtual=re.findall(r'^set_instance_assignment -name VIRTUAL_PIN ON -to \{([^}]+)\}$',q,re.M)
    need(virtual and all(x not in ('clk','rst_n') for x in virtual),'virtual host I/O, real clk/reset only')
    header=(project/'rtl'/(m['top']+'.sv')).read_text().split(');',1)[0]
    header=header[header.index('input logic'):]
    groups=re.findall(r'\b(?:input|output)\s+logic\s+(?:signed\s+)?(?:\[[^\]]+\]\s*)?([\w,\s]*?)(?=\b(?:input|output)\s+logic\b|$)',header)
    ports={n.strip() for g in groups for n in g.split(',') if n.strip()}
    need(ports=={n.removesuffix('[*]') for n in virtual}|{'clk','rst_n'},'exact all host ports virtual and no other physical data I/O')
    return dict(top=m['top'],device=m['device'],seed=m['seed'],baseline_period_ns=m['clock_period_ns'],
        manifest_sha256=pin(project/'manifest.json'),source_sha256=m['source_sha256'],
        actual_control_sha256={n:pin(project/n) for n in m['control_sha256']},parameters=p,virtual_pin_assignments=virtual)


def report_resources(text):
    def value(pattern):
        found=re.findall(r'^;\s*'+pattern+r'\s*;\s*([\d,]+)',text,re.M)
        need(len(found)==1,'unique fitted resource '+pattern)
        return int(found[0].replace(',',''))
    return dict(stage='Fitter Finalize, not synthesis or additive hierarchy estimates',
        ALMs_needed=value(r'ALMs needed \[=A-B\+C\]'),ALMs_placed=value(r'\[A\] ALMs used in final placement \[=a\+b\+c\+d\]'),
        LABs_used=value(r'Total LABs:  partially or completely used'),MLABs=value(r'-- Memory LABs \(up to half of total LABs\)'),
        registers=value(r'Dedicated logic registers'),M20Ks=value(r'M20K blocks'),
        physical_DSPs=value(r'Total number of DSP blocks'),DSPs_needed=value(r'DSP Blocks Needed \[=A\+B\+C-D\]'),
        DSPs_dense_merge_estimate=value(r'\[D\] Estimate of DSP Blocks recoverable by dense merging'),
        virtual_pins=value(r'Virtual pins'))


def audit_replay(directory,fit_directory):
    d=Path(directory);r=read(d/'receipt.json');f=Path(fit_directory);fr=read(f/'receipt.json')
    need(r['terminal_proven'] and r['collection_completed'] and r['original_unchanged'] and r['compiled_input_unchanged'] and r['fit_commands']==0,'collected same-layout no-refit audit')
    need(r['original_invocation']==fr['invocation_id'],'actual original fit invocation')
    wanted=lambda n:n in ('tools/spec.json','audit/context.json','audit/receipt.json','audit/audit.log','adapter/context.json','adapter/result.json') or (n.startswith('audit/timing/') and n.endswith(('-summary.rpt','-clocks.rpt','-effective.sdc','-setup-paths.rpt','-exceptions.rpt','-ignored.rpt')))
    raw=archive_files(d/'native-audit.tar.gz',r['archive']['sha256'],wanted)
    spec=json.loads(raw['tools/spec.json']);ctx=json.loads(raw['audit/context.json']);adapter=json.loads(raw['adapter/context.json'])
    need(sha(raw['tools/spec.json'])==r['spec_sha256']==ctx['spec_sha256'],'audit spec identity')
    need(sha(raw['audit/receipt.json'])==r['audit_receipt_sha256'],'native audit receipt pin')
    need(ctx['helper_sha256']==AUDITOR_PIN and ctx['tool_sha256']==spec['tool_sha256'],'actual parser/tool identities')
    need(all(r[k]==ctx[k]==adapter[k] for k in ('original_tree_sha256','qdb_inventory_sha256')),'QDB/tree association')
    need(adapter['original_request_sha256']==fr['source_request_sha256'],'original source request association')
    project=f/'evidence/project';physical=controls(project)
    need(all(ctx['source_pins']['rtl/'+n]==h for n,h in physical['source_sha256'].items()),'audit original full source58 join')
    need(all(ctx['source_pins'][n]==h for n,h in physical['actual_control_sha256'].items()),'audit actual controls join')
    need('26.1.0 Build 110' in adapter['version'],'installed native tool version')
    parser=reader();out={}
    for phase,record in r['timing'].items():
        need(len(record['corners'])==4 and set(record['corners'])==parser.CORNERS,'actual four-corner scope')
        entries=re.findall(r'^'+re.escape(parser.MARK)+r'\tBEGIN\t'+phase+r'\t([0-3])\t([^\t\n]+)\t([01])$',raw['audit/audit.log'].decode(),re.M)
        need(len(entries)==4 and {x[1] for x in entries}==parser.CORNERS,'raw ordered native corner markers')
        mapping={corner:(i,hold) for i,corner,hold in entries}
        replays={}
        for corner,row in record['corners'].items():
            # Native report indices are bound by actual log markers, not JSON order.
            i,hold=mapping[corner];need((hold=='1')==row['tool_declared_hold_only'],'actual corner analysis eligibility')
            prefix='audit/timing/'+phase+'-'+i+'-'
            get=lambda name:raw[prefix+name].decode()
            replay={kind:parser.summary(get(kind+'-summary.rpt'),kind,row['tool_declared_hold_only']) for kind in parser.TYPES}
            need(all(replay[k]==row[k] for k in parser.TYPES),'raw summary replay '+corner)
            need(parser.clock_report(get('clocks.rpt'),str(record['period_ns']))==row['clock'],'raw clock association')
            parser.effective_sdc(get('effective.sdc'),str(record['period_ns']))
            need('No constraints were ignored.' in get('ignored.rpt'),'native ignored-constraint report')
            need(all('No exceptions were found.' in get(k+'-exceptions.rpt') for k in parser.TYPES[:-1]),'native no-exception reports')
            need(parser.unconstrained(get('ucp-summary.rpt'))==row['unconstrained'],'raw I/O/unconstrained coverage')
            paths=parser.paths(get('setup-paths.rpt'),corner,str(record['period_ns']),spec['path_limit'])
            need(abs(paths[0]['slack_ns']-row['setup']['slack_ns'])<=.0011,'worst raw path/summary')
            replays[corner]=dict(**replay,unconstrained=row['unconstrained'],no_ignored_constraints=True,no_reported_exceptions=True,worst_setup_path=paths[0],observed_paths=len(paths))
        out[phase]=dict(period_ns=record['period_ns'],closes=record['timing_closes'],corners=replays,
            minimum_slack_ns={k:min(x[k]['slack_ns'] for x in replays.values() if x[k]['status']=='measured') for k in ('setup','hold','mpw')})
    need(all(out[p]['closes']==all(x[k].get('closes',True) for x in out[p]['corners'].values() for k in parser.TYPES) for p in out),'raw timing closure outcome')
    return dict(receipt_sha256=pin(d/'receipt.json'),archive_sha256=r['archive']['sha256'],
        original_invocation=r['original_invocation'],original_tree_sha256=r['original_tree_sha256'],qdb_inventory_sha256=r['qdb_inventory_sha256'],
        tool_sha256=ctx['tool_sha256'],spec_sha256=r['spec_sha256'],phases=out)


def layout(project,fit,selected,adjacent):
    p=Path(project);f=Path(fit);prepared=controls(p);actual=controls(f/'evidence/project');receipt=read(f/'receipt.json')
    raw_fit=archive_files(f/'native-reports.tar.gz',receipt['archive']['sha256'],
        lambda n:n in ('project/manifest.json','project/probe.qsf','project/probe.sdc','project/output_files/probe.fit.rpt',
                      'project/execution-context.json','project/execution-result.json','project/plain-final-source-guard.json'))
    need(all(pin(f/'evidence'/n)==sha(raw) for n,raw in raw_fit.items()),'raw fit archive/local source-controls-report association')
    execution=json.loads(raw_fit['project/execution-result.json']);context=json.loads(raw_fit['project/execution-context.json'])
    guard=json.loads(raw_fit['project/plain-final-source-guard.json'])
    need(execution['quartus_returncode']==execution['summarize_returncode']==0 and execution['context_sha256']==sha(raw_fit['project/execution-context.json']),'original successful fit/context result')
    need(guard['unchanged'] and not guard['drift'] and guard['vendor_returncode']==0,'actual source guard')
    need(context['source_sha256']==actual['source_sha256'] and context['manifest_sha256']==sha(raw_fit['project/manifest.json']),'executed source/manifest context')
    need(prepared['source_sha256']==actual['source_sha256'] and prepared['parameters']==actual['parameters'],'literal prepared->executed source/params')
    native_qsf=(f/'evidence/project/probe.qsf').read_text()
    native_qsf=re.sub(r'^set_global_assignment -name NUM_PARALLEL_PROCESSORS \d+$',
        'set_global_assignment -name NUM_PARALLEL_PROCESSORS '+str(read(p/'manifest.json')['compile_processors']),native_qsf,flags=re.M)
    native_qsf=re.sub(r'^set_global_assignment -name SEED \d+$','set_global_assignment -name SEED '+str(prepared['seed']),native_qsf,flags=re.M)
    native_qsf=native_qsf.replace('set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS on\n','set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON\n')
    suffix='set_global_assignment -name LAST_QUARTUS_VERSION "26.1.0 Pro Edition"\n'
    if native_qsf.endswith(suffix):native_qsf=native_qsf[:-len(suffix)]
    need(native_qsf==(p/'probe.qsf').read_text(),'only exact worker/seed/snapshot-case/vendor-version QSF delta')
    need((f/'evidence/project/probe.sdc').read_bytes()==(p/'probe.sdc').read_bytes(),'unchanged source SDC')
    need(receipt['terminal_proven'] and receipt['native_job_succeeded'] and not receipt['findings'],'successful source-bound whole fit')
    a=audit_replay(selected,f);b=audit_replay(adjacent,f)
    for k in ('original_invocation','original_tree_sha256','qdb_inventory_sha256','tool_sha256'):need(a[k]==b[k],'same-layout adjacent bracket '+k)
    need(a['phases']['selected']['closes'] and not b['phases']['selected']['closes'],'selected PASS/adjacent FAIL actual')
    span=Decimal(str(a['phases']['selected']['period_ns']))-Decimal(str(b['phases']['selected']['period_ns']))
    need(span>0,'selected PASS versus narrower operator-designated tested FAIL')
    resources=report_resources((f/'evidence/project/output_files/probe.fit.rpt').read_text())
    return dict(status='PHYSICAL_ONLY_PASS',prepared=prepared,actual=actual,fit_receipt_sha256=pin(f/'receipt.json'),
        fit_archive_sha256=receipt['archive']['sha256'],fit_report_sha256=sha(raw_fit['project/output_files/probe.fit.rpt']),resources=resources,selected=a,adjacent=b,
        adjacent_tested_span_ns=str(span),bracket_scope='Operator-designated tested points only, not exhaustive period search or global maximum',
        exclusions=['All RTL/arithmetic/native semantics including reviewer-authored unchanged ancestors','Board I/O/host transfer/reset release','Exhaustive graph/global maximum clock','Production/advisor adoption'])


def cycle_association(result,index_path):
    """Identity/projection association only; does not replay numerical semantics."""
    index=read(index_path);p=index['production'];bundle=read(p['bundle']['path'])
    need(pin(p['bundle']['path'])==p['bundle']['sha256'],'own numerical production bundle pin')
    need(bundle['generated_sha256']==result['actual']['source_sha256']==p['all58_generated_sha256'],'own numerical/physical literal58 map')
    need(p['parameters']==result['actual']['parameters'],'own numerical/physical compiled epoch/flag parameters')
    ref=index['own_healthy_source_native_ledger'];need(pin(ref['path'])==ref['sha256'],'own source-native healthy ledger pin')
    ledger=read(ref['path']);need(ledger['production']['all58_generated_sha256']==result['actual']['source_sha256'] and ledger['production']['top']==result['actual']['top'],'own ledger/source association')
    sample=ledger['sample'];cycles=sample['pair_completion_cycles'];need(type(cycles) is int and cycles>0,'declared sample pair cycles')
    seconds=Decimal(cycles)*Decimal(str(result['selected']['phases']['selected']['period_ns']))/Decimal(10**9)
    return dict(scope='Source/parameter identity association and exact period multiplication only; numerical/source semantics reviewed separately',
        own_numerical_index=dict(path=str(index_path),sha256=pin(index_path),status=index['status']),
        own_ledger=ref,sample_cycles=cycles,sample_scope=sample,
        pair_seconds=str(seconds),amortized_seconds=str(seconds/2),
        limitations='Healthy internal-compute conditional model projection, not measured full sample/full PRP/board/individual latency. Existing source_ready/conditional/proof labels preserved; no independent functional/numerical verdict.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',required=True);p.add_argument('--fit',required=True);p.add_argument('--selected',required=True);p.add_argument('--adjacent',required=True);p.add_argument('--numerical-index')
    a=p.parse_args();result=layout(a.project,a.fit,a.selected,a.adjacent)
    if a.numerical_index:result['cycle_association']=cycle_association(result,a.numerical_index)
    print(json.dumps(result,indent=2))
