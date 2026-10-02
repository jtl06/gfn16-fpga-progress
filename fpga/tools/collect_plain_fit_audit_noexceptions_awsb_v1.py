"""Finite read-only collection of a completed plain-fit timing audit.

No native Quartus, refit, lifecycle, original writes, or raw QDB transfer.
Original manager journal fields, not transient-unit inactivity, prove terminal.
"""
from contextlib import ExitStack
from datetime import datetime, timezone
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile

ADAPTER_SHA='dc2bf465823e04ad54d122d894b992944c8d8bc13687bfb9ff7e59f48ead0bd1'
COLLECTOR_SHA='51aec17246c64a289917517f690c77f0497fb2dd004e214c1a5889fe15f70dd3'


def need(ok, reason):
    if not ok: raise ValueError(reason)


def load(name, path, pin):
    need(hashlib.sha256(path.read_bytes()).hexdigest()==pin,'pinned reused helper')
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def time_bound(value, proof):
    stamp=datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()*1e6
    need(int(proof['manager_start_realtime_us'])-1000000<=stamp<=int(proof['manager_end_realtime_us'])+1000000,
         'native audit timestamp outside original invocation')


def collect(args):
    need(sys.platform=='linux' and os.geteuid()!=0,'nonroot existing Linux worker')
    tools=args.request.parent
    ad=load('_audit_collection_adapter',tools/'plain_fit_audit_noexceptions_v1.py',ADAPTER_SHA)
    root=Path(ad.HOSTS[ad.AWS]['root'])
    need(tools.parent==root and args.output.parent==root and args.output.resolve()==args.output and not args.output.exists(),
         'fresh sibling collection outside original/private snapshot')
    need(re.fullmatch('[0-9a-f]{32}',args.invocation),'exact native invocation')
    request=json.loads(ad.regular(args.request,args.request_sha256))
    need(request['host']==ad.AWS and request['slot']=='b','delegated AWSB audit collection only')
    # Launch validation deliberately requires a nonexistent output. A completed
    # collector must instead replay its immutable source/results, not bypass
    # that frozen launch guard or validate freshness against a spent budget.
    need(set(request)==ad.KEYS and request['schema']=='plain-fit-audit-request-v1','closed completed request')
    spec=ad.read(request['audit_spec']); h=ad.helper(tools)
    need(set(spec)==h.SPEC_KEYS and spec['helper_sha256']==ad.AUDIT_SHA and spec['tcl_sha256']==ad.TCL_SHA and
         Path(request['audit_spec']['path']).parent==tools and Path(spec['tcl'])==tools/ad.TCL,'completed spec/helper/Tcl identity')
    for relative,pin in request['runtime_sha256'].items(): ad.regular(tools/relative,pin)
    original,terminal=ad.source_checks(request,spec,h)
    project=Path(spec['project']); audit=Path(spec['output']); unit=request['unit']
    collector=load('_audit_original_terminal_collector',root/'tools-collect-plain-v1.py',COLLECTOR_SHA)
    physical=ad.topology(ad.AWS,'b')
    with ExitStack() as locks:
        for filename,mode in ad.lock_names(ad.AWS,'b',physical):
            fd=os.open(root/filename,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600); locks.callback(os.close,fd)
            need(os.fstat(fd).st_nlink==1,'canonical collection lock')
            fcntl.flock(fd,mode|fcntl.LOCK_NB)
        current=collector.state(unit); collector.quiescent(current,args.invocation)
        raw=subprocess.check_output(['journalctl','-u',unit,'--no-pager','-o','json'],text=True,timeout=30)
        need(len(raw.encode())<=32<<20,'finite native journal')
        proof,exact=collector.journal_proof([json.loads(row) for row in raw.splitlines()],unit,args.invocation)
        need(proof['manager_elapsed_seconds']<=2280 and proof['terminal_kind']=='deactivated_successfully','admitted audit terminal interval')
        context_path=root/(audit.name+'-adapter-context.json')
        result_path=root/(audit.name+'-adapter-result.json')
        context=json.loads(ad.regular(context_path)); result=json.loads(ad.regular(result_path))
        receipt=json.loads(ad.regular(audit/'receipt.json'))
        need(context['unit']==unit and context['slot']=='b' and context['request_sha256']==args.request_sha256 and
             context['audit_spec_sha256']==request['audit_spec']['sha256'] and context['original_invocation']==terminal['invocation_id'],
             'source-bound native adapter context')
        need(result['context_sha256']==ad.sha(context_path) and result['request_sha256']==args.request_sha256 and
             result['audit_receipt_sha256']==ad.sha(audit/'receipt.json') and result['final_errors']==[] and
             result['native_execution_complete'] is True and result['returncode'] in (0,2), 'complete adapter result')
        need(result['status']==receipt['status'] and result['timing_closes']==receipt['timing_closes'] and
             receipt['original_before']==request['original_tree'] and receipt['original_after']==request['original_tree'] and
             receipt['original_unchanged'] is True and receipt['compiled_input_unchanged'] is True and
             receipt['final_verification_errors']==[] and receipt['fit_commands']==0 and receipt['promotion_allowed'] is False and
             receipt['spec_sha256']==request['audit_spec']['sha256'] and receipt['tool_sha256']==spec['tool_sha256'] and
             receipt['helper_sha256']==ad.AUDIT_SHA and receipt['tcl_sha256']==ad.TCL_SHA,'strict helper/source/compiled-input result')
        for value in (context['started_at'],result['finished_at'],receipt['finished_at']): time_bound(value,proof)
        for tool,pin in spec['tool_sha256'].items(): ad.regular(tool,pin)
        checked={}; h.check_copy(checked,project,audit/'snapshot',request['original_tree'])
        need(checked['snapshot_after']==receipt['snapshot_after'],'private copy after terminal drift')
        _,baseline=h.verify_project(project,spec)
        parsed=h.parse_results(audit/'timing',(audit/'audit.log').read_text(),spec,baseline)
        need(parsed==receipt['timing'],'actual retained reports replay equals native receipt')
        files={}
        def add(name,path):
            need(name not in files and '/qdb/' not in name and '/snapshot/' not in name,'closed unique non-QDB archive selection')
            h.pin(path); files[name]=path
        for path in sorted(tools.rglob('*')):
            need(not path.is_symlink(),'no linked tooling evidence')
            if path.is_file(): add('tools/'+str(path.relative_to(tools)),path)
        for path in sorted(audit.rglob('*')):
            if path.is_relative_to(audit/'snapshot'): continue
            need(not path.is_symlink(),'no linked native reports')
            if path.is_file(): add('audit/'+str(path.relative_to(audit)),path)
        for name in spec['pins']: add('original/'+name,project/name)
        add('original/original-request.json',Path(request['original_request']['path']))
        add('original/terminal-receipt.json',Path(spec['terminal_receipt']))
        add('adapter/context.json',context_path); add('adapter/result.json',result_path)
        before={name:h.pin(path) for name,path in files.items()}
        need(len(before)<=10000 and sum(row['size'] for row in before.values())<=512<<20,'finite native audit archive')
        args.output.mkdir()
        ad.save(args.output/'native-journal-proof.json',proof)
        ad.save(args.output/'unit-state-before.json',current)
        with (args.output/'native-journal.jsonl').open('x') as stream:
            for row in exact: stream.write(json.dumps(row,sort_keys=True)+'\n')
        final=collector.state(unit); collector.quiescent(final,args.invocation)
        ad.save(args.output/'unit-state-after.json',final)
        need(h.inventory(project)==request['original_tree'],'original full-tree/QDB collection drift')
        for path in sorted(args.output.iterdir()): add('collection/'+path.name,path)
        inventory={name:h.pin(path) for name,path in sorted(files.items())}
        ad.save(args.output/'inventory.json',dict(schema='plain-fit-audit-collection-inventory-v1',files=inventory,
            count=len(inventory),bytes=sum(row['size'] for row in inventory.values()),raw_qdb_included=False))
        add('collection/inventory.json',args.output/'inventory.json')
        archive=args.output/'native-audit.tar.gz'
        with tarfile.open(archive,'w:gz',compresslevel=1) as tar:
            for name,path in sorted(files.items()): tar.add(path,arcname=name,recursive=False)
        need({name:h.pin(files[name]) for name in before}==before,'native reports changed during collection')
        outcome=dict(schema='plain-fit-audit-terminal-collection-v1',collection_completed=True,terminal_proven=True,
            unit=unit,invocation_id=args.invocation,scope=spec['scope'],project=str(project),original_invocation=terminal['invocation_id'],
            request_sha256=args.request_sha256,spec_sha256=request['audit_spec']['sha256'],collector_sha256=h.sha(Path(__file__).resolve()),
            native_journal_proof=proof,adapter_result_sha256=h.sha(result_path),audit_receipt_sha256=h.sha(audit/'receipt.json'),
            original_tree_sha256=spec['original_tree_sha256'],qdb_inventory_sha256=spec['qdb_inventory_sha256'],
            original_unchanged=True,compiled_input_unchanged=True,status=receipt['status'],timing_closes=receipt['timing_closes'],
            timing=parsed,archive=dict(path=str(archive),**h.pin(archive)),inventory_sha256=h.sha(args.output/'inventory.json'),
            observed_at_utc=ad.now().isoformat(),promotion_allowed=False,fit_commands=0,
            supplementary_checks=dict(latches='unsupported_native_check_timing_selector; retained warnings332051/332052; not PASS'),
            limitation='Internal compute scoped MCMM timing only, finite setup observations; no board I/O/reset-release/exhaustive graph or clock promotion.')
        ad.save(args.output/'terminal-collection.json',outcome)
        print(json.dumps(dict(receipt=str(args.output/'terminal-collection.json'),receipt_pin=h.pin(args.output/'terminal-collection.json'),
            archive=outcome['archive'],manager_elapsed_seconds=proof['manager_elapsed_seconds'],status=outcome['status']),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request',type=Path,required=True); parser.add_argument('--request-sha256',required=True)
    parser.add_argument('--invocation',required=True); parser.add_argument('--output',type=Path,required=True)
    collect(parser.parse_args())

