"""Additive v1 smoke successor: a live legacy EX is compatibility evidence.

Runs only Python coordination tests in a finite cgroup on dispatcher-reserved
aethia CPUs8/10. Never starts HDL/vendor work or interrupts an old compiler.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

from fpga.tools import native_resource_leases_v1 as leases


GIB = 1 << 30
LEGACY = Path('/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock')


def run(directory):
    leases.require(socket.gethostname() == 'aethia', 'aethia-only coordination smoke')
    directory = leases.canonical_directory(directory)
    leases.require(not (directory / 'smoke-report.json').exists(), 'fresh write-once smoke report')
    affinity = sorted(os.sched_getaffinity(0))
    leases.require(affinity == [8, 10], 'dispatcher-reserved smoke affinity8/10')
    cgroup = next(row.split('::', 1)[1] for row in Path('/proc/self/cgroup').read_text().splitlines() if row.startswith('0::'))
    group = Path('/sys/fs/cgroup') / cgroup.lstrip('/')
    quota, period = map(int, (group / 'cpu.max').read_text().split())
    memory = int((group / 'memory.max').read_text())
    leases.require(0 < quota <= 2 * period and 0 < memory <= 512 * 1024**2
                   and (group / 'memory.swap.max').read_text().strip() == '0', '512MiB/200%/no-swap smoke cgroup')
    rows = []
    for cpu in range(16):
        top = Path('/sys/devices/system/cpu') / f'cpu{cpu}/topology'
        rows.append(dict(cpu=cpu, package_id=int((top / 'physical_package_id').read_text()),
                         core_id=int((top / 'core_id').read_text())))
    leases.require(rows == [dict(cpu=cpu, package_id=0, core_id=cpu // 2) for cpu in range(16)], 'aethia adjacent SMT topology')
    mem = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    total = int(mem['MemTotal'].split()[0]) * 1024
    source_pins = {}
    for source in (Path(__file__).resolve(), Path(leases.__file__).resolve()):
        with source.open('rb') as stream:
            source_pins[str(source)] = hashlib.file_digest(stream, 'sha256').hexdigest()
    report = dict(schema='native-resource-coordination-smoke-v2', status='running', host='aethia',
        evidence_class='Linux pure-Python flock coordination; no HDL/vendor/native arithmetic validation',
        started_at_unix=time.time(), affinity=affinity, cgroup=cgroup,
        limits=dict(cpu_max=[quota, period], memory_max_bytes=memory, swap_max_bytes=0),
        topology=rows, original_legacy_inode=LEGACY.stat().st_ino, legacy_lock=str(LEGACY), source_sha256=source_pins,
        retained='All source/test outputs, failures and lock metadata retained; no cleanup')

    def guard():
        leases.require(time.time() - report['started_at_unix'] < 45, '45-second finite coordination bound')
        for flag in (Path('/home/jtl/gfn-fpga-lab/agent-work/native-test-queue/PAUSE'),
                     Path('/home/jtl/gfn-fpga-lab/fpga/docs/briefs/PAUSE'), directory / 'PAUSE'):
            leases.require(not flag.exists(), 'PAUSE: ' + str(flag))
        leases.require(shutil.disk_usage(directory).free >= 10 * GIB, 'durable disk floor')

    def observer():
        mem = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        return dict(observed_at_unix=time.time(), complete=True,
            available_memory_bytes=int(mem['MemAvailable'].split()[0]) * 1024,
            external_reservations=[dict(id='legacy-cpu02-conservative', cpus=[0, 2], memory_bytes=4 * GIB, managed_lease_id=None),
                                   dict(id='legacy-cpu46-conservative', cpus=[4, 6], memory_bytes=6 * GIB, managed_lease_id=None)])

    try:
        guard()
        pool = leases.ResourcePool(directory, topology=rows, total_memory_bytes=total, memory_floor_bytes=4 * GIB,
            max_jobs=4, max_job_cpus=2, max_job_memory_bytes=6 * GIB)
        with pool.acquire('bounded-smoke', [8, 10], memory, observer=observer, guard=guard) as job:
            report['resource_lease'] = job.receipt
            slots = leases.CompileSlots(LEGACY, directory)
            try:
                first = slots.acquire(guard=guard)
            except leases.LeaseBusy:
                # No compiler is launched and no timeout implies termination.
                # The fresh isolated slot is known free; SH refusal establishes
                # that the original EX lock is occupied at this instant.
                report['legacy_live_exclusive_blocks_new_builds'] = True
                report['actual_shared_compile_overlap'] = 'deferred_until_legacy_exclusive_release'
            else:
                with first, slots.acquire(guard=guard) as second:
                    report['compile_slots'] = [first.receipt, second.receipt]
                    try:
                        slots.acquire(guard=guard)
                    except leases.LeaseBusy:
                        report['third_compile_refused'] = True
                    else:
                        raise leases.LeaseError('third compile unexpectedly admitted')
                    with LEGACY.open('r') as old:
                        try:
                            fcntl.flock(old, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        except BlockingIOError:
                            report['legacy_exclusive_refused_while_shared_builds'] = True
                        else:
                            raise leases.LeaseError('legacy EX unexpectedly admitted')
            try:
                pool.acquire('same-core-refusal', [9, 11], memory, observer=observer, guard=guard)
            except leases.LeaseBusy:
                report['runtime_smt_overlap_refused_after_compile_release'] = True
            else:
                raise leases.LeaseError('runtime resource reservation unexpectedly released')
            guard()
            with (directory / 'python-tests.stdout.log').open('x') as output, (directory / 'python-tests.stderr.log').open('x') as error:
                child = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'fpga.tests.test_native_resource_leases_v1', '-v'],
                    stdout=output, stderr=error, timeout=30, pass_fds=job.pass_fds, check=False)
            report['source_tests_returncode'] = child.returncode
            leases.require(child.returncode == 0, 'Linux coordination tests failed; logs retained')
        leases.require(LEGACY.stat().st_ino == report['original_legacy_inode'], 'legacy lock inode changed')
        report['status'] = 'passed_linux_coordination_only'
    except BaseException as error:
        report['status'] = 'failed_coordination_retained'
        report['error'] = repr(error)
        raise
    finally:
        report['finished_at_unix'] = time.time()
        leases._write_once(directory / 'smoke-report.json', report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', required=True, type=Path)
    run(parser.parse_args().directory)
