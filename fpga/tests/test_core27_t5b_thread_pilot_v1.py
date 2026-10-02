"""Pure P3 source/record/runner checks; no HDL or full-N arithmetic."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest.mock import patch

from fpga.reference import core27_t5b_thread_pilot_v1 as pilot
from fpga.tools import native_threaded_class_v1 as threaded


def stub_execute(path, pin, out):
    manifest = json.loads(Path(path).read_text())
    validate_serial(manifest)
    module = parent('mock')
    module.LEASE_FDS = ()
    return module.execute(path, pin, out)


class T5bThreadPilotTests(unittest.TestCase):
    def test_two_complete_qualified_records_source_identical_across_threads(self):
        one, a = pilot.recipe(1)
        two, b = pilot.recipe(2)
        self.assertEqual(one, two)
        vector = one[pilot.VECTOR]
        self.assertEqual(sum(line.startswith(b'RUN ') for line in vector.splitlines()), 2)
        self.assertEqual(sum(line.startswith(b'LOAD ') for line in vector.splitlines()), 1)
        self.assertIn(b'BADDIGIT_AT 1000000000 -2 65535\n', vector)
        self.assertIn(b'RUN full-random-s0-d0 0\n', vector)
        self.assertIn(b'RUN full-random-s1-d1 1\n', vector)
        self.assertEqual(pilot.digest(vector), '3869d9c20ef6a9f00c448c973a456a7387a3e97f4d359b4f900ea8f16bfdbfa6')
        self.assertEqual(pilot.digest(one[pilot.STDOUT]), '48b89f454ca5d5a1bcaa23dd4ae6815df55c3f01f062d3b3ecdc60aed174e0ee')
        self.assertEqual(one[pilot.STDOUT], a['steps'][0]['expected_stdout'].encode())
        self.assertEqual(a['steps'], b['steps'])
        self.assertEqual(a['build']['cpp_source'], pilot.adapter.ADAPTER)
        self.assertEqual(a['thread_admission']['core_sha256'], pilot.lineage.CORE_SHA)
        self.assertEqual(a['sources']['rtl/kernel/'+pilot.lineage.TOP+'.sv'], pilot.lineage.CORE_SHA)
        self.assertEqual(b['probe']['expected_json'], dict(context_threads=2, model_threads=2, expected_threads=2))

    def test_identity_changes_only_thread_build_not_source_allocation(self):
        _, one = pilot.recipe(1)
        _, two = pilot.recipe(2)
        identity = threaded.load('build_identity_v2.py', threaded.IDENTITY_SHA)
        selected = threaded.profile('gcp-c4d-static01-v1')
        a, b = identity.build_identity(one, selected), identity.build_identity(two, selected)
        self.assertNotEqual(a['build_key'], b['build_key'])
        self.assertEqual(a['identity']['sources'], b['identity']['sources'])
        self.assertEqual(a['identity']['runtime_allocation'], b['identity']['runtime_allocation'])
        self.assertEqual(a['identity']['model_threads'], 1)
        self.assertEqual(b['identity']['context_threads'], 2)

    def test_incomplete_records_or_altered_cycles_refused(self):
        content, _ = pilot.recipe(1)
        vector, stdout = content[pilot.DONOR_VECTOR], content[pilot.DONOR+'/aw16-normal.log']
        for a, b in ((vector.replace(b'65536\n', b'32\n', 1), stdout),
                     (vector.replace(b'RUN full-random-s1-d1 1', b'RUN full-random-s1-d1 0'), stdout),
                     (vector, stdout.replace(b'cycles=41674', b'cycles=41673', 1)),
                     (vector, stdout.replace(b'cycles=28826', b'cycles=28825', 1)),
                     (vector.replace(b'RUN full-random-s2-d1', b'BROKEN full-random-s2-d1'), stdout)):
            with self.assertRaises(ValueError):
                pilot.completed_prefix(a, b)

    def test_short_or_unallocated_model_thread_configuration_refused(self):
        _, manifest = pilot.recipe(2)
        self.assertEqual(threaded.validate_threaded(manifest), 2)
        for count in (4, 8):
            value = copy.deepcopy(manifest)
            value['build']['runtime_threads'] = count
            value['build']['cflags'][-1] = '-DGFN16_RUNTIME_THREADS='+str(count)
            value['probe']['expected_json'] = pilot.runtime.expected_probe(count)
            with self.assertRaisesRegex(ValueError, 'one/two'):
                threaded.validate_threaded(value)
        value = copy.deepcopy(manifest)
        value['build']['parameters']['AW'] = 5
        with self.assertRaisesRegex(ValueError, 'short'):
            threaded.validate_threaded(value)
        value = copy.deepcopy(manifest)
        value['build']['cflags'].append('-DCORE27_RUNTIME_THREADS=1')
        with self.assertRaisesRegex(ValueError, 'macro'):
            threaded.validate_threaded(value)
        allocation = threaded.profile('gcp-c4d-static01-v1')['runtime_allocation']
        allocation['physical_cores'] = [[0, 0], [0, 0]]
        with self.assertRaisesRegex(ValueError, 'physical'):
            pilot.runtime.validate_allocation(allocation, 2)

    def text(self):
        parent = threaded.source_policy()
        raw = parent.host.static_module().pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes()
        return threaded.adapted_source(raw, threaded.profile('gcp-c4d-static01-v1'))

    def test_class_and_physical_quota_compile_guards_retained(self):
        text = self.text()
        ast.parse(text)
        self.assertEqual(text.count("'-Wno-fatal'"), 2)
        self.assertIn("'--build', '-Wall', '-Wno-fatal', '-j', '2', '--threads', str(config['runtime_threads'])", text)
        self.assertIn('classify(child.returncode', text)
        self.assertIn('fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)', text)
        self.assertIn('pass_fds=LEASE_FDS + ((lock.fileno(),)', text)
        self.assertIn('check_scratch_quota(scratch, used, inodes, profile)', text)
        self.assertIn('guard_protected(profile); guard(); begin =', text)
        self.assertIn('exact_build_identity=identity.build_identity(manifest, profile)', text)
        self.assertNotIn('ResourcePool', text)
        self.assertNotIn('CompileSlots', text)
        for name in ('gcp-c4d-static01-v1', 'aethia-static02-v1', 'azure-f16-static45-v1', 'azure-burst16-static01-v1'):
            module = threaded.parent(name)
            self.assertEqual(module.SELF, threaded.SELF)
            self.assertEqual(module.PROFILES[threaded.profile(name)['host']]['runtime_allocation']['compile_workers'], 2)
        for name, pin in threaded.dependencies().items():
            self.assertEqual(hashlib.sha256((threaded.HERE.parent/name).read_bytes()).hexdigest(), pin)

    def test_nested_execute_preserves_outer_shared_lock_fd_and_thread_validator(self):
        host = threaded.source_policy().host
        real_static = host.static_module()
        base = real_static.load('tools/native_shared_v1.py')
        _, manifest_data = pilot.recipe(2)
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            manifest = root/'manifest.json'
            manifest_data['cpu_profile'] = 'mock'
            manifest.write_text(json.dumps(manifest_data))
            slot = root/'slot.lock'
            module = types.SimpleNamespace()
            def model(path, pin, out):
                self.assertEqual(len(module.LEASE_FDS), 1)
                with self.assertRaises(BlockingIOError):
                    with base.lock(slot):
                        pass
                return {'guarded': True, 'threads': 2}
            module.execute = model
            fake = types.SimpleNamespace(sha=real_static.sha, execute=stub_execute, load=lambda name: base)
            with patch.object(threaded, 'source_policy', return_value=types.SimpleNamespace(host=host)), \
                 patch.object(host, 'static_module', return_value=fake), \
                 patch.object(threaded, 'profile', return_value={'shared_locks': [str(slot)]}), \
                 patch.object(threaded, 'parent', return_value=module):
                result = threaded.execute(manifest, real_static.sha(manifest), root/'out')
            self.assertEqual(result, {'guarded': True, 'threads': 2})
            with base.lock(slot):
                pass

    def test_actual_run_fragment_records_per_child_usage_and_wall(self):
        execute = next(n for n in ast.parse(self.text()).body if isinstance(n, ast.FunctionDef) and n.name == 'execute')
        run = next(n for n in execute.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            report = {'steps': [], 'artifacts': {}}
            calls = []
            def popen(command, **options):
                calls.append((command, options['pass_fds']))
                options['stdout'].write('matched\n')
                return types.SimpleNamespace(returncode=0, poll=lambda: 0, wait=lambda: 0,
                    resource_receipt=lambda: {'schema': 'native-wait4-child-usage-v1', 'user_seconds': 2.5,
                                              'system_seconds': .1, 'peak_rss_kib': 1024})
            def need(ok, why):
                if not ok:
                    raise ValueError(why)
            namespace = dict(guard=lambda: None, guard_protected=lambda _: None, time=time,
                resource=types.SimpleNamespace(RUSAGE_CHILDREN=0, getrusage=lambda _: types.SimpleNamespace(
                    ru_utime=100, ru_stime=50, ru_maxrss=2048)), out=root, root=root, env={},
                toolpaths={'taskset': Path('/mock/taskset')}, profile={'cpus': [0, 1]},
                MeasuredPopen=popen, LEASE_FDS=(101, 102), lock=types.SimpleNamespace(fileno=lambda: 103),
                remember=lambda _: None, report=report, save=lambda: None,
                sha=lambda path: hashlib.sha256(path.read_bytes()).hexdigest(), require=need)
            code = ast.fix_missing_locations(ast.Module(body=[run], type_ignores=[]))
            exec(compile(code, '<source-only-thread-run-fragment>', 'exec'), namespace)
            self.assertEqual(namespace['run']('t5b-cold-warm', ['/mock/exe']), 'matched\n')
            self.assertEqual(calls[0][1], (101, 102))
            step = report['steps'][0]
            self.assertEqual(step['native_child_usage']['user_seconds'], 2.5)
            self.assertEqual(step['native_child_usage']['peak_rss_kib'], 1024)
            self.assertGreaterEqual(step['seconds'], 0)


if __name__ == '__main__':
    unittest.main()
