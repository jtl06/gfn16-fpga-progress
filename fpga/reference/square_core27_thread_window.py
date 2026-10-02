"""Run one quiet, bounded timing window against frozen thread-benchmark builds.

No compile-lock wait occurs here: the owner reserves a quiet window first.
Separate windows permit other agents' queued evidence to progress between them.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import socket
import time
from .square_core27_thread_benchmark import cpu_context, run, save, sha, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--aw', type=int, choices=[5, 16], required=True)
    parser.add_argument('--cpus', required=True)
    parser.add_argument('--seconds', type=int, default=540)
    args = parser.parse_args()
    if socket.gethostname() != 'aethia':
        raise RuntimeError('aethia only')
    if not 60 <= args.seconds <= 570:
        raise ValueError('window must be 60..570 seconds; cleanup has a separate ten-second bound')
    resource.setrlimit(resource.RLIMIT_AS, (6 << 30, 6 << 30))
    manifest_path = args.build_report.resolve()
    manifest = json.loads(manifest_path.read_text())
    if manifest['status'] != 'built-awaiting-coordinated-timing':
        raise ValueError('fresh, completed build evidence required')
    verify(manifest['inputs'])
    cpus = [int(item) for item in args.cpus.split(',')]
    context = cpu_context()
    if len(cpus) != 8 or len(set(cpus)) != 8 or not set(cpus) <= set(context['affinity']):
        raise ValueError('eight distinct eligible CPUs required')
    os.sched_setaffinity(0, cpus)
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = dict(status='running', build_report=str(manifest_path),
                  build_report_sha256=sha(manifest_path), runner_sha256=sha(__file__),
                  aw=args.aw, n=1 << args.aw, cpu_context=context, affinity=cpus,
                  memory_limit_bytes=6 << 30, window_seconds=args.seconds,
                  runs=[], lock_wait_seconds=0,
                  note='Parent/queue owner confirmed quiet window before invocation; no lock-wait time is measured.')
    deadline = time.monotonic() + args.seconds
    builds = {item['threads']: item for item in manifest['builds'] if item['aw']==args.aw}
    order = (1, 8, 8, 1) if args.aw == 5 else (1, 8)
    outputs = []
    try:
        for index, threads in enumerate(order):
            remaining = deadline - time.monotonic()
            if remaining <= 1:
                report.update(status='incomplete-window-cap', unexecuted_order=list(order[index:]))
                break
            item = builds[threads]
            verify(manifest['inputs'])
            if sha(item['executable']) != item['executable_sha256']:
                raise ValueError('executable identity changed')
            result = run(out, f'aw{args.aw}-threads{threads}-r{index}',
                         [item['executable'], manifest['fixtures'][str(args.aw)], 'cache'],
                         timeout=min(600, remaining))
            result.update(threads=threads, repeat=index,
                          executable_sha256=item['executable_sha256'],
                          permitted_runtime_seconds=min(600, remaining))
            report['runs'].append(result)
            if result['timed_out']:
                report.update(status='incomplete-window-cap', unexecuted_order=list(order[index+1:]))
                break
            if result['returncode']:
                raise RuntimeError('oracle execution failed')
            payload = Path(result['stdout']).read_bytes()
            if b'PASS n=' not in payload:
                raise RuntimeError('oracle completion absent')
            outputs.append(payload)
            if payload != outputs[0]:
                raise RuntimeError('thread-count/repeat output or counter nondeterminism')
            verify(manifest['inputs'])
            if sha(item['executable']) != item['executable_sha256']:
                raise ValueError('executable changed during run')
            save(out / 'report.json', report)
        else:
            report['status'] = 'passed'
        verify(manifest['inputs'])
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        save(out / 'report.json', report)


if __name__ == '__main__':
    main()
