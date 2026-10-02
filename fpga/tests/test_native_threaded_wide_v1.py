"""Exact fixed-wide role/resource/FD/namespace checks, no native or arithmetic."""
import ast
import copy
import json
from pathlib import Path
import shutil
import tempfile
import types
import unittest
from unittest.mock import patch

from fpga.reference import core27_t5b_thread_wide_pilot_v1 as recipe
from fpga.tools import build_identity_v2 as identity
from fpga.tools import native_threaded_wide_v1 as runner

ROOT = Path(__file__).resolve().parents[1]


class FixedWideThreadPilotTests(unittest.TestCase):
    def test_same61source_role_and_distinct_thread_identity(self):
        original = json.loads((ROOT / recipe.ROLE).read_text())
        sources, builds, keys = [], [], []
        selected = runner.profile(runner.PROFILE_ID)
        for count in (2, 4, 8):
            content, manifest = recipe.recipe(count)
            self.assertEqual(runner.validate_threaded(manifest), count)
            self.assertEqual(manifest['steps'], original['steps'])
            self.assertTrue(all(manifest['sources'][name] == digest for name, digest in original['sources'].items()))
            manifest.update(host=selected['host'], source_root=selected['base'] + '/jobs/matched/source/fpga')
            exact = identity.build_identity(manifest, selected)
            self.assertEqual(exact['identity']['runtime_allocation'], selected['runtime_allocation'])
            self.assertEqual(exact['identity']['compile_workers'], 2)
            self.assertEqual(exact['identity']['model_threads'], count)
            sources.append(content); builds.append(manifest['build']); keys.append(exact['build_key'])
        self.assertEqual(len(sources[0]), 61)
        self.assertEqual(sources[0], sources[1]); self.assertEqual(sources[1], sources[2])
        self.assertEqual(len(set(keys)), 3)
        self.assertEqual(builds[0]['sv_sources'], builds[2]['sv_sources'])

    def test_donor_build_output_source_and_probe_mismatch_rejected(self):
        _, original = recipe.recipe(4)
        for label in ('count1', 'AW', 'flag', 'probe_bool', 'probe', 'source', 'stdout', 'step', 'compiled'):
            manifest = copy.deepcopy(original)
            if label == 'count1':
                manifest['build']['runtime_threads'] = 1
                manifest['build']['cflags'] = ['-DGFN16_RUNTIME_THREADS=1' if flag == '-DGFN16_RUNTIME_THREADS=4' else flag for flag in manifest['build']['cflags']]
                manifest['probe']['expected_json'] = dict(context_threads=1, model_threads=1, expected_threads=1)
            elif label == 'AW': manifest['build']['parameters']['AW'] = 8
            elif label == 'flag': manifest['build']['cflags'].append('-O0')
            elif label == 'probe_bool': manifest['probe']['expected_json']['context_threads'] = True
            elif label == 'probe': manifest['probe']['expected_json']['expected_threads'] = 8
            elif label == 'source': manifest['sources'][manifest['build']['sv_sources'][0]] = '0' * 64
            elif label == 'stdout': manifest['steps'][0]['expected_stdout'] += 'PASS\n'
            elif label == 'step': manifest['steps'].append(copy.deepcopy(manifest['steps'][0]))
            elif label == 'compiled': manifest['build']['cpp_source'] = 'rtl/tb/core27_t5b_soak_v1.cpp'
            with self.subTest(label=label), self.assertRaises(ValueError): runner.validate_threaded(manifest)

    def test_fixed_overlay_keeps_base_runtime_and_all_constituent_locks(self):
        selected = runner.profile(runner.PROFILE_ID)
        prior = runner.base().profile('azure-burst16-static23-v1')
        self.assertEqual(selected['cpus'], list(range(8)))
        self.assertEqual(selected['memory_bytes'], 8 << 30)
        self.assertEqual(selected['cpu_quota_percent'], 800)
        self.assertEqual(selected['runtime_allocation']['compile_workers'], 2)
        self.assertEqual(selected['hardware_profile_sha256'], prior['profile_sha256'])
        for name in ('hashes', 'tool_paths', 'toolchain_files_sha256', 'toolchain_symlinks', 'python_module_paths',
                     'lock', 'interop', 'static_lanes', 'scratch_reservation_bytes', 'scratch_floor_bytes'):
            self.assertEqual(selected[name], prior[name])
        self.assertEqual(len(selected['physical_locks']), 8)
        self.assertEqual(len(selected['constituent_pair_locks']), 4)
        self.assertEqual(len(selected['toolchain_files_sha256']), 1113)
        for name, digest in runner.PINS.items(): self.assertEqual(runner.sha(ROOT / name), digest)
        with self.assertRaises(ValueError): runner.profile('azure-burst16-static23-v1')

    def test_final_actual_executor_namespace_and_poll_guards(self):
        module = runner.parent(runner.PROFILE_ID)
        for name in ('execute', 'load_manifest', 'check_sources', 'tools_for'):
            self.assertIs(getattr(module, name).__globals__, module.__dict__)
        self.assertEqual(module.SELF, runner.SELF)
        self.assertEqual(Path(module.__file__).name, 'native_threaded_wide_v1.py')
        module.LEASE_FDS = (13, 17)
        self.assertEqual(module.execute.__globals__['LEASE_FDS'], (13, 17))
        static = runner.base().source_policy().host.static_module()
        text = runner.adapted_source(static.pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes(), runner.profile(runner.PROFILE_ID))
        tree = ast.parse(text)
        execute = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'execute')
        guard = next(node for node in execute.body if isinstance(node, ast.FunctionDef) and node.name == 'guard')
        self.assertEqual(ast.unparse(guard.body[0]), 'guard_protected(profile)')
        self.assertIn("'-j', '2', '--threads', str(config['runtime_threads'])", text)
        self.assertIn('pass_fds=LEASE_FDS + ((lock.fileno(),)', text)
        self.assertIn('fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)', text)
        self.assertIn('native_child_usage=child.resource_receipt()', text)
        self.assertIn('check_scratch_quota(scratch, used, inodes, profile)', text)

    def test_real_fullsource_load_manifest_wronghost_and_self(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary).resolve(); root = folder / 'source/fpga'; root.mkdir(parents=True)
            content, manifest = recipe.recipe(8)
            for name, digest in runner.PINS.items(): content[name] = (ROOT / name).read_bytes()
            content[runner.SELF] = (ROOT / runner.SELF).read_bytes()
            manifest['sources'] = {name: recipe.digest(raw) for name, raw in content.items()}
            for name, raw in content.items():
                destination = root / name; destination.parent.mkdir(parents=True, exist_ok=True); destination.write_bytes(raw)
            manifest.update(cpu_profile=runner.PROFILE_ID, host='gfn16-azure-sim-f32', source_root=str(root), output_parent=str(folder))
            path = folder / 'manifest.json'; path.write_text(json.dumps(manifest))
            module = runner.parent(runner.PROFILE_ID)
            module.PROFILES = {manifest['host']: dict(runner.profile(runner.PROFILE_ID), base=str(folder))}
            module.__file__ = str(root / runner.SELF)
            with patch.object(module.socket, 'gethostname', return_value=manifest['host']):
                self.assertEqual(module.load_manifest(path, runner.sha(path))[0], manifest)
            with patch.object(module.socket, 'gethostname', return_value='wrong'):
                with self.assertRaisesRegex(ValueError, 'explicit approved native host'): module.load_manifest(path, runner.sha(path))
            module.__file__ = str(root / 'tools/native_threaded_class_v1.py')
            with patch.object(module.socket, 'gethostname', return_value=manifest['host']):
                with self.assertRaisesRegex(ValueError, 'launcher inside pinned snapshot'): module.load_manifest(path, runner.sha(path))

    def test_native_resource_shape_cache_domain_and_ancestor_negatives(self):
        selected = runner.profile(runner.PROFILE_ID)
        real_read, real_glob = Path.read_text, Path.glob
        state = dict(quota='800000 100000', memory=str(8 << 30), cache='0-7', siblings=False, ancestor='max 100000')
        def read(path, *args, **kwargs):
            name = str(path)
            if name == '/sys/devices/system/cpu/online': return '0-15'
            if name.startswith('/sys/devices/system/cpu/cpu'):
                cpu = name.split('/cpu')[-1].split('/')[0]
                if name.endswith('physical_package_id'): return '0'
                if name.endswith('core_id'): return cpu
                if name.endswith('thread_siblings_list'): return cpu + ',16' if state['siblings'] else cpu
                return {'level': '3', 'type': 'Unified', 'id': '0', 'shared_cpu_list': state['cache']}[path.name]
            if name == '/proc/self/cgroup': return '0::/test.slice/wide.service\n'
            if name == '/proc/meminfo': return 'MemAvailable: 33554432 kB\n'
            if name.startswith('/sys/fs/cgroup/'):
                if path.name == 'memory.swap.max': return '0'
                if path.name == 'memory.max': return state['memory'] if 'wide.service' in name else 'max'
                if path.name == 'cpu.max': return state['quota'] if 'wide.service' in name else state['ancestor']
            return real_read(path, *args, **kwargs)
        def glob(path, pattern):
            if str(path).startswith('/sys/devices/system/cpu/cpu') and path.name == 'cache': return [path / 'index3']
            return real_glob(path, pattern)
        with patch.object(Path, 'read_text', read), patch.object(Path, 'glob', glob), \
                patch.object(runner.socket, 'gethostname', return_value=selected['host']), \
                patch.object(runner.os, 'geteuid', return_value=1000), \
                patch.object(runner.pwd, 'getpwuid', return_value=types.SimpleNamespace(pw_name='azureuser')), \
                patch.object(runner.os, 'sched_getaffinity', return_value=set(range(8)), create=True):
            self.assertEqual(runner.execution_limits(selected)['physical_cores'], [[0, n] for n in range(8)])
            for key, wrong in [('quota', '200000 100000'), ('quota', 'max 100000'), ('quota', '0 0'),
                               ('memory', str(4 << 30)), ('cache', '0-15'), ('siblings', True), ('ancestor', '400000 100000')]:
                prior = state[key]; state[key] = wrong
                with self.subTest(key=key, wrong=wrong), self.assertRaises(ValueError): runner.execution_limits(selected)
                state[key] = prior

    def test_actual_outer_lock_frame_includes_constituents_and_inherited_fds(self):
        selected = runner.profile(runner.PROFILE_ID)
        shared = runner.base().source_policy().host.static_module().load('tools/native_shared_v1.py')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); scratch = root / 'scratch'; scratch.mkdir()
            selected.update(base=str(root), scratch_base=str(scratch), interop=str(root / 'mode.lock'), pair_lock=str(root / 'wide.lock'),
                constituent_pair_locks=[str(root / f'pair{n}.lock') for n in range(4)], physical_locks=[str(root / f'core{n}.lock') for n in range(8)])
            _, manifest = recipe.recipe(2); manifest.update(cpu_profile=runner.PROFILE_ID, source_root=str(root), phase='run')
            manifest['sources'].update(runner.PINS)
            path = root / 'manifest.json'; path.write_text(json.dumps(manifest))
            module = types.SimpleNamespace(load_manifest=lambda *args: None, LEASE_FDS=())
            def run(*args):
                self.assertEqual(len(module.LEASE_FDS), 14)
                for name in selected['constituent_pair_locks'] + selected['physical_locks']:
                    with self.assertRaises(BlockingIOError):
                        with shared.lock(Path(name)): pass
                with shared.lock(Path(selected['interop']), True): pass
                with self.assertRaises(BlockingIOError):
                    with shared.lock(Path(selected['interop'])): pass
                return {'all_fds_held': True}
            module.execute = run
            static = types.SimpleNamespace(load=lambda name: shared, check_scratch_quota=lambda *args: None)
            fake = types.SimpleNamespace(source_policy=lambda: types.SimpleNamespace(host=types.SimpleNamespace(static_module=lambda: static)))
            with patch.object(runner, 'profile', return_value=selected), patch.object(runner, 'parent', return_value=module), \
                    patch.object(runner, 'base', return_value=fake), patch.object(runner, 'validate_threaded', return_value=2), \
                    patch.object(runner, 'execution_limits', return_value={}), patch.object(runner, 'guard_protected'), \
                    patch.object(Path, 'cwd', return_value=root):
                self.assertTrue(runner.execute(path, runner.sha(path), root / 'output')['all_fds_held'])
            for name in selected['constituent_pair_locks'] + selected['physical_locks']:
                with shared.lock(Path(name)): pass

    def test_full3715_before_original_drain_boundary(self):
        selected = runner.profile(runner.PROFILE_ID)
        host = runner.base().source_policy().host
        with patch.object(runner, 'base', return_value=types.SimpleNamespace(source_policy=lambda: types.SimpleNamespace(host=host))), \
                patch.object(host, 'guard_protected', return_value='unchanged-protected-checks'):
            for left in (3714, 3715):
                with patch.object(runner.time, 'time', return_value=runner.DEADLINE - runner.DRAIN_LEAD_SECONDS - left):
                    with self.assertRaisesRegex(ValueError, 'full3715'): runner.guard_protected(selected)
            with patch.object(runner.time, 'time', return_value=runner.DEADLINE - runner.DRAIN_LEAD_SECONDS - 3716):
                self.assertEqual(runner.guard_protected(selected), 'unchanged-protected-checks')


if __name__ == '__main__':
    unittest.main()
