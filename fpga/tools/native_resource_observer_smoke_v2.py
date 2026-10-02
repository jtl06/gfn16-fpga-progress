"""Additive source-only smoke with an explicit fresh permanent lease ID."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from fpga.tools import native_resource_leases_v1 as leases
from fpga.tools import native_resource_observer_v1 as observations


def execute(profile_path, evidence, lease_id):
    leases.identifier(lease_id)
    profile = json.loads(profile_path.read_text())
    evidence = leases.canonical_directory(evidence)
    leases.require(sorted(os.sched_getaffinity(0)) == [8, 10], 'fresh dispatcher-reserved smokeCPU8/10')
    observer = observations.LegacyObserver(profile)
    receipt = dict(schema='native-resource-observer-smoke-v2', lease_id=lease_id, status='running', started_at_unix=time.time(),
                   evidence_class='Linux Python observer/coordination only; no HDL/vendor/cloud workload')
    try:
        before = observer.capture(require_disk=True)
        leases._write_once(evidence / 'before.json', before)
        occupied = {tuple(profile['topology'][str(cpu)]) for item in before['observation']['external_reservations'] for cpu in item['cpus']}
        leases.require(not occupied & {(0, 4), (0, 5)}, 'smoke physical cores no longer free')
        policy = observer.pool_policy()
        with leases.ResourcePool(**policy).acquire(lease_id, [8, 10], 512 * 1024**2, observer=observer) as job:
            receipt['job'] = job.receipt
            live = observer.capture(require_disk=True)
            leases._write_once(evidence / 'held.json', live)
            leases.require(any(item['managed_lease_id'] == lease_id for item in live['observation']['external_reservations']),
                           'own real cgroup/descriptor lease observed')
            for name, cpus, memory in [('smt-refusal', [9, 11], 512 * 1024**2),
                                       ('opt8-refusal', profile['opt8_cpus'], profile['opt8_memory_bytes'])]:
                try:
                    leases.ResourcePool(**policy).acquire(lease_id + '-' + name, cpus, memory, observer=observer)
                except leases.LeaseBusy:
                    receipt[name] = 'refused_while_live_lease'
                else:
                    raise leases.LeaseError('occupied resources unexpectedly admitted: ' + name)
            observer.validate_disk()
            with (evidence / 'python-tests.stdout.log').open('x') as out, (evidence / 'python-tests.stderr.log').open('x') as err:
                completed = subprocess.run([sys.executable, '-B', '-m', 'unittest',
                    'fpga.tests.test_native_resource_leases_v1', 'fpga.tests.test_native_resource_observer_v1',
                    'fpga.tests.test_native_user_quota_v1', 'fpga.tests.test_native_user_quota_v2', '-v'],
                    stdout=out, stderr=err, timeout=25, pass_fds=job.pass_fds)
            leases.require(completed.returncode == 0, 'Python tests failed; all logs retained')
            receipt['source_tests_returncode'] = completed.returncode
        released = observer.capture(require_disk=True)
        leases._write_once(evidence / 'released.json', released)
        leases.require(not any(item['managed_lease_id'] == lease_id for item in released['observation']['external_reservations']),
                       'released lease still reserved')
        receipt['status'] = 'passed_real_cgroup_observer_and_quota_coordination'
    except BaseException as error:
        receipt['status'] = 'failed_smoke_retained'
        receipt['error'] = repr(error)
        raise
    finally:
        receipt['finished_at_unix'] = time.time()
        leases._write_once(evidence / 'smoke-report.json', receipt)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--id', required=True)
    args = parser.parse_args()
    execute(args.profile, args.evidence, args.id)
