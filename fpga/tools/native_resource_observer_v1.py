"""Fresh complete Linux native-workload observation for the frozen lease API.

Systemd units are discovery hints, not proof of liveness. Actual /proc PID start
identities, descendants, cgroup membership, per-thread affinity and effective
limits determine reservations. Exited units reserve nothing. Unknown lab/model
workloads, opaque relevant processes or changed identities fail closed. No
kill, scheduling, mutation, empty-observer shortcut, or process-name authority.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import time

from fpga.tools import native_resource_leases_v1 as leases
from fpga.tools import native_user_quota_v2 as quota


GIB = 1 << 30


def need(ok, message):
    leases.require(ok, message)


def sha(path):
    path = Path(path)
    need(path.is_file() and not path.is_symlink() and path.stat().st_nlink == 1, 'regular single-link launcher')
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def parse_cpus(value):
    result = []
    for item in value.strip().split(','):
        need(re.fullmatch(r'[0-9]+(?:-[0-9]+)?', item), 'typed CPU list')
        ends = list(map(int, item.split('-')))
        need(len(ends) == 1 or ends[0] <= ends[1], 'ordered CPU range')
        result.extend([ends[0]] if len(ends) == 1 else range(ends[0], ends[1] + 1))
    need(result and len(result) == len(set(result)), 'nonempty unique CPU list')
    return sorted(result)


def read_stat(text):
    # comm may contain spaces and parentheses; the last ')' ends that field.
    pid_text, tail = text.rsplit(')', 1)
    pid = int(pid_text.split('(', 1)[0].strip())
    fields = tail.split()
    need(len(fields) >= 20, 'complete proc stat')
    return dict(pid=pid, state=fields[0], ppid=int(fields[1]), start_ticks=int(fields[19]))


def group_path(value):
    need(value.startswith('/') and str(Path(value)) == value and '..' not in Path(value).parts,
         'canonical unified cgroup path')
    return value


def under(path, root):
    return path == root or path.startswith(root.rstrip('/') + '/')


def live_units(prefixes, ordinary_manager_units=()):
    result = []
    for namespace in ('system', 'user'):
        base = ['/usr/bin/systemctl'] + (['--user'] if namespace == 'user' else [])
        listing = subprocess.run(base + ['list-units', '--all', '--type=service', '--no-pager', '--output=json'],
            capture_output=True, text=True, timeout=5, check=True,
            env=dict(PATH='/usr/bin:/bin', LC_ALL='C', XDG_RUNTIME_DIR='/run/user/' + str(os.getuid())))
        units = json.loads(listing.stdout)
        names = sorted(row['unit'] for row in units if any(row['unit'].startswith(prefix) for prefix in prefixes)
                       or namespace == 'system' and row['unit'] in ordinary_manager_units)
        need(len(names) <= 128, 'bounded managed unit inventory')
        for name in names:
            output = subprocess.run(base + ['show', name, '--no-pager',
                '--property=MainPID,ControlPID,InvocationID,ActiveState,SubState,ControlGroup,MemoryMax,MemorySwapMax,CPUQuotaPerSecUSec,ExecStart'],
                capture_output=True, text=True, timeout=5, check=True,
                env=dict(PATH='/usr/bin:/bin', LC_ALL='C', XDG_RUNTIME_DIR='/run/user/' + str(os.getuid())))
            values = dict(line.split('=', 1) for line in output.stdout.splitlines())
            need(set(values) == {'MainPID', 'ControlPID', 'InvocationID', 'ActiveState', 'SubState', 'ControlGroup',
                 'MemoryMax', 'MemorySwapMax', 'CPUQuotaPerSecUSec', 'ExecStart'}, 'complete systemd unit properties')
            result.append(dict(namespace=namespace, unit=name, **values))
    return result


class LegacyObserver:
    def __init__(self, profile, *, proc_root=Path('/proc'), cgroup_root=Path('/sys/fs/cgroup'),
                 sysfs=Path('/sys/devices/system/cpu'), unit_reader=None, current_pid=None):
        need(profile['schema'] == 'native-resource-host-profile-v1', 'observer host profile schema')
        self.profile = profile
        self.proc = Path(proc_root)
        self.cgroup = Path(cgroup_root)
        self.sysfs = Path(sysfs)
        self.current_pid = os.getpid() if current_pid is None else current_pid
        self.unit_reader = unit_reader or (lambda: live_units(profile['unit_prefixes'],
            profile['ordinary_manager_units'] + profile['ordinary_transport_units']))
        self.last_receipt = None
        self.vanished_processes = []

    def _pid(self, pid):
        path = self.proc / str(pid)
        before = read_stat((path / 'stat').read_text())
        if before['state'] == 'Z':
            return dict(**before, zombie=True)
        status = dict(line.split(':', 1) for line in (path / 'status').read_text().splitlines() if ':' in line)
        command = (path / 'cmdline').read_bytes()
        need(len(command) <= 128 * 1024, 'bounded process command')
        argv = [item.decode('utf-8', 'strict') for item in command.split(b'\0') if item]
        uid = int(status['Uid'].split()[0])
        groups = (path / 'cgroup').read_text().splitlines()
        need(len(groups) == 1 and groups[0].startswith('0::/'), 'unified cgroup inventory')
        cpus = parse_cpus(status['Cpus_allowed_list'])
        opaque = False
        try:
            executable, cwd = os.readlink(path / 'exe'), os.readlink(path / 'cwd')
        except (PermissionError, FileNotFoundError):
            # Foreign OS processes may hide exe/cwd. Their readable cmdline
            # remains checked for lab/compiler/model markers before ignoring.
            opaque = True
            executable, cwd = argv[0] if argv else '', None
        threads = {}
        if uid == self.profile['uid']:
            for item in sorted((path / 'task').iterdir()):
                if item.name.isdigit():
                    thread = dict(line.split(':', 1) for line in (item / 'status').read_text().splitlines() if ':' in line)
                    threads[item.name] = parse_cpus(thread['Cpus_allowed_list'])
        after = read_stat((path / 'stat').read_text())
        need(all(before[key] == after[key] for key in ('pid', 'ppid', 'start_ticks')) and after['state'] != 'Z',
             'process identity changed during observation')
        return dict(**before, zombie=False, uid=uid, argv=argv, executable=executable, cwd=cwd, opaque_executable=opaque,
                    cpus=cpus, thread_cpus=threads, cgroup=group_path(groups[0][3:]))

    def _inventory(self):
        result = {}
        for item in sorted(self.proc.iterdir()):
            if not item.name.isdigit():
                continue
            pid = int(item.name)
            try:
                result[pid] = self._pid(pid)
            except FileNotFoundError:
                if not item.exists():
                    # Confirmed absent, not a timeout or terminal-job claim.
                    # Live unit roots/cgroup members and the second inventory
                    # still must agree; orphan/new workloads remain refusals.
                    self.vanished_processes.append(pid)
                    continue
                raise leases.LeaseError('process inventory changed; take a new complete observation')
        return result

    def _topology(self):
        online = parse_cpus((self.sysfs / 'online').read_text())
        actual = {}
        for cpu in online:
            root = self.sysfs / f'cpu{cpu}/topology'
            actual[str(cpu)] = [int((root / key).read_text()) for key in ('physical_package_id', 'core_id')]
            siblings = parse_cpus((root / 'thread_siblings_list').read_text())
            expected = [int(other) for other, core in self.profile['topology'].items() if core == self.profile['topology'].get(str(cpu))]
            need(siblings == sorted(expected), 'physical-core SMT sibling drift')
        need(actual == self.profile['topology'], 'full host topology drift')
        return actual

    def _excluded(self, rows):
        result = set()
        pid = self.current_pid
        while pid in rows and pid not in result:
            result.add(pid)
            pid = rows[pid]['ppid']
        return result

    def _marker(self, row):
        if row['zombie']:
            return False
        executable = row['executable'].removesuffix(' (deleted)')
        paths = [executable, *(arg for arg in row['argv'] if arg.startswith('/'))]
        marker = any(any(under(value, root) for root in self.profile['lab_roots'])
                     or any(value.startswith(prefix) for prefix in self.profile['scratch_prefixes']) for value in paths)
        compiler = Path(executable).name in {'verilator', 'verilator_bin', 'cc1plus', 'cc1', 'g++', 'g++-15', 'gcc', 'gcc-15', 'make'}
        model = bool(re.match(r'^V[A-Za-z_]', Path(executable).name))
        ordinary = executable in self.profile['ordinary_user_executables']
        lab_cwd = row['cwd'] and any(under(row['cwd'], root) for root in self.profile['lab_roots'])
        module = any(arg.startswith('fpga.') for arg in row['argv'])
        return bool(marker or compiler or model or module or (lab_cwd and not ordinary))

    def _launcher(self, row):
        matches = []
        for argument in row['argv']:
            for approved in self.profile['legacy_launchers']:
                if argument.startswith('/') and argument.endswith('/' + approved['suffix']):
                    need(any(under(argument, root) for root in self.profile['lab_roots']), 'legacy launcher outside approved lab')
                    need(sha(argument) == approved['sha256'], 'legacy launcher source drift')
                    matches.append(approved)
        need(len(matches) <= 1, 'ambiguous legacy launcher')
        return matches[0] if matches else None

    def _limits(self, group, memory_cap, physical_cpus=2):
        root = self.cgroup / group.lstrip('/')
        need(root.is_dir() and root.resolve() == root, 'live canonical workload cgroup')
        memory = (root / 'memory.max').read_text().strip()
        quota = (root / 'cpu.max').read_text().split()
        swap = (root / 'memory.swap.max').read_text().strip()
        need(memory != 'max' and 0 < int(memory) <= memory_cap, 'known finite legacy memory cap')
        need(len(quota) == 2 and quota[0] != 'max' and int(quota[1]) > 0
             and int(quota[0]) == physical_cpus * int(quota[1]) and swap == '0', 'known finite physical-CPU/Swap0 policy')
        return dict(memory_bytes=int(memory), cpu_max=quota, swap_max_bytes=0)

    def _group_members(self, group):
        root = self.cgroup / group.lstrip('/')
        need(root.is_dir(), 'cgroup vanished during observation')
        result = set()
        for directory, _, _ in os.walk(root):
            result.update(int(value) for value in (Path(directory) / 'cgroup.procs').read_text().split())
        return result

    def _managed(self):
        pool = Path(self.profile['pool_directory'])
        result = []
        if not pool.exists():
            return result
        need(pool.resolve() == pool and pool.is_dir(), 'canonical shared pool')
        for path in sorted(pool.glob('*.lease.lock')):
            lock = leases._Lock(path, create=False)
            try:
                if lock.try_acquire():
                    continue
                value = leases._read_json(path.with_suffix('.json'))
                need(value['schema'] == 'native-resource-lease-v1' and value['lease_id'] + '.lease.lock' == path.name,
                     'live managed lease identity')
                result.append(dict(record=value, device=os.fstat(lock.fd).st_dev, inode=os.fstat(lock.fd).st_ino))
            finally:
                lock.close()
        return result

    def _holds(self, pid, descriptor_identity):
        folder = self.proc / str(pid) / 'fd'
        try:
            paths = list(folder.iterdir())
        except PermissionError:
            # This is not an ignore rule: opaque same-user tasks still need
            # independent OS-service proof, or are rejected below.
            return False
        for path in paths:
            try:
                info = path.stat()
            except FileNotFoundError:
                continue  # An unrelated descriptor was closed during traversal.
            except PermissionError:
                return False  # Not evidence of ownership; OS proof or refusal remains mandatory.
            if (info.st_dev, info.st_ino) == descriptor_identity:
                return True
        return False

    def _scratch_roots(self, members, rows):
        result = set()
        for pid in members:
            row = rows[pid]
            for value in [row['executable'], row['cwd'] or '', *row['argv']]:
                for prefix in self.profile['scratch_prefixes']:
                    if value.startswith(prefix):
                        parent = str(Path(prefix).parent)
                        result.add(parent + '/' + value[len(parent) + 1:].split('/')[0])
        return result

    def _disk(self, groups, details, rows, managed):
        roots_used = set()
        reservations = []
        own_lease = any(self.current_pid in item.get('holders', []) for item in details)
        for item in details:
            if item.get('kind') not in ('legacy_systemd_workload', 'managed_kernel_lease'):
                continue
            members = item.get('members', []) + item.get('holders', [])
            roots = self._scratch_roots(set(members), rows)
            need(not roots & roots_used, 'scratch directory shared by independent job reservations')
            roots_used |= roots
            allocated, inodes = 0, 0
            for root_name in roots:
                root = Path(root_name)
                need(root.is_dir() and root.resolve() == root and root.stat().st_uid == self.profile['uid'],
                     'canonical own-UID live scratch directory')
                for directory, _, names in os.walk(root):
                    inodes += 1
                    for name in names:
                        path = Path(directory) / name
                        try:
                            info = path.lstat()
                        except FileNotFoundError:
                            continue  # Compilers atomically replace temporary files.
                        need(stat.S_ISREG(info.st_mode) and info.st_uid == self.profile['uid'] and info.st_nlink == 1,
                             'regular own-UID scratch allocation')
                        allocated += info.st_blocks * 512
                        inodes += 1
            reserved = item.get('launcher', {}).get('scratch_reservation_bytes', self.profile['scratch_reservation_bytes_per_compiler'])
            reservations.append(dict(cgroup=item['cgroup'], scratch_roots=sorted(roots), allocated_bytes=allocated,
                allocated_inodes=inodes,
                outstanding_bytes=max(0, reserved - allocated),
                outstanding_inodes=max(0, self.profile['scratch_reservation_inodes_per_compiler'] - inodes)))
        pending = 0 if own_lease else 1
        outstanding_bytes = sum(item['outstanding_bytes'] for item in reservations) + pending * self.profile['scratch_reservation_bytes_per_compiler']
        outstanding_inodes = sum(item['outstanding_inodes'] for item in reservations) + pending * self.profile['scratch_reservation_inodes_per_compiler']
        raw = quota.user_quota(Path(self.profile['scratch_path']))
        result = dict(quota=raw, reservations=reservations, pending_admission_jobs=pending,
                      outstanding_reservation_bytes=outstanding_bytes, outstanding_reservation_inodes=outstanding_inodes)
        try:
            result['admission'] = quota.parent.admit_receipt(raw, outstanding_bytes,
                floor_bytes=self.profile['scratch_floor_bytes'], outstanding_reservation_inodes=outstanding_inodes,
                floor_inodes=self.profile['scratch_floor_inodes'])
            result['status'] = 'admitted_blocks_and_inodes'
        except quota.parent.QuotaError as error:
            result['status'] = 'blocked_quota_or_global_headroom'
            result['error'] = str(error)
        return result

    def capture(self, *, require_disk=False):
        need(socket.gethostname() == self.profile['host'], 'approved observer hostname')
        started = time.time()
        topology = self._topology()
        boot = (self.proc / 'sys/kernel/random/boot_id').read_text().strip()
        units = self.unit_reader()
        rows = self._inventory()
        excluded = self._excluded(rows)
        live = {pid: row for pid, row in rows.items() if not row['zombie'] and pid not in excluded}
        managed = self._managed()
        groups = {}
        details = []
        covered = set()
        trusted_ordinary = set()
        for item in managed:
            record = item['record']
            holders = [pid for pid, row in rows.items() if not row['zombie'] and row['uid'] == self.profile['uid']
                       and self._holds(pid, (item['device'], item['inode']))]
            need(holders, 'live managed lease has no verified workload descriptor holder')
            group_names = {rows[pid]['cgroup'] for pid in holders}
            need(len(group_names) == 1, 'managed lease spans ambiguous workload cgroups')
            group = group_names.pop()
            members = {pid for pid, row in live.items() if under(row['cgroup'], group)}
            limits = self._limits(group, record['memory_bytes'], len(record['cpus']))
            need(limits['memory_bytes'] == record['memory_bytes'], 'managed lease/cgroup memory mismatch')
            for pid in members | set(holders):
                row = rows[pid]
                need(set(row['cpus']) <= set(record['cpus'])
                     and all(set(value) <= set(record['cpus']) for value in row['thread_cpus'].values()),
                     'managed descendant/thread escaped reserved physical cores')
            need(group not in groups, 'multiple leases in one workload cgroup')
            groups[group] = dict(id='managed:' + record['lease_id'], cpus=record['cpus'],
                memory_bytes=record['memory_bytes'], managed_lease_id=record['lease_id'])
            covered |= members
            details.append(dict(kind='managed_kernel_lease', cgroup=group, holders=holders, members=sorted(members),
                lease_id=record['lease_id'], descriptor_identity=[item['device'], item['inode']]))
        for unit in units:
            group = unit['ControlGroup']
            members = {pid for pid, row in live.items() if group and under(row['cgroup'], group)}
            main = int(unit['MainPID'])
            if unit['namespace'] == 'system' and unit['unit'] in self.profile['ordinary_transport_units']:
                row = rows.get(main)
                executable = Path(self.profile['ordinary_transport_executable'])
                info = executable.stat()
                need(row is not None and not row['zombie'] and row['uid'] == 0 and row['argv'][0] == str(executable)
                     and row['cgroup'] == group and unit['ActiveState'] == 'active' and unit['SubState'] == 'running'
                     and unit['ExecStart'].startswith('{ path=' + str(executable) + ' ;')
                     and info.st_uid == 0 and info.st_mode & 0o022 == 0, 'independently verified root-owned transport daemon')
                sessions = {pid for pid, child in rows.items() if not child['zombie'] and child['ppid'] == main
                    and child.get('argv', [])[:3] == [str(executable), 'be-child', 'ssh']
                    and '--uid=' + str(self.profile['uid']) in child['argv']
                    and '--local-user=' + self.profile['user'] in child['argv']
                    and child['uid'] == self.profile['uid']
                    and child['cgroup'].startswith('/user.slice/user-' + str(self.profile['uid']) + '.slice/session-')}
                trusted_ordinary |= sessions
                for pid, child in rows.items():
                    if child['zombie'] or child.get('executable') not in self.profile['ordinary_transport_clients']:
                        continue
                    ancestor = child['ppid']
                    while ancestor in rows and ancestor not in sessions and ancestor != 0:
                        ancestor = rows[ancestor]['ppid']
                    if ancestor in sessions and child['cgroup'] == rows[ancestor]['cgroup']:
                        trusted_ordinary.add(pid)
                details.append(dict(kind='verified_ordinary_transport', unit=unit['unit'], main_pid=main,
                                    sessions=sorted(sessions), invocation_id=unit['InvocationID']))
                continue  # Native Python/compiler/model descendants are never exempted.
            if unit['namespace'] == 'system' and unit['unit'] in self.profile['ordinary_manager_units']:
                row = rows.get(main)
                executable = Path('/usr/lib/systemd/systemd')
                info = executable.stat()
                need(row is not None and not row['zombie'] and row['uid'] == self.profile['uid']
                     and row['argv'][:2] == [str(executable), '--user']
                     and len(row['argv']) <= 3 and all(re.fullmatch(r'--deserialize=[0-9]+', value) for value in row['argv'][2:])
                     and under(row['cgroup'], group)
                     and unit['ActiveState'] == 'active' and unit['SubState'] == 'running'
                     and unit['ExecStart'].startswith('{ path=' + str(executable) + ' ; argv[]=' + str(executable) + ' --user ;')
                     and info.st_uid == 0 and info.st_mode & 0o022 == 0, 'independently verified ordinary user-manager service')
                trusted_ordinary.add(main)
                # sd-pam is the original non-dumpable systemd manager fork,
                # not an executable name exemption for arbitrary descendants.
                # Require exact init.scope, parent identity and startup cohort.
                for child_pid, child in rows.items():
                    if not child['zombie'] and child['ppid'] == main and child.get('argv') == ['(sd-pam)']:
                        need(child['uid'] == self.profile['uid'] and child['cgroup'] == row['cgroup']
                             and 0 <= child['start_ticks'] - row['start_ticks'] <= 5 * os.sysconf('SC_CLK_TCK'),
                             'verified original user-manager PAM fork identity')
                        trusted_ordinary.add(child_pid)
                details.append(dict(kind='verified_ordinary_user_manager', unit=unit['unit'], main_pid=main,
                                    start_ticks=row['start_ticks'], cgroup=row['cgroup'], invocation_id=unit['InvocationID']))
                continue  # Only this manager PID, never its workload descendants.
            if not members:
                if main in excluded and rows[main].get('cgroup') == group:
                    details.append(dict(kind='observer_unit_no_workload', unit=unit['unit'], namespace=unit['namespace'],
                                        invocation_id=unit['InvocationID']))
                    continue
                need(main == 0 or main not in live, 'systemd main PID missing from declared cgroup')
                need(unit['ActiveState'] not in ('activating', 'deactivating') and unit['SubState'] != 'running',
                     'unit changing state without a complete process inventory')
                details.append(dict(kind='terminal_unit_no_reservation', unit=unit['unit'], namespace=unit['namespace'],
                    state=unit['ActiveState'], substate=unit['SubState'], invocation_id=unit['InvocationID']))
                continue
            group_path(group)
            if group in groups:
                all_members = {pid for pid, row in rows.items() if not row['zombie'] and under(row['cgroup'], group)}
                need(self._group_members(group) == all_members, 'managed systemd/proc/cgroup member race')
                continue
            need(self._group_members(group) == members, 'systemd/proc/cgroup member race')
            need(main in members and unit['ActiveState'] == 'active' and unit['SubState'] == 'running'
                 and re.fullmatch('[0-9a-f]{32}', unit['InvocationID']), 'verified live systemd workload root')
            approved = self._launcher(live[main])
            need(approved is not None, 'unknown managed-unit workload; source contract required')
            limits = self._limits(group, approved['memory_max_bytes'])
            need(unit['MemoryMax'] == str(limits['memory_bytes']) and unit['MemorySwapMax'] == '0'
                 and unit['CPUQuotaPerSecUSec'] == '2s', 'systemd/cgroup policy mismatch')
            cpus = approved['cpus']
            need(live[main]['cpus'] == cpus, 'legacy launcher affinity drift')
            for pid in members:
                row = live[pid]
                need(set(row['cpus']) <= set(cpus) and all(set(value) <= set(cpus) for value in row['thread_cpus'].values()),
                     'workload descendant/thread escaped reserved physical cores')
                ancestor = pid
                while ancestor in live and ancestor != main:
                    ancestor = live[ancestor]['ppid']
                need(ancestor == main, 'unowned process in legacy workload cgroup')
            groups[group] = dict(id=unit['namespace'] + ':' + unit['unit'] + ':' + unit['InvocationID'], cpus=cpus,
                memory_bytes=limits['memory_bytes'], managed_lease_id=None)
            covered |= members
            details.append(dict(kind='legacy_systemd_workload', unit=unit['unit'], namespace=unit['namespace'],
                invocation_id=unit['InvocationID'], main_pid=main, cgroup=group, limits=limits,
                launcher=approved, members=sorted(members)))
        ignored = []
        for pid, row in live.items():
            if pid in covered:
                continue
            need(not row.get('opaque_executable', False) or row['uid'] != self.profile['uid'] or pid in trusted_ordinary,
                 'opaque same-user process without independent OS-service proof')
            if pid in trusted_ordinary:
                ignored.append(dict(pid=pid, executable=row['executable'], uid=row['uid'],
                                    reason='independently verified OS manager/transport process; descendants not exempted'))
                continue
            need(not self._marker(row), 'unknown lab/compiler/model process: PID' + str(pid))
            if pid not in trusted_ordinary:
                need(row['uid'] != self.profile['uid'] or row['executable'] in self.profile['ordinary_user_executables'],
                     'unknown same-user process: PID' + str(pid))
            ignored.append(dict(pid=pid, executable=row['executable'], uid=row['uid'], reason='ordinary OS/interactive process outside workload markers'))
        # Revalidate every covered PID against start identity and allocation;
        # a replaced PID or escaped thread invalidates this entire snapshot.
        identities = {}
        revalidate = covered | {pid for item in details for pid in item.get('holders', [])}
        for pid in sorted(revalidate):
            current = self._pid(pid)
            old = rows[pid]
            keys = ('start_ticks', 'ppid', 'cgroup', 'cpus', 'thread_cpus', 'argv', 'executable', 'cwd')
            need(all(current[key] == old[key] for key in keys), 'workload identity/allocation changed during observation')
            identities[str(pid)] = {key: old[key] for key in keys}
        second_units = self.unit_reader()
        need(second_units == units, 'systemd invocation/state changed during observation')
        second = self._inventory()
        for pid, row in second.items():
            if pid not in rows and pid not in excluded and self._marker(row):
                raise leases.LeaseError('new lab/compiler/model process appeared during observation')
        mem = dict(line.split(':', 1) for line in (self.proc / 'meminfo').read_text().splitlines())
        total = int(mem['MemTotal'].split()[0]) * 1024
        available = int(mem['MemAvailable'].split()[0]) * 1024
        need(time.time() - started <= 5, 'bounded fresh host observation')
        result = dict(observed_at_unix=time.time(), complete=True, available_memory_bytes=available,
                      external_reservations=list(groups.values()))
        receipt = dict(schema='native-resource-observation-v1', status='complete_verified_snapshot',
            host=self.profile['host'], boot_id=boot, started_at_unix=started, observation=result,
            total_memory_bytes=total, topology=topology, units=units, workloads=details,
            process_identities=identities, excluded_observer_ancestors=sorted(excluded), ignored_ordinary=ignored,
            vanished_individual_pids_not_job_terminal_evidence=sorted(set(self.vanished_processes)),
            crosschecks=['systemd/proc/cgroup membership', 'PID start identities', 'descendant/thread affinity',
                        'source-pinned legacy launcher', 'finite CPU/memory/Swap0', 'second unit/process inventory'])
        try:
            receipt['disk'] = self._disk(groups, details, rows, managed)
        except (quota.parent.QuotaError, OSError) as error:
            receipt['disk'] = dict(status='blocked_unknown_user_quota', error=repr(error))
        self.last_receipt = receipt
        if require_disk:
            need(receipt['disk']['status'] == 'admitted_blocks_and_inodes', 'scratch quota/headroom admission blocked: ' + receipt['disk'].get('error', 'unknown'))
        return receipt

    def __call__(self):
        return self.capture(require_disk=True)['observation']

    def validate_disk(self):
        """Guard with all live jobs' unconsumed bytes/inodes, including this job."""
        return self.capture(require_disk=True)['disk']['admission']

    def pool_policy(self):
        receipt = self.capture()
        profile = self.profile
        topology = [dict(cpu=int(cpu), package_id=core[0], core_id=core[1])
                    for cpu, core in sorted(profile['topology'].items(), key=lambda item: int(item[0]))]
        return dict(directory=Path(profile['pool_directory']), topology=topology,
            total_memory_bytes=receipt['total_memory_bytes'], memory_floor_bytes=profile['memory_floor_bytes'],
            max_jobs=profile['max_jobs'], max_job_cpus=profile['max_job_cpus'], max_job_memory_bytes=profile['max_job_memory_bytes'],
            core_locks={(core[0], core[1]): Path(profile['physical_lock_pattern'].format(package_id=core[0], core_id=core[1]))
                        for core in profile['topology'].values()}, mode_lock=Path(profile['mode_lock']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(LegacyObserver(json.loads(args.profile.read_text())).capture(), indent=2))
