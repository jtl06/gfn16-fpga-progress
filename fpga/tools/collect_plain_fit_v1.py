"""Read-only terminal collection for one r53 plain fit, including failures.

Run on its existing Linux worker. No Quartus, lifecycle, locks, source writes or
raw QDB transfer. Zero exit means original-inv terminal evidence was collected,
not native design/timing/promotion PASS. All retained reports remain scoped.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tarfile

ROOTS = {'gfn16-aws-m8i': Path('/home/ubuntu/gfn16-worker'),
         'gfn16-azure-f16': Path('/home/azureuser/gfn16-worker')}
LIMIT = 512 << 20
SUFFIX = b'set_global_assignment -name LAST_QUARTUS_VERSION "26.1.0 Pro Edition"\n'
REPORT_SUFFIXES = {'.rpt', '.summary', '.log', '.json', '.xml', '.csv', '.txt', '.done'}
PROJECT_EVIDENCE = ['manifest.json', 'probe.qsf', 'probe.qpf', 'probe.sdc', 'run.tcl',
 'execution-context.json', 'execution-result.json', 'plain-admission.json',
 'plain-final-source-guard.json', 'database-inventory-final.json', 'rtl-structural-result.json']


def need(ok, why):
    if not ok: raise ValueError(why)


def pin(path):
    path = Path(path)
    need(path.is_absolute() and path.resolve() == path and path.is_file() and path.stat().st_nlink == 1, 'regular canonical evidence: '+str(path))
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 << 20), b''): h.update(block)
    return dict(sha256=h.hexdigest(), size=path.stat().st_size)


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False); stream.write('\n')


def state(unit):
    keys = ['LoadState', 'ActiveState', 'SubState', 'MainPID', 'InvocationID', 'ExecMainStatus', 'Result', 'MemoryPeak']
    command = ['systemctl', 'show', unit]
    for key in keys: command += ['-p', key]
    raw = subprocess.check_output(command, text=True, timeout=15)
    return dict(line.split('=',1) for line in raw.splitlines())


def quiescent(current, invocation):
    need(current.get('MainPID') == '0' and current.get('ActiveState') in ('inactive','failed')
        and current.get('SubState') in ('dead','failed','exited'), 'unit not terminal; no collection/release from observation timeout')
    need(current.get('InvocationID','') in ('', invocation), 'current unit is another invocation')


def journal_proof(rows, unit, invocation):
    """Bind original manager start/end, including transient-unit GC and failure."""
    manager = [row for row in rows if str(row.get('_PID')) == '1' and row.get('UNIT') == unit and row.get('INVOCATION_ID') == invocation]
    exact = [row for row in rows if row in manager or (row.get('_SYSTEMD_UNIT') == unit and row.get('_SYSTEMD_INVOCATION_ID') == invocation)]
    starts = [row for row in manager if row.get('JOB_TYPE') == 'start' and row.get('JOB_RESULT') == 'done']
    success = [row for row in manager if row.get('MESSAGE') == unit+': Deactivated successfully.']
    failure = [row for row in manager if str(row.get('MESSAGE','')).startswith(unit+": Failed with result '")]
    need(len(starts) == 1 and len(success)+len(failure) == 1, 'exact original-inv manager start and terminal event required')
    start, end = starts[0], (success+failure)[0]
    duration = (int(end['__MONOTONIC_TIMESTAMP'])-int(start['__MONOTONIC_TIMESTAMP']))/1e6
    need(0 <= duration <= 21780, 'native manager interval outside admitted plain-fit bound')
    need(int(end['__REALTIME_TIMESTAMP']) >= int(start['__REALTIME_TIMESTAMP']), 'native manager clock ordering')
    main_exit = [row['MESSAGE'] for row in manager if re.search(r'Main process exited, code=\w+, status=', str(row.get('MESSAGE','')))]
    return dict(unit=unit, invocation_id=invocation, terminal_proven=True,
        terminal_kind='deactivated_successfully' if success else 'failed', manager_elapsed_seconds=duration,
        manager_start_realtime_us=start['__REALTIME_TIMESTAMP'], manager_end_realtime_us=end['__REALTIME_TIMESTAMP'],
        manager_terminal_message=end['MESSAGE'], manager_main_exit_messages=main_exit,
        resource_journal=[row for row in manager if 'CPU_USAGE_NSEC' in row or 'MEMORY_PEAK' in row],
        provenance='Trusted manager _PID=1 UNIT/INVOCATION_ID fields. GC properties are not reconstructed from inactivity.'), exact


def select_files(root, project, request, service_log=None):
    """Closed regular file selection: never recursively collect a QDB tree."""
    files = {'request.json': request}
    for name in PROJECT_EVIDENCE:
        path = project/name
        if path.exists(): files['project/'+name] = path
    for folder in ('rtl','output_files'):
        for path in sorted((project/folder).rglob('*')):
            need(not path.is_symlink(), 'linked source/report refused')
            if path.is_file() and (folder == 'rtl' or path.suffix in REPORT_SUFFIXES):
                files['project/'+str(path.relative_to(project))] = path
    for suffix in ('-fit.log','-summary.json'):
        path = root/(project.name+suffix)
        if path.exists(): files['root/'+path.name] = path
    if service_log:
        need(service_log.is_relative_to(root) and not service_log.is_relative_to(project/'qdb'), 'owned service log path')
        if service_log.exists(): files['service/service.log'] = service_log
    need(all('/qdb/' not in name and '/db/' not in name and '/incremental_db/' not in name for name in files), 'raw compiled DB selection forbidden')
    return files


def assess(project, request, proof):
    findings = []
    def read(name):
        path = project/name
        if not path.is_file(): findings.append('missing_'+name); return None
        return json.loads(path.read_text())
    context, result = read('execution-context.json'), read('execution-result.json')
    guard, database = read('plain-final-source-guard.json'), read('database-inventory-final.json')
    if context:
        expected = request['project']
        if any(context.get(name) != expected[name] for name in ('manifest_sha256','source_sha256','control_sha256','qsf_parameters')):
            findings.append('request_native_source_context_mismatch')
        if result and result.get('context_sha256') != pin(project/'execution-context.json')['sha256']:
            findings.append('native_result_context_sha_mismatch')
        for prefix, mapping in (('rtl/', context['source_sha256']), ('', context['control_sha256'])):
            for name, digest in mapping.items():
                path = project/(prefix+name)
                need(path.resolve() == path and path.is_relative_to(project), 'closed source context path')
                if not path.is_file(): findings.append('missing_source_'+prefix+name); continue
                raw = path.read_bytes(); actual = hashlib.sha256(raw).hexdigest()
                if actual != digest and not (name == 'probe.qsf' and not prefix and raw.endswith(SUFFIX)
                    and hashlib.sha256(raw[:-len(SUFFIX)]).hexdigest() == digest):
                    findings.append('source_drift_'+prefix+name)
        for key in ('started_at',):
            value = datetime.fromisoformat(context[key].replace('Z','+00:00')).timestamp()*1e6
            if not int(proof['manager_start_realtime_us'])-1000000 <= value <= int(proof['manager_end_realtime_us'])+1000000:
                findings.append('native_context_time_outside_invocation')
    if result:
        value = datetime.fromisoformat(result['finished_at'].replace('Z','+00:00')).timestamp()*1e6
        if not int(proof['manager_start_realtime_us'])-1000000 <= value <= int(proof['manager_end_realtime_us'])+1000000:
            findings.append('native_result_time_outside_invocation')
    if guard and (guard.get('unchanged') is not True or guard.get('drift') != []): findings.append('native_final_source_guard_failed')
    if isinstance(database, dict):
        for name, row in database.items():
            relative = Path(name)
            need(not relative.is_absolute() and '..' not in relative.parts and relative.parts[0] == 'qdb'
                and re.fullmatch('[0-9a-f]{64}', row['sha256']) and type(row['size']) is int and row['size'] >= 0, 'native QDB inventory schema')
    elif database is not None: findings.append('invalid_native_database_inventory')
    succeeded = bool(not findings and proof['terminal_kind'] == 'deactivated_successfully' and result
        and result.get('quartus_returncode') == result.get('summarize_returncode') == 0 and guard
        and guard.get('vendor_returncode') == 0 and database)
    return dict(native_job_succeeded=succeeded, findings=findings, native_result=result,
        compiled_db_files=len(database) if isinstance(database,dict) else None,
        compiled_db_bytes=sum(row['size'] for row in database.values()) if isinstance(database,dict) else None,
        compiled_db_provenance='Native runner final inventory retained; raw QDB remains on worker, not transferred or rehashed by collector.',
        native_context_resources={key:context.get(key) for key in ('quartus_workers','affinity','physical_cores','cpu_max','memory_max','swap_max','started_at','timeout_seconds','launcher_sha256')} if context else None)


def collect(args):
    host = socket.gethostname().split('.')[0]
    need(sys.platform == 'linux' and os.geteuid() != 0 and host in ROOTS, 'existing nonroot Linux worker only')
    root = ROOTS[host]; project = args.project; output = args.output
    need(project.is_absolute() and project.resolve() == project and project.parent == root and project.is_dir(), 'exact existing worker project')
    need(output.is_absolute() and output.resolve() == output and output.parent == root and not output.exists(), 'fresh sibling evidence directory, never original project')
    need(args.request.is_relative_to(root) and pin(args.request)['sha256'] == args.request_sha256, 'source-bound existing plain request')
    request = json.loads(args.request.read_text())
    need(request['schema'] == 'plain-fit-request-v1' and request['host'] == host and request['project_name'] == project.name and request['unit'] == args.unit, 'request/project/host/unit binding')
    need(re.fullmatch(r'[a-zA-Z0-9_.-]+\.service', args.unit) and re.fullmatch('[0-9a-f]{32}', args.invocation), 'exact unit/invocation')
    need(args.scope in ('component_probe','whole_core') and (request.get('exemption') != 'component_sizing_probe' or args.scope == 'component_probe'), 'sizing probe cannot become whole-core timing')
    current = state(args.unit); quiescent(current, args.invocation)
    raw_journal = subprocess.check_output(['journalctl','-u',args.unit,'--no-pager','-o','json'], text=True, timeout=30)
    need(len(raw_journal.encode()) <= 32 << 20, 'finite invocation journal')
    proof, exact = journal_proof([json.loads(line) for line in raw_journal.splitlines()], args.unit, args.invocation)
    files = select_files(root, project, args.request, args.service_log)
    before = {name:pin(path) for name,path in files.items()}
    need(len(before) <= 10000 and sum(row['size'] for row in before.values()) <= LIMIT, 'finite source/report archive bound')
    assessment = assess(project, request, proof)
    output.mkdir()
    save(output/'unit-state-before.json', current)
    save(output/'native-journal-proof.json', proof)
    with (output/'native-journal.jsonl').open('x') as stream:
        for row in exact: stream.write(json.dumps(row, sort_keys=True)+'\n')
    after_state = state(args.unit); quiescent(after_state, args.invocation)
    save(output/'unit-state-after.json', after_state)
    for path in sorted(output.iterdir()): files['collection/'+path.name] = path
    inventory = {name:pin(path) for name,path in sorted(files.items())}
    save(output/'collection-inventory-v1.json', dict(schema='plain-fit-collection-inventory-v1', files=inventory,
        count=len(inventory), bytes=sum(row['size'] for row in inventory.values()), raw_qdb_included=False))
    files['collection/collection-inventory-v1.json'] = output/'collection-inventory-v1.json'
    archive = output/'native-reports.tar.gz'
    with tarfile.open(archive, 'w:gz', compresslevel=1) as tar:
        for name,path in sorted(files.items()): tar.add(path, arcname=name, recursive=False)
    need({name:pin(files[name]) for name in before} == before, 'native evidence changed during terminal collection')
    assessment.update(schema='plain-fit-terminal-collection-v1', collection_completed=True, terminal_proven=True,
        host=host, project=str(project), unit=args.unit, invocation_id=args.invocation, scope=args.scope,
        source_request_sha256=args.request_sha256, collector_sha256=pin(Path(__file__).resolve())['sha256'],
        observed_at_utc=datetime.now(timezone.utc).isoformat(), native_journal_proof=proof,
        archive=dict(path=str(archive), **pin(archive)), inventory_sha256=pin(output/'collection-inventory-v1.json')['sha256'],
        collected_native_report_files=sum(name.startswith('project/output_files/') for name in files),
        fit_allowed=False, promotion_allowed=False, whole_core_clock_claim=False,
        limitation='Terminal collection and source provenance only. Native failures stay failures; component clocks never become whole-core clocks. All-corner STA/critical paths require separate report interpretation and independent promotion review.')
    save(output/'terminal-collection-v1.json', assessment)
    print(json.dumps(dict(status='terminal_evidence_collected', native_job_succeeded=assessment['native_job_succeeded'],
        receipt=str(output/'terminal-collection-v1.json'), receipt_pin=pin(output/'terminal-collection-v1.json'), archive=assessment['archive']), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('project','request','output'): parser.add_argument('--'+name, type=Path, required=True)
    for name in ('request-sha256','unit','invocation'): parser.add_argument('--'+name, required=True)
    parser.add_argument('--scope', choices=('component_probe','whole_core'), required=True)
    parser.add_argument('--service-log', type=Path)
    collect(parser.parse_args())
