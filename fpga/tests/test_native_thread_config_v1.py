"""Pure configuration, source-adapter and mocked-context checks; no RTL runs."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from fpga.tools import build_identity_v2 as identity
from fpga.tools import native_harness_adapter_v1 as adapter
from fpga.tools import native_thread_config_v1 as runtime
from fpga.reference import core27_threaded_current_v1 as current

ROOT = Path(__file__).resolve().parents[1]


class ThreadConfiguration(unittest.TestCase):
    def build(self, aw=16, threads=1):
        return runtime.configure_build(dict(top='current_core', parameters=dict(AW=aw),
            sv_sources=['core.sv'], cpp_source=adapter.ADAPTER,
            cflags=['-std=c++17', '-Werror=return-type']), threads)

    def allocation(self, count=2):
        return dict(cpus=list(range(count)), physical_cores=[[0, cpu] for cpu in range(count)],
                    compile_workers=2, cpu_quota_percent=100*count, memory_bytes=8<<30)

    def manifest(self, threads=1):
        return dict(schema='native-source-gate-v1', host='admitted-linux-worker', source_root='/native/source/fpga',
            sources={'core.sv': '1'*64, adapter.ADAPTER: '2'*64, adapter.HEADER: '3'*64},
            build=self.build(threads=threads), probe=dict(expected_json=runtime.expected_probe(threads)))

    def profile(self, count=2):
        return dict(hashes={'compiler': '4'*64, 'verilator': '5'*64}, verilator_dir='/approved/bin',
                    runtime_allocation=self.allocation(count))

    def test_short_batches_and_compiler_workers(self):
        for aw in (5, 8):
            self.assertEqual(self.build(aw=aw)['runtime_threads'], 1)
            for threads in (2, 4, 8):
                with self.assertRaisesRegex(ValueError, 'short'):
                    self.build(aw=aw, threads=threads)
        for threads in runtime.THREADS:
            build = self.build(threads=threads)
            self.assertEqual(runtime.validate_build(build, runtime.expected_probe(threads)), threads)
            flags = runtime.verilator_flags(build)
            self.assertEqual(flags[flags.index('-j')+1], '2')
            self.assertEqual(flags[flags.index('--threads')+1], str(threads))

    def test_mismatched_or_duplicate_context_overrides_fail(self):
        for flag in ('-DGFN16_RUNTIME_THREADS=1', '-UGFN16_RUNTIME_THREADS',
                     '-DCORE27_PREFETCH_R2_RUNTIME_THREADS=8', '-O3 -DGFN16_RUNTIME_THREADS=8'):
            build = self.build(threads=2)
            build['cflags'].append(flag)
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, 'macro'):
                runtime.validate_build(build, runtime.expected_probe(2))
        for value in (0, 3, 16, True, '2', 2.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.build(threads=value)
        with self.assertRaises(ValueError):
            runtime.check_probe('{"context_threads":true,"model_threads":1,"expected_threads":1}', 1)

    def test_physical_cores_and_quota_bound_runtime(self):
        runtime.validate_allocation(self.allocation(4), 4)
        with self.assertRaisesRegex(ValueError, 'physical cores'):
            runtime.validate_allocation(self.allocation(4), 8)
        # GCP eight vCPUs are four physical cores, never eight eligible cores.
        smt = self.allocation(8)
        smt['physical_cores'] = [[0, cpu % 4] for cpu in range(8)]
        with self.assertRaisesRegex(ValueError, 'distinct physical'):
            runtime.validate_allocation(smt, 8)
        too_little = self.allocation(4)
        too_little['cpu_quota_percent'] = 200
        with self.assertRaisesRegex(ValueError, 'quota'):
            runtime.validate_allocation(too_little, 4)

    def test_exact_identity_detached_and_thread_compiler_binding(self):
        one, two = self.manifest(), self.manifest(2)
        key = identity.build_identity(one, self.profile())
        self.assertNotEqual(key['build_key'], identity.build_identity(two, self.profile())['build_key'])
        for role in ('compiler', 'verilator'):
            profile = self.profile()
            profile['hashes'][role] = '0'*64
            self.assertNotEqual(key, identity.build_identity(one, profile))
        changed = copy.deepcopy(one)
        changed['sources'][adapter.HEADER] = '0'*64
        self.assertNotEqual(key, identity.build_identity(changed, self.profile()))
        one['build']['parameters']['AW'] = 8
        self.assertEqual(key['identity']['build']['parameters']['AW'], 16)

    def test_identity_helper_loads_by_pinned_filename_for_shared_packages(self):
        spec = importlib.util.spec_from_file_location('_standalone_identity_test', ROOT/'tools/build_identity_v2.py')
        loaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded)
        self.assertEqual(loaded.build_identity(self.manifest(2), self.profile()),
                         identity.build_identity(self.manifest(2), self.profile()))

    def test_current_recipes_share_source_bytes_and_preserve_frozen_events(self):
        one_content, one = current.recipes(1)
        two_content, two = current.recipes(2)
        self.assertEqual(one_content, two_content)
        for role in ('normal', 'targeted'):
            self.assertEqual(one[role]['steps'], two[role]['steps'])
            self.assertEqual(one[role]['sources'], two[role]['sources'])
            self.assertEqual(one[role]['build']['sv_sources'], two[role]['build']['sv_sources'])
        source = one_content[current.EXPLICIT].decode()
        self.assertIn('gfn16_runtime::configure(context,argc,argv)', source)
        self.assertIn('T5_TARGET_READBACK', source)
        self.assertIn('T5_ERROR_TAIL_NOT_REJECTED', source)
        original = (ROOT/'rtl/tb/core27_prefill_pipe_tail_aw16_v1.cpp').read_text()
        self.assertIn('context.threads(1)', original)
        with self.assertRaisesRegex(ValueError, 'anchor'):
            adapter.explicit_successor(original.replace('context.threads(1)', 'context.threads(2)'))

    def test_crtmont_current_parent_recipe_is_exact_and_thread_independent(self):
        content, one = current.crtmont_recipe(1)
        threaded, two = current.crtmont_recipe(2)
        self.assertEqual(content, threaded)
        self.assertEqual(one['steps'], two['steps'])
        self.assertEqual(one['build']['sv_sources'], two['build']['sv_sources'])
        self.assertTrue(one['build']['top'].endswith('_rootfused_crtmont'))
        self.assertIn('full-random-s0-d0 cycles=41663 ', one['steps'][0]['expected_stdout'])
        self.assertIn('PASS n=65536 squares=5 readbacks=5 aborts=0', one['steps'][0]['expected_stdout'])
        self.assertIn('square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont.cpp',
                      content[adapter.SELECTION].decode())

    def test_stage_is_closed_fresh_and_not_executed(self):
        with tempfile.TemporaryDirectory(prefix='core27-thread-stage-') as tmp:
            output = Path(tmp).resolve()/'stage'
            result = current.prepare(output)
            self.assertFalse(result['native_execution'])
            self.assertEqual(result['thread_counts'], [1, 2])
            manifests = [json.loads((output/name).read_text()) for name in result['manifests']]
            inventory = {str(path.relative_to(output/'source/fpga')): current.digest(path.read_bytes())
                         for path in (output/'source/fpga').rglob('*') if path.is_file()}
            self.assertTrue(all(manifest['sources'] == inventory for manifest in manifests))
            with self.assertRaisesRegex(ValueError, 'fresh'):
                current.prepare(output)


class MockedRuntimeContext(unittest.TestCase):
    @unittest.skipUnless(shutil.which('c++'), 'C++ compiler unavailable')
    def test_shared_implicit_adapter_sets_context_before_model_and_detects_drift(self):
        # Deliberately use no Verilator, generated model, numeric oracle or HDL.
        with tempfile.TemporaryDirectory(prefix='gfn16-runtime-context-') as tmp:
            directory = Path(tmp)
            (directory/'verilated.h').write_text(
                '#pragma once\nclass VerilatedContext { unsigned n=1; public:\n'
                'void threads(unsigned v){n=v;} unsigned threads() const{return n;}\n'
                'void commandArgs(int,char**){} };\n'
                'class Verilated { public: static VerilatedContext* threadContextp(){static VerilatedContext c;return &c;} };\n')
            (directory/'mock.cpp').write_text(
                '#include "verilated.h"\n#include <string>\n'
                'class Vmock { unsigned n;public: explicit Vmock(VerilatedContext* c):n(c->threads()){} unsigned threads()const{return n;} };\n'
                'int main(int argc,char** argv){if(argc==2 && std::string(argv[1])=="drift")Verilated::threadContextp()->threads(1);return 0;}\n')
            for threads in (1, 2, 4, 8):
                output = directory/f'mock-{threads}'
                result = subprocess.run(['c++', '-std=c++17', '-Werror=return-type', '-I'+str(directory),
                    '-I'+str(ROOT/'rtl/tb'), '-DGFN16_RUNTIME_BENCH="'+str(directory/'mock.cpp')+'"',
                    '-DGFN16_RUNTIME_MODEL=Vmock', '-DGFN16_RUNTIME_THREADS='+str(threads),
                    str(ROOT/adapter.ADAPTER), '-o', str(output)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                probe = subprocess.run([str(output), '--runtime-probe'], capture_output=True, text=True)
                self.assertEqual(probe.returncode, 0, probe.stderr)
                self.assertEqual(json.loads(probe.stdout), runtime.expected_probe(threads))
                drift = subprocess.run([str(output), 'drift'], capture_output=True, text=True)
                self.assertEqual(drift.returncode, 0 if threads == 1 else 97)


if __name__ == '__main__':
    unittest.main()
