"""Additive native-job leases, not a dispatcher or resource-limit launcher.

CompileSlots holds SH on the *existing* legacy compile.lock throughout a build
plus EX on one new slot. Old EX compilers/cleanup therefore still exclude all
new builds. ResourcePool holds whole-job physical-core and memory reservations
independently of compile slots. It never kills/reaps a PID, deletes a lock, or
turns a stale PID/time limit into evidence that a workload has ended.

The caller supplies a fresh, complete legacy-job observation and enforces its
existing source/tool/PAUSE/cgroup/time/disk gates. Use one canonical pool per
host. Include pass_fds in Popen when children must keep reservations after a
parent crash, or use a service whose failure terminates every workload child.
All metadata is retained; flock, rather than PID metadata, establishes liveness.
"""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import time


class LeaseError(ValueError):
    """A malformed or unverified reservation must not be admitted."""


class LeaseBusy(LeaseError):
    """A verified resource is currently unavailable."""


def require(ok, message):
    if not ok:
        raise LeaseError(message)


def integer(value, name, minimum=1):
    require(type(value) is int and value >= minimum, 'invalid ' + name)
    return value


def identifier(value):
    require(type(value) is str and re.fullmatch('[a-z0-9][a-z0-9-]{0,95}', value), 'lease identifier')
    return value


def canonical_directory(path):
    path = Path(path)
    require(path.is_absolute() and path.is_dir() and path.resolve() == path, 'pre-existing canonical lock directory')
    return path


