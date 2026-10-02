"""Real file-lock races/lifetime checks; no HDL, compilers, or cloud access."""
import fcntl
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from fpga.tools import native_resource_leases_v1 as r


TOPOLOGY = [dict(cpu=cpu, package_id=0, core_id=cpu // 2) for cpu in range(16)]


def observation(external=(), available=100):
    return dict(observed_at_unix=time.time(), complete=True, available_memory_bytes=available,
                external_reservations=list(external))


def pool_options(directory, **changes):
    options = dict(directory=Path(directory), topology=TOPOLOGY, total_memory_bytes=100,
                   memory_floor_bytes=20, max_jobs=4, max_job_cpus=2, max_job_memory_bytes=30)
    options.update(changes)
    return options


def concurrent_resource_worker(directory, name, start, release, messages, cpus):
    start.wait(10)
    try:
        with r.ResourcePool(**pool_options(directory)).acquire(name, cpus, 20, observer=observation) as held:
            messages.put(('acquired', name, held.receipt['physical_cores']))
            release.wait(10)
    except r.LeaseBusy:
        messages.put(('busy', name))
    except BaseException as error:
        messages.put(('error', name, repr(error)))


def crash_resource_worker(directory, messages):
    held = r.ResourcePool(**pool_options(directory)).acquire('crashed-worker', [0, 2], 20, observer=observation)
    messages.put(held.receipt)
    messages.close()
    messages.join_thread()
    os._exit(23)


def crash_compile_worker(directory, legacy, messages):
    held = r.CompileSlots(legacy, directory).acquire()
    messages.put(held.receipt)
    messages.close()
    messages.join_thread()
    os._exit(24)


class ResourceLeases(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name).resolve()
        self.pool = r.ResourcePool(**pool_options(self.directory))
        self.legacy = self.directory / 'compile.lock'
        self.legacy.write_text('legacy inode retained\n')
        self.compile = r.CompileSlots(self.legacy, self.directory)

    def tearDown(self):
        self.temporary.cleanup()

    def acquire(self, name='job-a', cpus=None, memory=20, **kwargs):
        return self.pool.acquire(name, [0, 2] if cpus is None else cpus, memory,
                                 observer=kwargs.pop('observer', observation), **kwargs)

    def test_two_compiles_coexist_but_third_cannot_enter(self):
        with self.compile.acquire() as first, self.compile.acquire() as second:
            self.assertEqual({first.receipt['slot'], second.receipt['slot']}, {0, 1})
            with self.assertRaises(r.LeaseBusy):
                self.compile.acquire()
            with self.legacy.open('r') as exclusive:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(exclusive, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with self.legacy.open('r') as exclusive:
            fcntl.flock(exclusive, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.assertEqual(self.legacy.read_text(), 'legacy inode retained\n')

    def test_live_legacy_exclusive_lock_blocks_both_new_slots(self):
        inode = self.legacy.stat().st_ino
        with self.legacy.open('r') as legacy:
            fcntl.flock(legacy, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for _ in range(3):
                with self.assertRaises(r.LeaseBusy):
                    self.compile.acquire()
            # Failed acquisitions release their provisional slot locks.
            for slot in range(2):
                with (self.directory / f'compile-slot-{slot}.lock').open('a+') as free:
                    fcntl.flock(free, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.assertEqual(self.legacy.stat().st_ino, inode)
        with self.compile.acquire():
            pass

    def test_missing_or_symlink_legacy_lock_is_never_created_or_bypassed(self):
        absent = self.directory / 'absent.lock'
        with self.assertRaises(FileNotFoundError):
            r.CompileSlots(absent, self.directory)
        self.assertFalse(absent.exists())
        link = self.directory / 'link.lock'
        link.symlink_to(self.legacy)
        with self.assertRaises(OSError):
            r.CompileSlots(link, self.directory)

    def test_compile_release_does_not_release_runtime_resources(self):
        with self.acquire() as job:
            with self.compile.acquire() as compiler:
                self.assertEqual(len(compiler.pass_fds), 2)
            with self.compile.acquire(), self.compile.acquire():
                pass
            with self.assertRaises(r.LeaseBusy):
                self.acquire('runtime-overlap', cpus=[1, 3])
            job.check()
        with self.acquire('next-job', cpus=[1, 3]):
            pass
        self.assertTrue((self.directory / 'job-a.lease.json').is_file())
        self.assertTrue((self.directory / 'job-a.released.json').is_file())

    def test_admits_four_two_core_jobs_with_adjacent_smt_topology(self):
        held = []
        try:
            for index in range(4):
                held.append(self.acquire('job-' + str(index), cpus=[index * 4, index * 4 + 2]))
            with self.assertRaises(r.LeaseBusy):
                self.acquire('fifth-job', cpus=[1])
            self.assertEqual(sum(item.receipt['memory_bytes'] for item in held), 80)
            self.assertEqual(len({tuple(core) for item in held for core in item.receipt['physical_cores']}), 8)
        finally:
            for item in held:
                item.close()

    def test_smt_duplicate_unknown_cpu_and_boolean_caps_fail_closed(self):
        for cpus in ([0, 1], [0, 0], [16], [True]):
            with self.subTest(cpus=cpus), self.assertRaises(r.LeaseError):
                self.acquire(cpus=cpus)
        with self.assertRaises(r.LeaseError):
            self.acquire(memory=True)
        with self.assertRaises(r.LeaseError):
            self.acquire(memory=31)
        with self.assertRaises(r.LeaseError):
            self.acquire(cpus=[0, 2, 4])

    def test_external_legacy_jobs_reserve_cores_memory_and_job_capacity(self):
        old = [dict(id='old-f2', cpus=[0, 2], memory_bytes=20, managed_lease_id=None),
               dict(id='old-t5b', cpus=[4, 6], memory_bytes=30, managed_lease_id=None)]
        observe = lambda: observation(old)
        with self.assertRaises(r.LeaseBusy):
            self.acquire('sibling-conflict', cpus=[1, 3], observer=observe)
        with self.acquire('job-c', cpus=[8, 10], memory=20, observer=observe):
            with self.assertRaisesRegex(r.LeaseBusy, 'aggregate memory'):
                self.acquire('too-much-memory', cpus=[12, 14], memory=20, observer=observe)
            with self.acquire('job-d', cpus=[12, 14], memory=10, observer=observe):
                with self.assertRaisesRegex(r.LeaseBusy, 'capacity'):
                    self.acquire('fifth', cpus=[1], observer=observe)

    def test_low_live_memory_blocks_even_when_reservation_ledger_has_room(self):
        with self.assertRaisesRegex(r.LeaseBusy, 'available memory'):
            self.acquire(observer=lambda: observation(available=39))
        self.assertFalse((self.directory / 'job-a.lease.lock').exists())

    def test_unknown_stale_future_incomplete_or_overlapping_observations_block(self):
        observations = [None, dict(observation(), complete=False),
                        dict(observation(), observed_at_unix=time.time() - 31),
                        dict(observation(), observed_at_unix=time.time() + 31),
                        observation([dict(id='one', cpus=[0], memory_bytes=10, managed_lease_id=None),
                                     dict(id='two', cpus=[1], memory_bytes=10, managed_lease_id=None)])]
        for data in observations:
            with self.subTest(observation=data), self.assertRaises(r.LeaseError):
                self.acquire(observer=lambda: data)
        with self.assertRaises(r.LeaseError):
            self.acquire(observer=None)

    def test_matching_managed_observation_is_not_counted_twice(self):
        with self.acquire() as held:
            observed = [dict(id='unit-a', cpus=[0, 2], memory_bytes=20, managed_lease_id='job-a')]
            with self.acquire('job-b', cpus=[4, 6], observer=lambda: observation(observed)):
                pass
            observed[0]['memory_bytes'] = 19
            with self.assertRaisesRegex(r.LeaseError, 'mismatch'):
                self.acquire('bad-match', cpus=[8, 10], observer=lambda: observation(observed))
            held.check()

    def test_stale_pid_metadata_never_frees_a_live_lock(self):
        with self.acquire():
            path = self.directory / 'job-a.lease.json'
            record = json.loads(path.read_text())
            record['pid'] = 999999999
            record['acquired_at_unix'] = 0
            path.write_text(json.dumps(record))
            with self.assertRaises(r.LeaseBusy):
                self.acquire('would-steal', cpus=[1, 3])

    def test_unlocked_corrupt_crash_metadata_is_retained_without_reserving(self):
        lock = self.directory / 'old.lease.lock'
        metadata = self.directory / 'old.lease.json'
        lock.write_text('')
        metadata.write_text('interrupted json {')
        with self.acquire():
            pass
        self.assertEqual(metadata.read_text(), 'interrupted json {')

    def test_locked_corrupt_metadata_fails_closed_and_releases_partial_locks(self):
        with self.acquire():
            (self.directory / 'job-a.lease.json').write_text('{}')
            with self.assertRaises((r.LeaseError, KeyError)):
                self.acquire('job-b', cpus=[4, 6])
        # Historical corruption does not become a permanent live reservation.
        with self.acquire('job-c', cpus=[4, 6]):
            pass

    def test_pool_policy_and_physical_topology_drift_are_refused(self):
        with self.acquire():
            pass
        changed = r.ResourcePool(**pool_options(self.directory, max_jobs=3))
        with self.assertRaisesRegex(r.LeaseError, 'policy/topology drift'):
            changed.acquire('changed-policy', [4, 6], 20, observer=observation)
        self.assertFalse((self.directory / 'changed-policy.lease.lock').exists())

    def test_interoperable_fit_exclusive_and_core_interlocks(self):
        mode_path = self.directory / '.native-fit-mode.lock'
        mapping = {(0, core): self.directory / f'.physical-core-{core}.lock' for core in range(8)}
        pool = r.ResourcePool(**pool_options(self.directory, mode_lock=mode_path, core_locks=mapping))
        with pool.acquire('simulation', [0, 2], 20, observer=observation):
            with mode_path.open('r') as fit:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(fit, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with mode_path.open('r') as fit:
            fcntl.flock(fit, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(r.LeaseBusy, 'mode occupied'):
                pool.acquire('blocked-by-fit', [4, 6], 20, observer=observation)
        mapping[(0, 2)].touch()
        with mapping[(0, 2)].open('r') as fit_core:
            fcntl.flock(fit_core, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(r.LeaseBusy, 'interlock occupied'):
                pool.acquire('blocked-by-core', [4, 6], 20, observer=observation)
        with pool.acquire('after-fit', [4, 6], 20, observer=observation):
            pass

    def test_failed_guard_exception_and_duplicate_identity_release_all_leases(self):
        calls = []
        def fail_late():
            calls.append(1)
            if len(calls) == 2:
                raise RuntimeError('PAUSE appeared')
        with self.assertRaisesRegex(RuntimeError, 'PAUSE'):
            self.acquire(guard=fail_late)
        self.assertFalse((self.directory / 'job-a.lease.lock').exists())
        with self.acquire():
            with self.assertRaisesRegex(r.LeaseError, 'already used'):
                self.acquire()
        with self.assertRaisesRegex(r.LeaseError, 'already used'):
            self.acquire()
        with self.acquire('unique-next'):
            pass

    def test_compile_guard_failure_and_body_exception_release_both_slots(self):
        def fail():
            raise RuntimeError('source drift')
        with self.assertRaises(RuntimeError):
            self.compile.acquire(guard=fail)
        with self.assertRaises(RuntimeError):
            with self.compile.acquire():
                raise RuntimeError('build failed')
        with self.compile.acquire(), self.compile.acquire():
            pass

    def test_replaced_lock_inode_and_hardlinks_are_detected(self):
        held = self.acquire()
        try:
            original = self.directory / 'job-a.lease.lock'
            original.rename(self.directory / 'retained-original')
            original.write_text('')
            with self.assertRaisesRegex(r.LeaseError, 'unchanged'):
                held.check()
        finally:
            held.close()
        hard = self.directory / 'hard.lock'
        os.link(self.legacy, hard)
        with self.assertRaisesRegex(r.LeaseError, 'single-link'):
            r.CompileSlots(self.legacy, self.directory)

    def test_crashed_resource_and_compile_owners_release_kernel_locks(self):
        context = multiprocessing.get_context('spawn')
        messages = context.Queue()
        worker = context.Process(target=crash_resource_worker, args=(str(self.directory), messages))
        worker.start()
        receipt = messages.get(timeout=10)
        worker.join(10)
        self.assertEqual(worker.exitcode, 23)
        self.assertEqual(receipt['lease_id'], 'crashed-worker')
        self.assertFalse((self.directory / 'crashed-worker.released.json').exists())
        with self.acquire('after-crash'):
            pass
        compiler = context.Process(target=crash_compile_worker, args=(str(self.directory), str(self.legacy), messages))
        compiler.start()
        self.assertEqual(messages.get(timeout=10)['schema'], 'native-compile-slot-v1')
        compiler.join(10)
        self.assertEqual(compiler.exitcode, 24)
        with self.compile.acquire(), self.compile.acquire():
            pass
        messages.close()

    def test_inherited_workload_descriptors_keep_reservations_after_owner_close(self):
        held = self.acquire()
        child = subprocess.Popen([sys.executable, '-c', 'import sys; print("ready", flush=True); sys.stdin.read()'],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, pass_fds=held.pass_fds)
        try:
            self.assertEqual(child.stdout.readline(), 'ready\n')
            held.close()
            with self.assertRaises(r.LeaseBusy):
                self.acquire('child-still-live')
            child.communicate('', timeout=10)
            with self.acquire('after-child'):
                pass
        finally:
            held.close()
            if child.poll() is None:
                child.communicate('', timeout=10)

    def race(self, cpus_by_worker):
        context = multiprocessing.get_context('spawn')
        start, release, messages = context.Event(), context.Event(), context.Queue()
        workers = [context.Process(target=concurrent_resource_worker,
                    args=(str(self.directory), f'worker-{index}', start, release, messages, cpus))
                   for index, cpus in enumerate(cpus_by_worker)]
        for worker in workers:
            worker.start()
        start.set()
        try:
            results = [messages.get(timeout=10) for _ in workers]
            self.assertFalse(any(item[0] == 'error' for item in results), results)
            return results
        finally:
            release.set()
            for worker in workers:
                worker.join(10)
                self.assertEqual(worker.exitcode, 0)
            messages.close()

    def test_racing_same_physical_core_admits_exactly_one(self):
        results = self.race([[0, 2], [1, 3]])
        self.assertEqual(sum(item[0] == 'acquired' for item in results), 1)

    def test_racing_disjoint_jobs_never_exceed_aggregate_capacity(self):
        # A transient mutex collision is a refusal, never over-admission.
        results = self.race([[0], [2], [4], [6], [8], [10]])
        admitted = [item for item in results if item[0] == 'acquired']
        self.assertGreaterEqual(len(admitted), 1)
        self.assertLessEqual(len(admitted), 4)
        cores = [tuple(core) for item in admitted for core in item[2]]
        self.assertEqual(len(cores), len(set(cores)))


if __name__ == '__main__':
    unittest.main()
