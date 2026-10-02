"""Thread identity/cache-key tests; execute only on aethia."""
import json
from pathlib import Path
import socket
import tempfile
import unittest
from reference.build_cache import BuildCache, BuildProduct, BuildSpec
from reference.square_core27_stream_pair_regression import (
    build_configuration, check_probe, validate_configuration,
)


@unittest.skipUnless(socket.gethostname() == 'aethia', 'aethia only')
class RuntimeThreads(unittest.TestCase):
    def config(self, threads=1):
        return build_configuration(1, 16, threads, ['/frozen/core.sv', '/frozen/adapter.cpp'])

    def test_worker_and_memory_bounds_independent(self):
        for threads in (1, 8):
            config = self.config(threads)
            validate_configuration(config)
            self.assertEqual(config['compile_workers'], 2)
            self.assertEqual(config['memory_limit_bytes'], 6 << 30)
            self.assertEqual(config['context_threads'], threads)

    def test_invalid_thread_counts(self):
        for threads in (0, 2, 4, 16, True, 1.0, '8', None):
            with self.subTest(threads=threads), self.assertRaises(ValueError):
                self.config(threads)

    def test_report_and_flag_mismatch_rejected(self):
        for key, value in (('context_threads', 1), ('model_threads', 1),
                           ('compile_workers', 8), ('memory_limit_bytes', 8 << 30)):
            config = self.config(8)
            config[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_configuration(config)
        for old, new in (('8', '1'), ('-DCORE27_STREAM_PAIR_RUNTIME_THREADS=8', '-DCORE27_STREAM_PAIR_RUNTIME_THREADS=1')):
            config = self.config(8)
            config['flags'][config['flags'].index(old)] = new
            with self.assertRaises(ValueError):
                validate_configuration(config)
        config = self.config(8)
        config['flags'] += ['--threads', '1']
        with self.assertRaises(ValueError):
            validate_configuration(config)

    def test_actual_executable_probe_is_required(self):
        correct = dict(context_threads=8, model_threads=8, expected_threads=8)
        check_probe(json.dumps(correct), 8)
        for key in correct:
            changed = dict(correct, **{key: 1})
            with self.assertRaises(ValueError):
                check_probe(json.dumps(changed), 8)
        for payload in ('', '{}', 'not JSON', '{"context_threads":true,"model_threads":1,"expected_threads":1}'):
            with self.assertRaises(ValueError):
                check_probe(payload, 1)

    def test_thread_key_isolation_and_fresh_builder(self):
        with tempfile.TemporaryDirectory(prefix='core27-stream-thread-cache-') as directory:
            root = Path(directory)
            source = root / 'core.sv'
            adapter = root / 'adapter.cpp'
            source.write_text('frozen RTL\n')
            adapter.write_text('explicit context wrapper\n')
            cache = BuildCache(root / 'cache')
            def spec(threads):
                return BuildSpec.capture(sources={'RTL': source, 'adapter': adapter},
                    configuration=build_configuration(1, 16, threads, [source, adapter]),
                    toolchain={}, environment={})
            builds = []
            def builder(target):
                builds.append(str(target))
                executable = target / 'sim'
                executable.write_text('#!/bin/sh\nexit 0\n')
                executable.chmod(0o755)
                return BuildProduct('sim')
            one, eight = spec(1), spec(8)
            self.assertNotEqual(one.key, eight.key)
            self.assertEqual(cache.obtain(one, builder).cache_status, 'built')
            self.assertEqual(cache.obtain(one, builder).cache_status, 'hit')
            self.assertEqual(cache.obtain(eight, builder).cache_status, 'built')
            self.assertEqual(cache.obtain(eight, builder).cache_status, 'hit')
            source.write_text('mutated RTL\n')
            mutant = spec(8)
            self.assertNotEqual(mutant.key, eight.key)
            self.assertEqual(cache.obtain(mutant, builder).cache_status, 'built')
            adapter.write_text('changed context wrapper\n')
            changed_wrapper = spec(8)
            self.assertNotEqual(changed_wrapper.key, mutant.key)
            self.assertEqual(cache.obtain(changed_wrapper, builder).cache_status, 'built')
            self.assertEqual(len(builds), 4)


if __name__ == '__main__':
    unittest.main()
