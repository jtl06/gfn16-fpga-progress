"""Authority/race counterexamples for the complete host observer; no HDL."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from fpga.tools import native_resource_observer_v1 as o


PROFILE = Path(o.__file__).resolve().parents[1] / 'cloud/aethia-native-resource-profile-v1.json'


def process(pid, *, ppid=1, uid=1000, executable='/usr/bin/python3.14', argv=None,
            cgroup='/jobs/gfn-field.service', cpus=None, cwd='/lab', start_ticks=123):
    cpus = [0, 2] if cpus is None else cpus
    return dict(pid=pid, ppid=ppid, state='S', start_ticks=start_ticks, zombie=False,
        uid=uid, executable=executable, argv=[] if argv is None else argv,
        cgroup=cgroup, cpus=cpus, cwd=cwd, thread_cpus={str(pid): cpus})


def unit(*, main=100, group='/jobs/gfn-field.service', active='active', sub='running', invocation='a' * 32):
    return dict(namespace='user', unit='gfn-field.service', MainPID=str(main), ControlPID='0',
        InvocationID=invocation, ActiveState=active, SubState=sub, ControlGroup=group,
        MemoryMax=str(4 * o.GIB), MemorySwapMax='0', CPUQuotaPerSecUSec='2s')


class FixtureObserver(o.LegacyObserver):
    def __init__(self, profile, root, rows, units):
        self.rows = rows
        self.units = units
        self.inventory_calls = 0
        self.second_inventory = None
        self.recheck_override = {}
        self.unit_calls = 0
        self.second_units = None
        self.managed_values = []
        self.fd_holders = set()
        self.disk_status = 'admitted_blocks_and_inodes'
        super().__init__(profile, proc_root=root, cgroup_root=root / 'cgroup',
                         unit_reader=self.read_units, current_pid=9)

    def read_units(self):
        self.unit_calls += 1
        return copy.deepcopy(self.second_units if self.unit_calls > 1 and self.second_units is not None else self.units)

    def _inventory(self):
        self.inventory_calls += 1
        return copy.deepcopy(self.second_inventory if self.inventory_calls > 1 and self.second_inventory is not None else self.rows)

    def _topology(self):
        return self.profile['topology']

    def _pid(self, pid):
        return copy.deepcopy(self.recheck_override.get(pid, self.rows[pid]))

    def _managed(self):
        return self.managed_values

    def _holds(self, pid, identity):
        return pid in self.fd_holders

    def _disk(self, *args):
        return dict(status=self.disk_status, admission={'status': self.disk_status}, error='quota test refusal')


class HostObserver(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        boot = self.root / 'sys/kernel/random'
        boot.mkdir(parents=True)
        (boot / 'boot_id').write_text('boot-test-identity\n')
        (self.root / 'meminfo').write_text('MemTotal: 27979504 kB\nMemAvailable: 16000000 kB\n')
        self.profile = json.loads(PROFILE.read_text())
        self.profile['lab_roots'] = [str(self.root / 'lab')]
        self.launcher = self.root / 'lab/snapshot/fpga/tools/native_source_gate_aethia_cpu02_v2.py'
        self.launcher.parent.mkdir(parents=True)
        self.launcher.write_text('# test pinned legacy launcher\n')
        approved = copy.deepcopy(self.profile['legacy_launchers'][2])
        approved['sha256'] = hashlib.sha256(self.launcher.read_bytes()).hexdigest()
        self.profile['legacy_launchers'] = [approved]
        self.rows = {1: process(1, uid=0, executable='/usr/lib/systemd/systemd', cgroup='/', cwd='/', ppid=0),
                     9: process(9, cgroup='/observer.service', cwd=str(self.root / 'lab')),
                     100: process(100, argv=['/usr/bin/python3.14', str(self.launcher)], cwd=str(self.launcher.parents[1])),
                     101: process(101, ppid=100, executable='/usr/libexec/gcc/cc1plus',
                                  argv=['cc1plus', str(self.root / 'lab/build.cpp')], cwd=str(self.root / 'lab'))}
        self.write_group([100, 101])
        self.observer = FixtureObserver(self.profile, self.root, self.rows, [unit()])
        self.hostname = patch.object(o.socket, 'gethostname', return_value='aethia')
        self.hostname.start()

    def tearDown(self):
        self.hostname.stop()
        self.temp.cleanup()

    def write_group(self, members, memory=None, quota='200000 100000', swap='0'):
        group = self.root / 'cgroup/jobs/gfn-field.service'
        group.mkdir(parents=True, exist_ok=True)
        (group / 'cgroup.procs').write_text('\n'.join(map(str, members)))
        (group / 'memory.max').write_text(str(4 * o.GIB if memory is None else memory))
        (group / 'cpu.max').write_text(quota)
        (group / 'memory.swap.max').write_text(swap)

    def test_live_source_pinned_service_descendants_and_exact_identities(self):
        result = self.observer.capture()
        self.assertEqual(result['observation']['external_reservations'][0]['cpus'], [0, 2])
        self.assertEqual(result['observation']['external_reservations'][0]['memory_bytes'], 4 * o.GIB)
        self.assertEqual(result['process_identities']['100']['start_ticks'], 123)
        self.assertEqual(result['workloads'][0]['invocation_id'], 'a' * 32)
        self.assertTrue(result['observation']['complete'])

    def test_exited_released_units_with_no_processes_reserve_nothing(self):
        self.observer.rows = {pid: row for pid, row in self.rows.items() if pid < 100}
        self.observer.units = [unit(main=0, active='active', sub='exited'), unit(main=0, group='', active='failed', sub='failed')]
        result = self.observer.capture()
        self.assertEqual(result['observation']['external_reservations'], [])
        self.assertEqual(sum(item['kind'] == 'terminal_unit_no_reservation' for item in result['workloads']), 2)

    def test_unknown_lab_model_or_compiler_cannot_be_declared_empty(self):
        self.observer.units = []
        with self.assertRaisesRegex(o.leases.LeaseError, 'unknown lab/compiler/model'):
            self.observer.capture()

    def test_unknown_same_user_process_is_not_treated_as_os_daemon(self):
        self.observer.rows[102] = process(102, executable='/tmp/unknown-workload', cwd='/', cgroup='/session.scope')
        with self.assertRaisesRegex(o.leases.LeaseError, 'unknown same-user'):
            self.observer.capture()

    def test_proven_ordinary_os_and_interactive_processes_are_ignored(self):
        self.observer.rows[200] = process(200, uid=0, executable='/usr/sbin/tailscaled', cwd='/', cgroup='/system.slice/tailscaled.service')
        self.observer.rows[201] = process(201, executable='/usr/bin/ncdu', cwd=str(self.root / 'lab'), cgroup='/session.scope')
        result = self.observer.capture()
        self.assertEqual({item['pid'] for item in result['ignored_ordinary']}, {200, 201})

    def test_pid_reuse_invocation_race_and_new_compiler_race_fail_closed(self):
        self.observer.recheck_override[100] = dict(self.rows[100], start_ticks=124)
        with self.assertRaisesRegex(o.leases.LeaseError, 'identity/allocation changed'):
            self.observer.capture()
        self.observer.recheck_override.clear()
        self.observer.unit_calls = 0
        self.observer.second_units = [unit(invocation='b' * 32)]
        with self.assertRaisesRegex(o.leases.LeaseError, 'invocation/state changed'):
            self.observer.capture()
        self.observer.second_units = None
        self.observer.inventory_calls = 0
        self.observer.second_inventory = dict(self.rows, **{})
        self.observer.second_inventory[103] = process(103, executable='/usr/bin/verilator', cwd=str(self.root / 'lab'))
        with self.assertRaisesRegex(o.leases.LeaseError, 'appeared'):
            self.observer.capture()

    def test_cgroup_membership_and_escaped_thread_affinity_fail_closed(self):
        self.write_group([100])
        with self.assertRaisesRegex(o.leases.LeaseError, 'member race'):
            self.observer.capture()
        self.write_group([100, 101])
        self.observer.rows[101]['thread_cpus']['102'] = [0, 1, 2]
        with self.assertRaisesRegex(o.leases.LeaseError, 'escaped'):
            self.observer.capture()

    def test_unknown_launcher_source_drift_and_wrong_physical_slot_are_refused(self):
        self.launcher.write_text('# drifted launcher\n')
        with self.assertRaisesRegex(o.leases.LeaseError, 'source drift'):
            self.observer.capture()
        self.profile['legacy_launchers'][0]['sha256'] = hashlib.sha256(self.launcher.read_bytes()).hexdigest()
        self.observer.rows[100]['cpus'] = [1, 3]
        with self.assertRaisesRegex(o.leases.LeaseError, 'affinity drift'):
            self.observer.capture()

    def test_unknown_or_wrong_cgroup_memory_cpu_swap_caps_are_refused(self):
        for fields in ({'memory': 'max'}, {'memory': 5 * o.GIB}, {'quota': 'max 100000'}, {'quota': '800000 100000'}, {'swap': 'max'}):
            self.write_group([100, 101], **fields)
            with self.subTest(fields=fields), self.assertRaises(o.leases.LeaseError):
                self.observer.capture()
        self.write_group([100, 101])

    def test_orphan_or_unowned_group_member_cannot_hide_behind_known_unit(self):
        self.observer.rows[101]['ppid'] = 1
        with self.assertRaisesRegex(o.leases.LeaseError, 'unowned process'):
            self.observer.capture()

    def test_observer_own_service_does_not_create_false_external_reservation(self):
        self.observer.units.append(unit(main=9, group='/observer.service'))
        result = self.observer.capture()
        self.assertEqual(len(result['observation']['external_reservations']), 1)

    def test_disk_unknown_or_exhausted_blocks_callable_without_faking_empty(self):
        self.observer.disk_status = 'blocked_unknown_user_quota'
        result = self.observer.capture()
        self.assertTrue(result['observation']['complete'])
        self.assertEqual(len(result['observation']['external_reservations']), 1)
        with self.assertRaisesRegex(o.leases.LeaseError, 'quota/headroom admission blocked'):
            self.observer()

    def test_canonical_policy_contains_all_pairs_and_opt8_in_same_pool(self):
        policy = self.observer.pool_policy()
        self.assertEqual(policy['max_jobs'], 4)
        self.assertEqual(policy['max_job_cpus'], 8)
        self.assertEqual(policy['max_job_memory_bytes'], 6 * o.GIB)
        self.assertEqual(len(policy['core_locks']), 8)
        self.assertEqual(policy['directory'], Path(self.profile['pool_directory']))

    def test_own_managed_service_root_and_inherited_child_are_not_legacy_membership_race(self):
        self.observer.rows = {1: self.rows[1], 9: dict(self.rows[9], cgroup='/jobs/gfn-field.service'),
                              101: dict(self.rows[101], ppid=9)}
        self.write_group([9, 101])
        self.observer.units = [unit(main=9)]
        self.observer.managed_values = [dict(device=1, inode=2, record=dict(lease_id='own-job', cpus=[0, 2], memory_bytes=4 * o.GIB))]
        self.observer.fd_holders = {9, 101}
        receipt = self.observer.capture()
        self.assertEqual(receipt['observation']['external_reservations'][0]['managed_lease_id'], 'own-job')
        self.assertEqual(set(receipt['process_identities']), {'9', '101'})

    def test_stale_managed_handle_or_escaped_own_child_fails_closed(self):
        self.observer.managed_values = [dict(device=1, inode=2, record=dict(lease_id='stale-handle', cpus=[0, 2], memory_bytes=4 * o.GIB))]
        with self.assertRaisesRegex(o.leases.LeaseError, 'descriptor holder'):
            self.observer.capture()

    def test_protected_fd_stat_is_not_ownership_and_unknown_opaque_process_is_refused(self):
        folder = self.root / '333/fd'
        folder.mkdir(parents=True)
        (folder / '0').write_text('protected OS descriptor fixture')
        with patch.object(Path, 'stat', side_effect=PermissionError('protected descriptor')):
            self.assertFalse(o.LegacyObserver._holds(self.observer, 333, (1, 2)))
        self.observer.rows[333] = dict(process(333, executable='/usr/bin/zsh', cwd='/', cgroup='/session.scope'), opaque_executable=True)
        with self.assertRaisesRegex(o.leases.LeaseError, 'opaque same-user'):
            self.observer.capture()
        self.observer.fd_holders = {100}
        self.observer.rows[101]['thread_cpus']['101'] = [4, 6]
        with self.assertRaisesRegex(o.leases.LeaseError, 'escaped'):
            self.observer.capture()

    def test_quota_reservations_cover_all_jobs_and_pending_admission(self):
        # Exercise actual accounting with synthetic known kernel receipt,
        # rather than accepting an unexplained empty or per-current-job guard.
        self.observer._scratch_roots = lambda members, rows: set()
        raw = dict(schema='native-own-user-quota-v1', status='known_read_only_kernel_quota',
            observed_at_unix=time.time(), user_blocks=dict(remaining=None), user_inodes=dict(remaining=None),
            global_available_bytes=25 * o.GIB, global_available_inodes=100000)
        details = [dict(kind='legacy_systemd_workload', cgroup='/one', members=[100]),
                   dict(kind='managed_kernel_lease', cgroup='/two', members=[101]),
                   dict(kind='verified_ordinary_user_manager', cgroup='/manager', main_pid=200)]
        with patch.object(o.quota, 'user_quota', return_value=raw):
            result = o.LegacyObserver._disk(self.observer, {}, details, self.rows, [])
        self.assertEqual(result['outstanding_reservation_bytes'], 12 * o.GIB)
        self.assertEqual(result['pending_admission_jobs'], 1)
        raw['global_available_bytes'] = 21 * o.GIB
        with patch.object(o.quota, 'user_quota', return_value=raw):
            result = o.LegacyObserver._disk(self.observer, {}, details, self.rows, [])
        self.assertEqual(result['status'], 'blocked_quota_or_global_headroom')

    def test_proc_stat_parser_handles_spaces_and_parentheses(self):
        fields = ['S', '1'] + ['0'] * 17 + ['123'] + ['0'] * 5
        result = o.read_stat('100 (test (worker)) ' + ' '.join(fields))
        self.assertEqual(result, dict(pid=100, state='S', ppid=1, start_ticks=123))

    def test_confirmed_absent_individual_pid_is_not_a_terminal_job_shortcut(self):
        process_dir = self.root / '444'
        process_dir.mkdir()
        def disappeared(pid):
            process_dir.rmdir()
            raise FileNotFoundError('exited individual process')
        with patch.object(self.observer, '_pid', side_effect=disappeared):
            rows = o.LegacyObserver._inventory(self.observer)
        self.assertEqual(rows, {})
        self.assertEqual(self.observer.vanished_processes, [444])
        process_dir.mkdir()
        with patch.object(self.observer, '_pid', side_effect=FileNotFoundError('only a thread disappeared')):
            with self.assertRaisesRegex(o.leases.LeaseError, 'inventory changed'):
                o.LegacyObserver._inventory(self.observer)


if __name__ == '__main__':
    unittest.main()
