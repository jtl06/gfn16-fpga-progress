"""Read-only FIELD100 settings-layout physical review; no vendor invocation.

Source-identical numerical/source semantics are excluded. The optional adjacent
argument is required for a tested period bracket, not for an own 12ns-only audit.
"""
import argparse
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import re

BASE=Path(__file__).with_name('stream27_field100_r13_physical_review.py')
BASE_PIN='eccd4640ed51b1cc456d168181d60680119d074c96f839b4963764bd42b4b64b'


def base():
    if hashlib.sha256(BASE.read_bytes()).hexdigest()!=BASE_PIN:
        raise ValueError('immutable prior physical-only parser identity')
    spec=importlib.util.spec_from_file_location('field100_physical_raw_base',BASE)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def review(project,fit,selected,index,adjacent=None):
    v=base()
    if adjacent:
        result=review(project,fit,selected,index)
        a=result['selected'];b=v.audit_replay(adjacent,fit)
        for k in ('original_invocation','original_tree_sha256','qdb_inventory_sha256','tool_sha256'):
            v.need(a[k]==b[k],'same own layout bracket '+k)
        phase='selected' if 'selected' in b['phases'] else 'baseline'
        v.need(a['phases']['selected']['closes'] and not b['phases'][phase]['closes'],'actual selected PASS/narrower FAIL')
        span=Decimal(str(a['phases']['selected']['period_ns']))-Decimal(str(b['phases'][phase]['period_ns']))
        v.need(span>0,'narrower operator-designated tested FAIL')
        result.update(status='PHYSICAL_ONLY_PASS',adjacent=b,adjacent_phase=phase,adjacent_tested_span_ns=str(span),
            bracket_scope='Operator-designated tested points only; not exhaustive search/global maximum')
    else:
        # Same original fit/source/control checks as the pinned bracket replayer,
        # without manufacturing an adjacent point or a maximum-clock verdict.
        p=Path(project);f=Path(fit);prepared=v.controls(p);actual=v.controls(f/'evidence/project')
        receipt=v.read(f/'receipt.json')
        wanted={'project/manifest.json','project/probe.qsf','project/probe.sdc',
            'project/output_files/probe.fit.rpt','project/execution-context.json',
            'project/execution-result.json','project/plain-final-source-guard.json'}
        raw=v.archive_files(f/'native-reports.tar.gz',receipt['archive']['sha256'],lambda n:n in wanted)
        v.need(set(raw)==wanted,'complete original fit archive association')
        v.need(all(v.pin(f/'evidence'/n)==v.sha(data) for n,data in raw.items()),'raw fit/local identity')
        context=json.loads(raw['project/execution-context.json']);execution=json.loads(raw['project/execution-result.json'])
        guard=json.loads(raw['project/plain-final-source-guard.json'])
        v.need(execution['quartus_returncode']==execution['summarize_returncode']==0 and execution['context_sha256']==v.sha(raw['project/execution-context.json']),'successful original/context')
        v.need(guard['unchanged'] and not guard['drift'] and guard['vendor_returncode']==0,'original source guard')
        v.need(context['source_sha256']==actual['source_sha256'] and context['manifest_sha256']==v.sha(raw['project/manifest.json']),'executed source/context')
        v.need(prepared['source_sha256']==actual['source_sha256'] and prepared['parameters']==actual['parameters'],'prepared/executed literal source and parameters')
        q=(f/'evidence/project/probe.qsf').read_text()
        q=re.sub(r'^set_global_assignment -name NUM_PARALLEL_PROCESSORS \d+$','set_global_assignment -name NUM_PARALLEL_PROCESSORS '+str(v.read(p/'manifest.json')['compile_processors']),q,flags=re.M)
        q=re.sub(r'^set_global_assignment -name SEED \d+$','set_global_assignment -name SEED '+str(prepared['seed']),q,flags=re.M)
        q=q.replace('set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS on\n','set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON\n')
        suffix='set_global_assignment -name LAST_QUARTUS_VERSION "26.1.0 Pro Edition"\n'
        if q.endswith(suffix):q=q[:-len(suffix)]
        prepared_q=(p/'probe.qsf').read_text().replace('set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS on\n','set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON\n')
        if prepared_q.endswith(suffix):prepared_q=prepared_q[:-len(suffix)]
        v.need(q==prepared_q,'only known worker/seed/snapshot-case/vendor suffix QSF delta')
        v.need((f/'evidence/project/probe.sdc').read_bytes()==(p/'probe.sdc').read_bytes(),'unchanged SDC')
        v.need(receipt['terminal_proven'] and receipt['native_job_succeeded'] and not receipt['findings'],'collected successful own fit')
        audit=v.audit_replay(selected,f)
        phase='selected' if 'selected' in audit['phases'] else 'baseline'
        closes=audit['phases'][phase]['closes']
        result=dict(status='PHYSICAL_ONLY_PASS_AT_TESTED_PERIOD' if closes else 'PHYSICAL_ONLY_REVIEWED_TIMING_VIOLATION',prepared=prepared,actual=actual,
            fit_receipt_sha256=v.pin(f/'receipt.json'),fit_archive_sha256=receipt['archive']['sha256'],
            fit_report_sha256=v.sha(raw['project/output_files/probe.fit.rpt']),
            resources=v.report_resources(raw['project/output_files/probe.fit.rpt'].decode()),selected=audit,phase_under_review=phase,
            adjacent=None,bracket_scope='Single own audited tested period only; no tighter bracket/global maximum')
    if result['status'] in ('PHYSICAL_ONLY_PASS','PHYSICAL_ONLY_PASS_AT_TESTED_PERIOD') and 'selected' in result['selected']['phases']:
        result['cycle_association']=v.cycle_association(result,index)
    else:
        # A failing baseline is evidence, not a usable clock. Bind the unchanged
        # numerical source identity without manufacturing throughput seconds.
        own=v.read(index);production=own['production']
        v.need(v.pin(production['bundle']['path'])==production['bundle']['sha256'],'own numerical bundle pin')
        bundle=v.read(production['bundle']['path'])
        v.need(bundle['generated_sha256']==result['actual']['source_sha256']==production['all58_generated_sha256'],'own literal58 source association')
        v.need(production['parameters']==result['actual']['parameters'],'own compiled parameter association')
        result['source_association']=dict(numerical_index=dict(path=str(index),sha256=v.pin(index)),projection_seconds=None,
            scope='Identity only; failing own period is not a qualified clock or throughput projection')
    result['review_scope']='Physical-only source/control/tool/QDB/resources/own audit association. All authored unchanged RTL/native semantics excluded; no board/reset-release/numerical requalification or advisor adoption.'
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',required=True);p.add_argument('--fit',required=True)
    p.add_argument('--selected',required=True);p.add_argument('--adjacent');p.add_argument('--numerical-index',required=True)
    a=p.parse_args();print(json.dumps(review(a.project,a.fit,a.selected,a.numerical_index,a.adjacent),indent=2))
