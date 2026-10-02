"""Pure observed-host path/configuration checks; no native tool execution."""
import ast
import unittest

from fpga.tools import native_static_v2 as static


class StaticHostPathTests(unittest.TestCase):
    def test_f32_exact_capture_not_reused_gcp_toolchain(self):
        data, receipt = static.descriptor()
        self.assertEqual(receipt['status'], 'PASS_native_tool_setup_not_RTL_admission')
        self.assertFalse(receipt['queue_admitted'])
        selected = static.profile('azure-f32-static01-v1')
        self.assertEqual(selected['host'], 'gfn16-azure-sim-f32')
        self.assertEqual(selected['hashes'], receipt['hashes'])
        self.assertEqual(selected['compiler_path'], '/usr/bin/x86_64-linux-gnu-g++-13')
        self.assertEqual(selected['python_path'], '/usr/bin/python3.12')
        self.assertEqual(selected['make_path'], '/usr/bin/make')
        self.assertEqual(selected['taskset_path'], '/usr/bin/taskset')
        gcp = static.profile('gcp-c4d-static01-v1')
        self.assertNotEqual(gcp['hashes']['compiler'], selected['hashes']['compiler'])
        self.assertNotEqual(gcp['hashes']['verilator_bin'], selected['hashes']['verilator_bin'])
        self.assertEqual(selected['tool_paths']['compiler_alias'], '/usr/bin/g++')

    def test_eight_serial_pairs_bound_actual_topology_memory_and_disk(self):
        data, receipt = static.descriptor()
        cores = set()
        for name in data['profiles']:
            selected = static.profile(name)
            pair = {tuple(selected['topology'][str(cpu)]) for cpu in selected['cpus']}
            self.assertFalse(cores & pair)
            self.assertEqual(len(pair), 2)
            cores.update(pair)
            self.assertEqual(selected['memory_bytes'], 4 << 30)
            self.assertEqual(selected['minimum_host_available_bytes'], 8 << 30)
            self.assertEqual(selected['model_threads'], 1)
            self.assertEqual(selected['compile_workers'], 2)
            self.assertEqual(selected['static_lanes'], 8)
            self.assertEqual(selected['scratch_floor_bytes'], 10 << 30)
            self.assertEqual(selected['scratch_reservation_bytes'], 4 << 30)
            self.assertEqual(selected['physical_locks'], [f'/home/azureuser/gfn16-worker/.physical-p0-c{cpu}.lock'
                                                         for cpu in selected['cpus']])
        self.assertEqual(cores, {(0, cpu) for cpu in range(16)})
        self.assertEqual(len(receipt['topology']), 32)
        self.assertLess(8 * (4 << 30) + (8 << 30), data['observed_total_memory_bytes'])
        self.assertGreater(receipt['scratch']['free_bytes'], 8 * (4 << 30) + (10 << 30))
        for unknown in ('azure-f32-threaded8-v1', 'azure-f16-static01-v1', 'azure-f32-static1617-v1'):
            with self.assertRaisesRegex(ValueError, 'approved observed'):
                static.profile(unknown)

    def test_path_flexible_source_preserves_compile_probe_locks_and_quota(self):
        ancestor = static.static_module()
        raw = ancestor.pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes()
        for name in static.SELECTIONS:
            selected = static.profile(name)
            source = static.adapted_source(raw, selected)
            ast.parse(source)
            self.assertIn("compiler=Path(profile['compiler_path'])", source)
            self.assertIn("python=Path(profile['python_path'])", source)
            self.assertIn("make=Path(profile['make_path'])", source)
            self.assertIn("taskset=Path(profile['taskset_path'])", source)
            self.assertIn("CXX=profile['compiler_path']", source)
            self.assertIn("host_memory_floor_bytes=profile['minimum_host_available_bytes']", source)
            self.assertIn("'--build', '-j', '2', '--threads', '1'", source)
            self.assertIn('fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)', source)
            self.assertIn('check_scratch_quota(scratch, used, inodes, profile)', source)
            self.assertIn('pass_fds=LEASE_FDS + ((lock.fileno(),)', source)
            self.assertNotIn('CompileSlots', source)
            self.assertNotIn('ResourcePool', source)
            module = static.parent(name)
            self.assertEqual(module.SELF, static.SELF)

    def test_dependency_export_closes_actual_profile_and_capture(self):
        dependencies = static.dependencies()
        self.assertEqual(len(dependencies), 9)
        self.assertEqual(dependencies[static.F32_PROFILE], static.F32_PROFILE_SHA)
        self.assertEqual(dependencies[static.F32_RECEIPT], static.F32_RECEIPT_SHA)
        self.assertEqual(dependencies['tools/native_static_v1.py'], static.STATIC_SHA)
        for name, pin in dependencies.items():
            self.assertEqual(static.sha(static.HERE.parent / name), pin)


if __name__ == '__main__':
    unittest.main()
