"""Pure r49 observed-hardware/static guard checks; no model/tool is run."""
import ast
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from fpga.tools import native_static_v4 as static


def stub_execute(path, pin, out):
    module = parent('mock')
    module.LEASE_FDS = ()
    return module.execute(path, pin, out)


class ResizedBurstTests(unittest.TestCase):
    def test_eight_pairs_match_fresh_sixteen_core_capture_not_prior_hardware(self):
        data, observed = static.descriptor()
        self.assertEqual(data['hardware_sku'], 'Standard_F16as_v7')
        self.assertEqual(observed['logical_cpus'], observed['physical_cores'])
        self.assertEqual(observed['physical_cores'], 16)
        cpus = set()
        for name in data['profiles']:
            selected = static.profile(name)
            self.assertFalse(cpus & set(selected['cpus']))
            cpus.update(selected['cpus'])
            self.assertEqual(selected['memory_bytes'], 4 << 30)
            self.assertEqual(selected['minimum_host_available_bytes'], 8 << 30)
            self.assertEqual(selected['compile_workers'], 2)
            self.assertEqual(selected['model_threads'], 1)
            self.assertEqual(selected['cpu_quota_percent'], 200)
            self.assertEqual(selected['topology'], observed['topology'])
            self.assertEqual(selected['hashes'], observed['hashes'])
            self.assertEqual(selected['toolchain_files_sha256'], observed['toolchain_files_sha256'])
            self.assertEqual(selected['toolchain_symlinks'], observed['toolchain_symlinks'])
            self.assertEqual(selected['python_path'], observed['paths']['python'])
            self.assertEqual(selected['physical_locks'], [f'/home/azureuser/gfn16-worker/.physical-p0-c{cpu}.lock' for cpu in selected['cpus']])
        self.assertEqual(cpus, set(range(16)))
        self.assertEqual(len(observed['toolchain_files_sha256']), 1113)
        self.assertEqual(len(observed['toolchain_symlinks']), 17)
        self.assertGreater(observed['filesystem_available_bytes'], 8 * (4 << 30) + (10 << 30))
        self.assertIn('pending', data['status'])

    def test_prior_profiles_and_sources_remain_immutable(self):
        prior = static.previous()
        self.assertEqual(static.sha(static.HERE / 'native_static_v3.py'), static.PREVIOUS_SHA)
        for name in prior.SELECTIONS:
            self.assertEqual(static.profile(name), prior.profile(name))
        old = static.profile('azure-f32-static01-v1')
        new = static.profile('azure-burst16-static01-v1')
        self.assertEqual(len(old['topology']), 32)
        self.assertEqual(len(new['topology']), 16)
        self.assertEqual(old['hashes'], new['hashes'])
        with self.assertRaisesRegex(ValueError, 'approved resized'):
            static.profile('azure-burst16-static1617-v1')

    def test_mock_live_sixteen_core_guard_accepts_new_profile_rejects_old(self):
        prior = static.static_module()
        real_read = Path.read_text
        def read(path, *args, **kwargs):
            name = str(path)
            if name.startswith('/sys/devices/system/cpu/'):
                cpu = int(name.split('/cpu')[-1].split('/')[0])
                if cpu >= 16:
                    raise FileNotFoundError('CPU absent after authorized resize')
                return '0' if name.endswith('physical_package_id') else str(cpu)
            if name == '/proc/self/cgroup':
                return '0::/test.slice/smoke.service\n'
            if name == '/proc/meminfo':
                return 'MemAvailable: 33554432 kB\n'
            if name.startswith('/sys/fs/cgroup/'):
                if name.endswith('memory.swap.max'):
                    return '0'
                if name.endswith('memory.max'):
                    return str(4 << 30) if 'smoke.service' in name else 'max'
                if name.endswith('cpu.max'):
                    return '200000 100000' if 'smoke.service' in name else 'max 100000'
            return real_read(path, *args, **kwargs)
        new = static.profile('azure-burst16-static01-v1')
        old = static.profile('azure-f32-static01-v1')
        with patch.object(Path, 'read_text', read), \
                patch.object(prior.socket, 'gethostname', return_value=new['host']), \
                patch.object(prior.pwd, 'getpwuid', return_value=types.SimpleNamespace(pw_name='azureuser')), \
                patch.object(prior.os, 'sched_getaffinity', return_value={0, 1}, create=True):
            result = prior.execution_limits(new)
            self.assertEqual(len(result['full_topology']), 16)
            self.assertEqual(result['physical_cores'], [[0, 0], [0, 1]])
            with self.assertRaises(FileNotFoundError):
                prior.execution_limits(old)

    def test_source_keeps_serial_compile_quota_fd_and_runtime_protections(self):
        previous = static.static_module()
        raw = previous.pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes()
        text = static.adapted_source(raw, static.profile('azure-burst16-static01-v1'))
        ast.parse(text)
        self.assertIn("'--build', '-j', '2', '--threads', '1'", text)
        self.assertIn('fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)', text)
        self.assertIn('pass_fds=LEASE_FDS + ((lock.fileno(),)', text)
        self.assertIn('check_scratch_quota(scratch, used, inodes, profile)', text)
        self.assertIn('RUNTIME_CHECK = guard_toolchain(profile)', text)
        self.assertIn('guard_protected(profile); guard(); begin = time.monotonic()', text)
        module = static.parent('azure-burst16-static01-v1')
        self.assertEqual(module.SELF, static.SELF)
        self.assertIs(module.guard_toolchain, static.guard_toolchain)

    def test_burst_deadline_guard_timer_drift_and_expiry_fail_closed(self):
        selected = static.profile('azure-burst16-static01-v1')
        prior = static.previous()
        calls = []
        def timer(argv, **kwargs):
            calls.append(argv)
            return types.SimpleNamespace(returncode=0, stdout=b'active\n' if argv[1] == 'is-active' else b'enabled\n', stderr=b'')
        with patch.object(static, 'previous', return_value=prior), \
                patch.object(static.time, 'time', return_value=0), \
                patch.object(static, 'sha', side_effect=lambda name: selected['burst_protected_sha256'][name]), \
                patch.object(prior.subprocess, 'run', side_effect=timer):
            static.guard_protected(selected)
        self.assertEqual([call[-1] for call in calls], ['gfn16-burst.timer'] * 2)
        self.assertEqual(selected['burst_deadline_epoch'], 1791162766)
        with patch.object(static, 'previous', return_value=prior), patch.object(static.time, 'time', return_value=selected['burst_deadline_epoch'] - 3700):
            with self.assertRaisesRegex(ValueError, 'bounded job'):
                static.guard_protected(selected)
        with patch.object(static, 'previous', return_value=prior), patch.object(static.time, 'time', return_value=0), patch.object(static, 'sha', return_value='0' * 64):
            with self.assertRaisesRegex(ValueError, 'guard/deadline'):
                static.guard_protected(selected)

    def test_additive_policy_retains_shared_lock_fd_and_closed_dependencies(self):
        previous = static.static_module()
        base = previous.load('tools/native_shared_v1.py')
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            manifest = root / 'manifest.json'
            manifest.write_text('{"cpu_profile":"mock"}\n')
            slot = root / 'slot.lock'
            module = types.SimpleNamespace()
            def model(path, pin, out):
                self.assertEqual(len(module.LEASE_FDS), 1)
                with self.assertRaises(BlockingIOError):
                    with base.lock(slot):
                        pass
                return {'guarded': True}
            module.execute = model
            fake = types.SimpleNamespace(sha=previous.sha, execute=stub_execute, load=lambda name: base)
            with patch.object(static, 'static_module', return_value=fake), \
                    patch.object(static, 'profile', return_value={'shared_locks': [str(slot)]}):
                result = static.execute_with_parent(lambda name: module, static.PINS, manifest, previous.sha(manifest), root / 'out')
            self.assertEqual(result, {'guarded': True})
            with base.lock(slot):
                pass
        self.assertEqual(len(static.dependencies()), 17)
        for name, pin in static.dependencies().items():
            self.assertEqual(static.sha(static.HERE.parent / name), pin)


if __name__ == '__main__':
    unittest.main()