class _Lock:
    def __init__(self, path, *, create=True, exclusive_create=False):
        self.path = Path(path)
        require(self.path.is_absolute() and self.path.parent.resolve() == self.path.parent
                and self.path.parent.is_dir(), 'canonical lock parent')
        flags = os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW
        if create:
            flags |= os.O_CREAT
        if exclusive_create:
            flags |= os.O_EXCL
        self.fd = os.open(self.path, flags, 0o600)
        try:
            self.check()
        except BaseException:
            self.close()
            raise

    def check(self):
        actual = os.fstat(self.fd)
        current = self.path.lstat()
        require(stat.S_ISREG(actual.st_mode) and actual.st_nlink == 1
                and (actual.st_dev, actual.st_ino) == (current.st_dev, current.st_ino),
                'regular, unchanged, single-link lock: ' + str(self.path))

    def try_acquire(self, mode=fcntl.LOCK_EX):
        self.check()
        try:
            fcntl.flock(self.fd, mode | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False

    def close(self):
        if self.fd is not None:
            # Do not LOCK_UN: inherited descriptors must keep the lock until
            # the last workload child closes its copy after a parent crash.
            os.close(self.fd)
            self.fd = None


def _close(locks):
    for lock in reversed(locks):
        lock.close()


def _write_once(path, payload):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump(payload, stream, sort_keys=True, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def _read_json(path):
    lock = _Lock(path, create=False)
    try:
        require(os.fstat(lock.fd).st_size <= 1024 * 1024, 'bounded lease metadata')
        with os.fdopen(os.dup(lock.fd), 'r') as stream:
            return json.load(stream)
    finally:
        lock.close()


def _deadline(wait_seconds):
    require(type(wait_seconds) in (int, float) and 0 <= wait_seconds <= 1800, 'finite <=1800-second lease wait')
    return time.monotonic() + wait_seconds


class HeldLease:
    def __init__(self, locks, receipt, release_path=None):
        self._locks = locks
        self.receipt = receipt
        self._owner_pid = os.getpid()
        self._release_path = release_path

    @property
    def pass_fds(self):
        require(self._locks, 'lease already released')
        return tuple(lock.fd for lock in self._locks)

    def check(self):
        require(self._locks and os.getpid() == self._owner_pid, 'live lease owned by this process')
        for lock in self._locks:
            lock.check()

    def close(self):
        require(os.getpid() == self._owner_pid, 'only the acquiring process may release a lease')
        if not self._locks:
            return
        try:
            if self._release_path is not None:
                _write_once(self._release_path, dict(schema='native-resource-release-v1',
                    lease_id=self.receipt['lease_id'], released_at_unix=time.time(), pid=self._owner_pid,
                    meaning='owner closed descriptors; inherited workload descriptors may still hold flock'))
        finally:
            _close(self._locks)
            self._locks = []

    def __enter__(self):
        self.check()
        return self

    def __exit__(self, *args):
        self.close()


class CompileSlots:
    def __init__(self, legacy_lock, directory, slots=2):
        self.legacy_lock = Path(legacy_lock)
        self.directory = canonical_directory(directory)
        require(type(slots) is int and slots in (1, 2), 'one or two compile slots')
        self.slots = slots
        # Never create or replace the frozen exclusive-lock inode.
        check = _Lock(self.legacy_lock, create=False)
        check.close()

    def acquire(self, *, wait_seconds=0, guard=None):
        deadline = _deadline(wait_seconds)
        while True:
            if guard:
                guard()
            locks = []
            try:
                # Reserve a slot before SH so blocked third compilers do not
                # hold SH and delay a waiting legacy EX compiler or cleanup.
                for slot in range(self.slots):
                    candidate = _Lock(self.directory / f'compile-slot-{slot}.lock')
                    if candidate.try_acquire():
                        locks.append(candidate)
                        break
                    candidate.close()
                if locks:
                    legacy = _Lock(self.legacy_lock, create=False)
                    locks.append(legacy)
                    if legacy.try_acquire(fcntl.LOCK_SH):
                        if guard:
                            guard()
                        return HeldLease(locks, dict(schema='native-compile-slot-v1', slot=slot,
                            slot_lock=str(locks[0].path), legacy_lock=str(self.legacy_lock), legacy_mode='shared',
                            acquired_at_unix=time.time(), pid=os.getpid()))
            except BaseException:
                _close(locks)
                raise
            _close(locks)
            if time.monotonic() >= deadline:
                raise LeaseBusy('compile slots or legacy exclusive compile lock occupied')
            time.sleep(min(.1, max(0, deadline - time.monotonic())))


def topology_map(rows):
    require(type(rows) is list and rows, 'complete topology rows')
    mapped = {}
    for row in rows:
        require(type(row) is dict and set(row) == {'cpu', 'package_id', 'core_id'}, 'exact topology fields')
        cpu, package, core = (integer(row[key], key, 0) for key in ('cpu', 'package_id', 'core_id'))
        require(cpu not in mapped, 'duplicate logical CPU')
        mapped[cpu] = (package, core)
    return mapped


class ResourcePool:
    def __init__(self, directory, *, topology, total_memory_bytes, memory_floor_bytes,
                 max_jobs, max_job_cpus, max_job_memory_bytes, core_locks=None, mode_lock=None):
        self.directory = canonical_directory(directory)
        self.topology = topology_map(topology)
        self.total_memory_bytes = integer(total_memory_bytes, 'total memory')
        self.memory_floor_bytes = integer(memory_floor_bytes, 'host memory floor')
        require(self.memory_floor_bytes < self.total_memory_bytes, 'memory floor consumes host')
        self.max_jobs = integer(max_jobs, 'job capacity')
        self.max_job_cpus = integer(max_job_cpus, 'per-job CPU capacity')
        self.max_job_memory_bytes = integer(max_job_memory_bytes, 'per-job memory capacity')
        require(self.max_jobs <= len(set(self.topology.values())) and self.max_job_cpus <= len(set(self.topology.values()))
                and self.max_job_memory_bytes <= self.total_memory_bytes - self.memory_floor_bytes, 'capacity exceeds host')
        all_cores = set(self.topology.values())
        if core_locks is None:
            self.core_locks = {core: self.directory / f'physical-p{core[0]}-c{core[1]}.lock' for core in all_cores}
        else:
            require(type(core_locks) is dict and set(core_locks) == all_cores, 'complete physical-core lock mapping')
            self.core_locks = {core: Path(path) for core, path in core_locks.items()}
        require(len(set(self.core_locks.values())) == len(all_cores), 'distinct physical-core lock paths')
        self.mode_lock = Path(mode_lock) if mode_lock is not None else None
        self.policy = dict(schema='native-resource-pool-v1', topology=sorted(topology, key=lambda row: row['cpu']),
            total_memory_bytes=self.total_memory_bytes, memory_floor_bytes=self.memory_floor_bytes,
            max_jobs=self.max_jobs, max_job_cpus=self.max_job_cpus, max_job_memory_bytes=self.max_job_memory_bytes,
            core_locks=[dict(package_id=core[0], core_id=core[1], path=str(self.core_locks[core])) for core in sorted(all_cores)],
            mode_lock=str(self.mode_lock) if self.mode_lock else None, observation_max_age_seconds=30)

    def _cores(self, cpus, *, job=True):
        require(type(cpus) is list and cpus and all(type(cpu) is int and cpu in self.topology for cpu in cpus)
                and len(set(cpus)) == len(cpus), 'known unique logical CPUs')
        cores = {self.topology[cpu] for cpu in cpus}
        require(len(cores) == len(cpus), 'SMT siblings inside one reservation')
        if job:
            require(len(cpus) <= self.max_job_cpus, 'per-job CPU cap exceeded')
        return cores

    def _policy_check(self):
        path = self.directory / 'pool-policy.json'
        if path.exists():
            require(_read_json(path) == self.policy, 'shared pool policy/topology drift')
        else:
            _write_once(path, self.policy)

    def _active(self):
        active = []
        for path in sorted(self.directory.glob('*.lease.lock')):
            lock = _Lock(path, create=False)
            try:
                if lock.try_acquire():
                    continue  # Historical/crashed record. Retain it untouched.
                record = _read_json(path.with_suffix('.json'))
                require(record['schema'] == 'native-resource-lease-v1'
                        and record['lease_id'] + '.lease.lock' == path.name, 'active lease metadata identity')
                cores = self._cores(record['cpus'])
                require(record['physical_cores'] == [list(core) for core in sorted(cores)]
                        and record['policy'] == self.policy, 'active resource policy/topology drift')
                memory = integer(record['memory_bytes'], 'active memory reservation')
                require(memory <= self.max_job_memory_bytes, 'active memory cap exceeded')
                active.append(record)
            finally:
                lock.close()
        return active

    def _observation(self, observer):
        require(callable(observer), 'fresh complete legacy-job observer required')
        observed = observer()
        require(type(observed) is dict and set(observed) == {'observed_at_unix', 'complete',
                'available_memory_bytes', 'external_reservations'}, 'exact host observation fields')
        stamp = observed['observed_at_unix']
        require(type(stamp) in (int, float) and 0 <= time.time() - stamp <= 30
                and observed['complete'] is True, 'fresh complete legacy-job observation required')
        integer(observed['available_memory_bytes'], 'observed available memory')
        require(type(observed['external_reservations']) is list, 'external reservation list')
        return observed

    def acquire(self, lease_id, cpus, memory_bytes, *, observer, wait_seconds=0, guard=None):
        identifier(lease_id)
        requested = self._cores(cpus)
        integer(memory_bytes, 'requested memory')
        require(memory_bytes <= self.max_job_memory_bytes, 'per-job memory cap exceeded')
        deadline = _deadline(wait_seconds)
        while True:
            if guard:
                guard()
            locks = []
            mutex = None
            try:
                if self.mode_lock:
                    mode = _Lock(self.mode_lock)
                    locks.append(mode)
                    if not mode.try_acquire(fcntl.LOCK_SH):
                        raise LeaseBusy('host fit/exclusive mode occupied')
                mutex = _Lock(self.directory / 'pool.lock')
                if not mutex.try_acquire():
                    raise LeaseBusy('resource admission in progress')
                self._policy_check()
                require(not (self.directory / (lease_id + '.lease.lock')).exists(), 'lease identity already used; history retained')
                active = self._active()
                observed = self._observation(observer)
                occupied, reserved_memory, count = set(), 0, 0
                active_by_id = {record['lease_id']: record for record in active}
                external_ids = set()
                for record in active + observed['external_reservations']:
                    external = record not in active
                    if external:
                        require(type(record) is dict and set(record) == {'id', 'cpus', 'memory_bytes', 'managed_lease_id'},
                                'exact external live reservation fields')
                        require(type(record['id']) is str and record['id'] and record['id'] not in external_ids,
                                'unique external workload identity')
                        external_ids.add(record['id'])
                        managed = record['managed_lease_id']
                        if managed is not None:
                            require(managed in active_by_id and record['cpus'] == active_by_id[managed]['cpus']
                                    and record['memory_bytes'] == active_by_id[managed]['memory_bytes'], 'managed observer/lease mismatch')
                            continue
                    cores = self._cores(record['cpus'], job=not external)
                    require(not cores & occupied, 'observed active physical-core overlap')
                    occupied |= cores
                    reserved_memory += integer(record['memory_bytes'], 'live reserved memory')
                    count += 1
                if count >= self.max_jobs:
                    raise LeaseBusy('whole-job capacity occupied')
                if requested & occupied:
                    raise LeaseBusy('physical core or its SMT sibling occupied')
                if reserved_memory + memory_bytes > self.total_memory_bytes - self.memory_floor_bytes:
                    raise LeaseBusy('aggregate memory reservations exceed host floor')
                if observed['available_memory_bytes'] < memory_bytes + self.memory_floor_bytes:
                    raise LeaseBusy('live available memory below new reservation plus host floor')
                for core in sorted(requested):
                    lock = _Lock(self.core_locks[core])
                    locks.append(lock)
                    if not lock.try_acquire():
                        raise LeaseBusy('physical-core interlock occupied')
                if guard:
                    guard()
                lease_path = self.directory / (lease_id + '.lease.lock')
                holder = _Lock(lease_path, exclusive_create=True)
                locks.append(holder)
                require(holder.try_acquire(), 'fresh lease lock unexpectedly occupied')
                receipt = dict(schema='native-resource-lease-v1', lease_id=lease_id, cpus=cpus,
                    physical_cores=[list(core) for core in sorted(requested)], memory_bytes=memory_bytes,
                    pid=os.getpid(), acquired_at_unix=time.time(), policy=self.policy,
                    admission_observation=observed)
                _write_once(lease_path.with_suffix('.json'), receipt)
                result = HeldLease(locks, receipt, self.directory / (lease_id + '.released.json'))
                locks = []
                return result
            except LeaseBusy:
                if time.monotonic() >= deadline:
                    raise
            finally:
                if mutex:
                    mutex.close()
                _close(locks)
            time.sleep(min(.1, max(0, deadline - time.monotonic())))


@contextmanager
def lease(profile, lease_id, cpus, memory_bytes, *, observer, wait_seconds=0, guard=None):
    """Whole-job convenience adapter: profile is exactly ResourcePool kwargs."""
    with ResourcePool(**profile).acquire(lease_id, cpus, memory_bytes, observer=observer,
                                        wait_seconds=wait_seconds, guard=guard) as held:
        yield held
