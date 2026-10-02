"""Pure F16 interop/tool policy checks; no Linux tools or HDL executed."""
import ast
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from fpga.tools import native_static_v3 as static


def stub_execute(path, pin, out):
    """Only exercise the parent/FD hook, never compile or execute a model."""
    module = parent('mock-pair')
    module.LEASE_FDS = ()
    return module.execute(path, pin, out)


class StaticF16Tests(unittest.TestCase):
    def test_actual_f16_inventory_paths_and_prior_hosts_preserved(self):
        data, observed, protected = static.descriptor()
        selected = static.profile('azure-f16-static45-v1')
        self.assertEqual(selected['hashes'], observed['hashes'])
        self.assertEqual(selected['cpus'], [4, 5])
        self.assertEqual(selected['memory_bytes'], 8 << 30)
        self.assertEqual(selected['python_path'], observed['paths']['python'])
        self.assertEqual(selected['toolchain_files_sha256'], dict(observed['toolchain_files_sha256'], **data['toolchain_files_sha256']))
        self.assertEqual(selected['toolchain_symlinks'], observed['toolchain_symlinks'])
        self.assertGreaterEqual(len(selected['toolchain_files_sha256']), 1113)
        self.assertEqual(selected['protected_deadline_epoch'], 1791153913)
        self.assertEqual(selected['protected_sha256'], protected['protected_sha256'])
        self.assertEqual(selected['physical_locks'], ['/home/azureuser/gfn16-worker/.fit-physical-p0-c4.lock',
                                                      '/home/azureuser/gfn16-worker/.fit-physical-p0-c5.lock'])
        self.assertEqual(selected['shared_locks'], ['/home/azureuser/gfn16-worker/.fit-slot-azure-b.lock'])
        for name in static.v2().SELECTIONS:
            previous = static.v2().profile(name)
            current = static.profile(name)
            self.assertEqual(current['hashes'], previous['hashes'])
            self.assertEqual(current['cpus'], previous['cpus'])
            self.assertEqual(current['shared_locks'], [])

    def test_all_possible_f16_pairs_disjoint_but_not_claimed(self):
        data, _, _ = static.descriptor()
        cpus = set()
        for name in data['profiles']:
            selected = static.profile(name)
            self.assertFalse(cpus & set(selected['cpus']))
            cpus.update(selected['cpus'])
            self.assertEqual(selected['compile_workers'], 2)
            self.assertEqual(selected['model_threads'], 1)
        self.assertEqual(cpus, set(range(16)))
        self.assertIn('pending', data['status'])
        with self.assertRaisesRegex(ValueError, 'approved observed'):
            static.profile('azure-f16-thread8-v1')

    def test_source_adaptation_has_exact_guard_hooks_outside_timed_run(self):
        previous = static.v2().static_module()
        raw = previous.pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes()
        text = static.adapted_source(raw, static.profile('azure-f16-static45-v1'))
        ast.parse(text)
        self.assertIn('RUNTIME_CHECK = guard_toolchain(profile)', text)
        self.assertIn('runtime_dependency_admission=RUNTIME_CHECK', text)
        self.assertIn("*profile['python_module_paths']", text)
        self.assertIn('guard_protected(profile); guard(); begin = time.monotonic()', text)
        self.assertIn("'--build', '-j', '2', '--threads', '1'", text)
        self.assertIn('fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)', text)
        module = static.parent('azure-f16-static45-v1')
        self.assertEqual(module.SELF, static.SELF)
        self.assertIs(module.guard_toolchain, static.guard_toolchain)

    def test_protected_deadline_timers_and_hashes_fail_closed(self):
        selected = static.profile('azure-f16-static45-v1')
        def expected_hash(name):
            return selected['protected_sha256'][name]
        calls = []
        def timer(argv, **kwargs):
            calls.append(argv)
            return types.SimpleNamespace(returncode=0, stdout=b'active\n' if argv[1] == 'is-active' else b'enabled\n', stderr=b'')
        with patch.object(static.time, 'time', return_value=selected['protected_deadline_drain_epoch'] - 4000), \
                patch.object(static, 'sha', side_effect=expected_hash), patch.object(static.subprocess, 'run', side_effect=timer):
            static.guard_protected(selected)
        self.assertEqual(len(calls), 2)
        with patch.object(static.time, 'time', return_value=selected['protected_deadline_drain_epoch'] - 3700):
            with self.assertRaisesRegex(ValueError, 'finite job'):
                static.guard_protected(selected)
        with patch.object(static.time, 'time', return_value=0), patch.object(static, 'sha', return_value='0' * 64):
            with self.assertRaisesRegex(ValueError, 'state drift'):
                static.guard_protected(selected)
        with patch.object(static.time, 'time', return_value=0), patch.object(static, 'sha', side_effect=expected_hash), \
                patch.object(static.subprocess, 'run', return_value=types.SimpleNamespace(returncode=3, stdout=b'inactive\n', stderr=b'')):
            with self.assertRaisesRegex(ValueError, 'timer'):
                static.guard_protected(selected)

    def test_policy_wrapper_retains_shared_slot_lock_and_inherited_fd(self):
        previous = static.static_module()
        base = previous.load('tools/native_shared_v1.py')
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw).resolve()
            slot = directory / 'slot.lock'
            manifest = directory / 'manifest.json'
            manifest.write_text('{"cpu_profile":"mock-pair"}\n')
            result = {}
            module = types.SimpleNamespace()
            def model(path, pin, out):
                result['fds'] = module.LEASE_FDS
                with self.assertRaises(BlockingIOError):
                    with base.lock(slot):
                        pass
                return {'guarded': True}
            module.execute = model
            fake = types.SimpleNamespace(sha=previous.sha, execute=stub_execute, load=lambda name: base)
            with patch.object(static, 'static_module', return_value=fake), \
                    patch.object(static, 'profile', return_value={'shared_locks': [str(slot)]}):
                receipt = static.execute_with_parent(lambda profile: module, static.PINS, manifest, previous.sha(manifest), directory / 'out')
            self.assertEqual(receipt, {'guarded': True})
            self.assertEqual(len(result['fds']), 1)
            with base.lock(slot):
                pass
        with self.assertRaisesRegex(ValueError, 'closed additive'):
            static.execute_with_parent(lambda name: None, {}, Path('/never-read'), '0' * 64, Path('/never-write'))

    def test_exact_dependencies_include_runtime_and_protected_records(self):
        self.assertEqual(len(static.dependencies()), 14)
        for name, pin in static.dependencies().items():
            self.assertEqual(static.sha(static.HERE.parent / name), pin)


if __name__ == '__main__':
    unittest.main()
