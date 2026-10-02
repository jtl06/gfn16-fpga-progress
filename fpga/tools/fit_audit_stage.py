"""Stable inventory/start entrypoint for a pinned, finite saved-layout audit.

Runs on the existing Linux worker only. Configuration is data; the selected
qualified adapter owns native bounds, source closure and financial checks.
No native invocation is retried after a write-ahead start intent.
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
import socket
import subprocess
import sys

KEYS = {'adapter', 'host', 'slot', 'unit', 'project', 'output', 'original_request',
        'terminal_receipt', 'original_invocation', 'manifest_sha256', 'selected_period_ns',
        'selection_reason', 'provider_inputs', 'transition', 'cutoff_utc'}
CAMPAIGN_END = datetime(2026, 10, 2, 16, tzinfo=timezone.utc)
WRAP_END = datetime(2026, 10, 3, 1, tzinfo=timezone.utc)


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def require_intake_open(end, now=None):
    now = now or datetime.now(timezone.utc)
    need(end.tzinfo is not None and end <= CAMPAIGN_END and now < end,
         'unchanged audit intake cutoff')
    need(now.timestamp()+2280+600 <= WRAP_END.timestamp(), 'audit completion and collection before wrap end')


def sha(path):
    path = Path(path)
    need(path.resolve() == path and path.is_file() and path.stat().st_nlink == 1,
         'canonical regular source')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pinned(ref):
    need(set(ref) == {'path', 'sha256'} and sha(ref['path']) == ref['sha256'], 'pinned source drift')
    return json.loads(Path(ref['path']).read_text())


def load(config_path, config_sha):
    cfg = pinned(dict(path=str(config_path), sha256=config_sha))
    need(set(cfg) in (KEYS, KEYS | {'hourly_provider_status'}), 'closed audit staging configuration')
    adapter = Path(cfg['adapter']['path'])
    need(sha(adapter) == cfg['adapter']['sha256'] and adapter.parent == config_path.parent,
         'flat exact adapter')
    module_spec = importlib.util.spec_from_file_location('configured_audit_adapter', adapter)
    ad = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(ad)
    need(cfg['host'] in ad.HOSTS and cfg['slot'] in ad.HOSTS[cfg['host']]['slots'], 'existing host and slot')
    root = Path(ad.HOSTS[cfg['host']]['root'])
    need(sys.platform == 'linux' and os.geteuid() != 0
         and socket.gethostname().split('.')[0] == cfg['host'] and config_path.parent.parent == root,
         'existing nonroot native worker and sibling tools')
    need(not (root/'PAUSE').exists() and not (config_path.parent/'fpga/docs/briefs/PAUSE').exists(), 'PAUSE')
    end = datetime.fromisoformat(cfg['cutoff_utc'].replace('Z', '+00:00'))
    require_intake_open(end)
    need(Path(cfg['project']).parent == root and Path(cfg['output']).parent == root, 'owned original and private output')
    need(sha(Path(cfg['project'])/'manifest.json') == cfg['manifest_sha256'], 'exact original design')
    terminal = pinned(cfg['terminal_receipt'])
    need(terminal['invocation_id'] == cfg['original_invocation'] and terminal['terminal_proven'] is True,
         'trusted original terminal identity')
    return cfg, ad, root


def locks(ad, host, slot, root):
    stack = ExitStack()
    try:
        physical = ad.topology(host, slot)
        for name, mode in ad.lock_names(host, slot, physical):
            fd = os.open(root/name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            stack.callback(os.close, fd)
            need(os.fstat(fd).st_nlink == 1, 'canonical mode/slot/core lock')
            fcntl.flock(fd, mode | fcntl.LOCK_NB)
        return stack
    except BaseException:
        stack.close()
        raise


def prepare(config_path, config_sha):
    cfg, ad, root = load(config_path, config_sha)
    tools = config_path.parent
    need(not (tools/'preparation.json').exists() and not (tools/'spec.json').exists(),
         'fresh preparation only; retain interrupted preparation')
    with locks(ad, cfg['host'], cfg['slot'], root):
        h = ad.helper(tools)
        original = pinned(cfg['original_request'])
        state = dict(line.split('=', 1) for line in subprocess.check_output(
            ['systemctl', 'show', original['unit'], '-p', 'MainPID', '-p', 'ActiveState', '-p', 'InvocationID'],
            text=True, timeout=15).splitlines())
        need(state['MainPID'] == '0' and state['ActiveState'] in ('inactive', 'failed')
             and state['InvocationID'] in ('', cfg['original_invocation']), 'original actual unit quiescent')
        project = Path(cfg['project'])
        spec = h.make_spec(project, Path(cfg['output']), Path(cfg['terminal_receipt']['path']),
            tools/ad.TCL, {str(root/'altera_pro/26.1/quartus'/name):pin for name,pin in ad.STA_PINS.items()},
            scope=original.get('scope', 'whole_core'), native_seconds=ad.INNER,
            maximum_copy_bytes=64 << 30, selected_period_ns=cfg['selected_period_ns'],
            selection_reason=cfg['selection_reason'])
        ad.save(tools/'spec.json', spec)
        spec_ref = dict(path=str(tools/'spec.json'), sha256=sha(tools/'spec.json'))
        budget = None
        if 'hourly_provider_status' in cfg:
            budget=dict(host=cfg['host'],max_seconds=ad.HORIZON,source_sha256=spec_ref['sha256'],
                        hourly_provider_status=cfg['hourly_provider_status'])
            ad.hourly_status(budget,cfg['host'])
        elif cfg['host'] == ad.FIT:
            meter = ad.meter(cfg['host'], tools/'fpga')
            provider = cfg['provider_inputs']
            transition = cfg['transition']
            budget = meter.make_budget(cfg['host'], ad.HORIZON, provider['path'], provider['sha256'],
                spec_ref['sha256'], transition_path=transition['path'], transition_sha256=transition['sha256'])
        runtime = ad.runtime_pins(cfg['host'], budget, tools/'fpga')
        request = ad.make_request(spec_ref, cfg['original_request'], cfg['host'], cfg['slot'], cfg['unit'], runtime, budget)
        ad.save(tools/'request.json', request)
        result = dict(status='prepared_not_launched', config_sha256=config_sha,
                      stage_source_sha256=sha(Path(__file__).resolve()),
                      request_path=str(tools/'request.json'), request_sha256=sha(tools/'request.json'),
                      spec_sha256=spec_ref['sha256'], original_tree_sha256=spec['original_tree_sha256'],
                      qdb_inventory_sha256=spec['qdb_inventory_sha256'])
        ad.save(tools/'preparation.json', result)
        return result


def start(config_path, config_sha):
    cfg, ad, root = load(config_path, config_sha)
    tools = config_path.parent
    prepared = json.loads((tools/'preparation.json').read_text())
    need(prepared['config_sha256'] == config_sha and not (tools/'start-intent.json').exists(),
         'same preparation and no prior start intent; never retry')
    request_ref = dict(path=prepared['request_path'], sha256=prepared['request_sha256'])
    request = pinned(request_ref)
    spec, h, original, terminal = ad.verify_request(request, tools)
    need(all(request[key] == cfg[key] for key in ('host', 'slot', 'unit'))
         and request['original_request'] == cfg['original_request']
         and all(spec[key] == cfg[key] for key in ('project', 'output', 'selected_period_ns', 'selection_reason')),
         'prepared request and selected period match immutable configuration')
    budget = ad.admission(request, tools/'fpga')
    need(budget['status'] == 'PASS_budget_only_no_job_reservation', 'fresh host-hours admission')
    with locks(ad, cfg['host'], cfg['slot'], root):
        ad.scratch(root, sum(row['size'] for row in request['original_tree'].values()))
        mem = {k:int(v.split()[0])*1024 for k,v in
               (line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())}
        need(mem['MemAvailable'] >= ad.HOSTS[cfg['host']]['memory']+(4 << 30), 'actual memory headroom')
        state = dict(line.split('=', 1) for line in subprocess.check_output(
            ['systemctl', 'show', cfg['unit'], '-p', 'LoadState', '-p', 'MainPID'], text=True, timeout=15).splitlines())
        journal = subprocess.check_output(['journalctl', '-u', cfg['unit'], '-o', 'json', '--no-pager'], text=True, timeout=15)
        need(state['LoadState'] == 'not-found' and state['MainPID'] == '0' and not journal.strip(),
             'fresh unit without a prior invocation')
        ad.save(tools/'start-intent.json', dict(status='write_ahead_never_retry', config_sha256=config_sha,
            request_sha256=request_ref['sha256'], unit=cfg['unit'], at_utc=ad.now().isoformat(), host_hours=budget))
    argv = ad.service_argv(request_ref)
    result = subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=30)
    ad.save(tools/'start-rpc.json', dict(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr,
                                     argv=argv, at_utc=ad.now().isoformat()))
    need(result.returncode == 0, 'uncertain start RPC: observe actual unit, never retry')
    state = dict(line.split('=', 1) for line in subprocess.check_output(
        ['systemctl', 'show', cfg['unit'], '-p', 'MainPID', '-p', 'ActiveState', '-p', 'SubState', '-p', 'InvocationID'],
        text=True, timeout=15).splitlines())
    observation = dict(unit=cfg['unit'], state=state, at_utc=ad.now().isoformat(), request=request_ref)
    ad.save(tools/'start-observation.json', observation)
    return observation


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'start'))
    parser.add_argument('config', type=Path)
    parser.add_argument('config_sha256')
    args = parser.parse_args()
    print(json.dumps(globals()[args.action](args.config, args.config_sha256), indent=2))
