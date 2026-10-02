"""Pure matched-thread pilot checks; no HDL or full-N arithmetic execution."""
import ast
import copy
import unittest

from fpga.reference import core27_current_thread_pilot_v1 as pilot
from fpga.tools import native_static_threaded_v1 as threaded


class MatchedThreadPilotTests(unittest.TestCase):
    def test_complete_reviewed_prefix_identical_source_not_full_segment(self):
        one, a = pilot.recipe(1)
        two, b = pilot.recipe(2)
        self.assertEqual(one, two)
        vector = one[pilot.VECTOR]
        self.assertEqual(sum(line.startswith(b'RUN ') for line in vector.splitlines()), 1)
        self.assertEqual(sum(line.startswith(b'LOAD ') for line in vector.splitlines()), 1)
        self.assertIn(b'BADDIGIT_AT 1000000000 -2 65535\n', vector)
        self.assertEqual(one[pilot.STDOUT], a['steps'][0]['expected_stdout'].encode())
        self.assertEqual(a['steps'], b['steps'])
        self.assertEqual(a['probe']['expected_json']['model_threads'], 1)
        self.assertEqual(b['probe']['expected_json']['model_threads'], 2)
        self.assertEqual(a['build']['cpp_source'], b['build']['cpp_source'])
        self.assertEqual(a['build']['sv_sources'], b['build']['sv_sources'])
        self.assertIn(b'readback=1\nPASS n=65536 squares=1 readbacks=1 aborts=0\n', one[pilot.STDOUT])

    def test_thread_identity_differs_with_identical_source_and_allocation(self):
        _, one = pilot.recipe(1)
        _, two = pilot.recipe(2)
        selected = threaded.profile('gcp-c4d-static01-v1')
        identity = threaded.load('build_identity_v2.py', threaded.IDENTITY_SHA)
        a, b = identity.build_identity(one, selected), identity.build_identity(two, selected)
        self.assertNotEqual(a['build_key'], b['build_key'])
        self.assertEqual(a['identity']['sources'], b['identity']['sources'])
        self.assertEqual(a['identity']['runtime_allocation'], b['identity']['runtime_allocation'])
        self.assertEqual(a['identity']['model_threads'], 1)
        self.assertEqual(b['identity']['context_threads'], 2)

    def test_hook_keeps_guarded_serial_infrastructure_and_compile_concurrency(self):
        static = threaded.load('native_static_v1.py', threaded.STATIC_SHA)
        text = threaded.adapted_source(static.pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes(),
                                       threaded.profile('gcp-c4d-static23-v1'))
        ast.parse(text)
        self.assertIn("'--build', '-j', '2', '--threads', str(config['runtime_threads'])", text)
        self.assertIn('fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)', text)
        self.assertIn('pass_fds=LEASE_FDS + ((lock.fileno(),)', text)
        self.assertIn('check_scratch_quota(scratch, used, inodes, profile)', text)
        self.assertIn('exact_build_identity=identity.build_identity(manifest, profile)', text)
        self.assertNotIn('ResourcePool', text)
        self.assertNotIn('CompileSlots', text)
        module = threaded.parent('aethia-static02-v1')
        self.assertEqual(module.SELF, threaded.SELF)
        self.assertEqual(module.PROFILES['aethia']['cpus'], [0, 2])
        self.assertEqual(len(threaded.dependencies()), 9)

    def test_short_case_and_out_of_pair_threads_refused(self):
        _, manifest = pilot.recipe(2)
        threaded.validate_threaded(manifest)
        runtime = threaded.load('native_thread_config_v1.py', threaded.RUNTIME_SHA)
        for count in (4, 8):
            value = copy.deepcopy(manifest)
            value['build']['runtime_threads'] = count
            value['build']['cflags'][-1] = '-DGFN16_RUNTIME_THREADS=' + str(count)
            value['probe']['expected_json'] = runtime.expected_probe(count)
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

    def test_incomplete_fixture_or_changed_completed_stdout_refused(self):
        content, _ = pilot.recipe(1)
        vector = content[pilot.current.CRTMONT_DONOR + '/segment0.txt']
        stdout = content[pilot.current.CRTMONT_DONOR + '/test-segment0.log']
        for bad_vector, bad_stdout in ((vector.replace(b'65536\n', b'32\n', 1), stdout),
                                      (vector.replace(b'RUN full-random-s0-d0 0', b'RUN full-random-s0-d0 1'), stdout),
                                      (vector, stdout.replace(b'cycles=41663', b'cycles=41664', 1))):
            with self.assertRaises(ValueError):
                pilot.completed_prefix(bad_vector, bad_stdout)


if __name__ == '__main__':
    unittest.main()
