"""Pure threaded shared-launcher checks; no remote or RTL execution."""
import ast
import copy
import unittest

from fpga.tools import native_shared_v2 as shared
from fpga.tools import native_thread_config_v1 as runtime


class SharedThreadedTests(unittest.TestCase):
    def manifest(self, threads=2):
        return dict(build=runtime.configure_build(dict(top='current', parameters=dict(AW=16),
            sv_sources=['tools/design.sv'], cpp_source='rtl/tb/bench.cpp',
            cflags=['-std=c++17', '-Werror=return-type']), threads),
            sources={'tools/design.sv':'1'*64, 'tools/role-oracle.py':'2'*64,
                     'rtl/tb/bench.cpp':'3'*64, shared.SELF:'4'*64,
                     'lint-baseline/unrelated.json':'5'*64,
                     'lint-baseline/exact.json':'6'*64,'lint-baseline/review.json':'7'*64},
            probe=dict(expected_json=runtime.expected_probe(threads)),
            lint_baseline=dict(baseline='lint-baseline/exact.json', review='lint-baseline/review.json'))

    def test_adapter_has_exact_runtime_and_separate_leases(self):
        selected = shared.profile('gcp-c4d-sim01-v1')
        base = shared.load('native_shared_v1.py')
        text = shared.adapted_source((shared.HERE/base.PARENT).read_bytes(), selected)
        ast.parse(text)
        self.assertIn('runtime.validate_build(build', text)
        self.assertIn("'--threads', str(config['runtime_threads'])", text)
        self.assertIn('with compile_slot(lockpath, guard, report, save)', text)
        self.assertIn('pass_fds=inherited_fds(name)', text)
        self.assertIn('user_seconds=', text)
        self.assertIn('system_seconds=', text)
        self.assertIn("report['scratch_quota_admission'] = check_scratch_quota", text)
        self.assertLess(text.index("run('lint', lint)"), text.index("run('build', command)"))
        self.assertNotIn('-Wno', text)
        self.assertNotIn('fcntl.LOCK_EX | fcntl.LOCK_NB', text)
        shared.parent('gcp-c4d-sim01-v1')

    def test_lint_identity_excludes_only_exact_shared_control_and_receipts(self):
        selected = shared.profile('gcp-c4d-sim01-v1')
        manifest = self.manifest()
        result = shared.lint_identity(manifest, selected)
        self.assertEqual(set(result['sources']), {'tools/design.sv','tools/role-oracle.py',
            'rtl/tb/bench.cpp','lint-baseline/unrelated.json'})
        self.assertEqual(result['lint_flags'][-1], '2')
        # Even a path normally exempted as shared control is included if it is
        # actually compiled: directory and filename never hide compiled design.
        manifest['build']['sv_sources'].append(shared.SELF)
        self.assertIn(shared.SELF, shared.lint_identity(manifest, selected)['sources'])

    def test_host_pair_allows_two_threads_but_never_eight(self):
        selected = shared.profile('gcp-c4d-sim01-v1')
        runtime.validate_allocation(selected['runtime_allocation'], 2)
        with self.assertRaisesRegex(ValueError, 'physical cores'):
            runtime.validate_allocation(selected['runtime_allocation'], 8)
        with self.assertRaisesRegex(ValueError, 'approved'):
            shared.profile('gcp-c4d-all-eight-logical-cpus')

    def test_pool_policy_binds_existing_interop_locks_and_memory(self):
        selected = shared.profile('gcp-c4d-sim01-v1')
        total = 63*(1<<30)
        from pathlib import Path
        interop = Path(selected['interop'])
        policy = dict(directory=Path(selected['base'])/'leases-v1',
            topology=[dict(cpu=cpu, package_id=0, core_id=cpu%4) for cpu in range(8)],
            total_memory_bytes=total, memory_floor_bytes=8<<30,max_jobs=2,max_job_cpus=2,
            max_job_memory_bytes=8<<30,core_locks={(0,cpu):interop.parent/f'.physical-core-{cpu}.lock' for cpu in range(4)},mode_lock=interop)
        self.assertEqual(shared.pool_policy(selected, policy, total), policy)
        for key, value in (('max_jobs',4),('max_job_cpus',8),('total_memory_bytes',total+1),('mode_lock',None)):
            changed = copy.deepcopy(policy);changed[key]=value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'policy'):
                shared.pool_policy(selected, changed, total)

    def test_aethia_actual_tools_topology_and_ordinary_vs_eight_profiles(self):
        from pathlib import Path
        ordinary = shared.profile('aethia-sim02-v2')
        full = shared.profile('aethia-aw16-all8-v2')
        four = shared.profile('aethia-aw16-high4-v2')
        self.assertEqual(len(ordinary['topology']), 16)
        self.assertEqual(len(set(map(tuple, ordinary['topology'].values()))), 8)
        self.assertEqual(ordinary['runtime_allocation']['physical_cores'], [[0,0],[0,1]])
        self.assertEqual(ordinary['memory_bytes'], 4 << 30)
        self.assertEqual(full['memory_bytes'], 6 << 30)
        self.assertEqual(full['runtime_allocation']['cpu_quota_percent'], 800)
        self.assertEqual(four['cpus'], [8,10,12,14])
        self.assertEqual(four['runtime_allocation']['cpu_quota_percent'], 400)
        runtime.validate_allocation(four['runtime_allocation'], 4)
        runtime.validate_allocation(full['runtime_allocation'], 8)
        with self.assertRaises(ValueError):
            runtime.validate_allocation(ordinary['runtime_allocation'], 8)
        self.assertEqual(ordinary['hashes']['compiler'],
            'e6718f7e0c7d057c3ff77b550c603da9bc4030e3ede3c053705acce1293dbe4d')
        interop = Path(ordinary['interop'])
        policy = dict(directory=Path(ordinary['base'])/'leases-v1',
            topology=[dict(cpu=cpu,package_id=0,core_id=cpu//2) for cpu in range(16)],
            total_memory_bytes=ordinary['observed_total_memory_bytes'], memory_floor_bytes=4<<30,
            max_jobs=4,max_job_cpus=8,max_job_memory_bytes=6<<30,
            core_locks={(0,core):interop.parent/f'.physical-p0-c{core}.lock' for core in range(8)}, mode_lock=interop)
        self.assertEqual(shared.pool_policy(ordinary, policy, policy['total_memory_bytes']), policy)
        self.assertEqual(shared.pool_policy(full, policy, policy['total_memory_bytes']), policy)
        module = shared.parent('aethia-aw16-all8-v2')
        self.assertEqual(module.PROFILES['aethia']['runtime_allocation']['compile_workers'], 2)
        self.assertEqual(module.SCRATCH_BASE, ordinary['base']+'/scratch-v2')
        self.assertEqual(module.SCRATCH_RESERVATION_BYTES, 4 << 30)
        self.assertEqual(module.SCRATCH_FLOOR_BYTES, 10 << 30)
        self.assertIn('not a measured upper bound', module.SCRATCH_RESERVATION_EVIDENCE)

    def test_quota_guard_is_exact_shared_dependency(self):
        quota = shared.load('native_user_quota_v1.py')
        self.assertEqual(quota.GET_USER_QUOTA, 0x80000700)
        self.assertTrue(callable(quota.validate_headroom))

    def test_gcp_new_profiles_fit_four_physical_cores_and_separate_tool_paths(self):
        left = shared.profile('gcp-c4d-sim01-v2')
        right = shared.profile('gcp-c4d-sim23-v2')
        full = shared.profile('gcp-c4d-aw16-all4-v2')
        self.assertEqual(left['cpus']+right['cpus'], full['cpus'])
        self.assertEqual(len(set(map(tuple, full['topology'].values()))), 4)
        runtime.validate_allocation(left['runtime_allocation'], 2)
        runtime.validate_allocation(full['runtime_allocation'], 4)
        with self.assertRaisesRegex(ValueError,'physical cores'):
            runtime.validate_allocation(full['runtime_allocation'], 8)
        module = shared.parent('gcp-c4d-aw16-all4-v2')
        self.assertEqual(module.COMPILER_PATH, '/usr/bin/x86_64-linux-gnu-g++-15')
        self.assertEqual(module.PYTHON_PATH, '/usr/bin/python3.14')
        self.assertEqual(module.SCRATCH_FLOOR_BYTES, 10<<30)

    def test_full_eight_physical_profile_refuses_active_pair_before_claim(self):
        from pathlib import Path
        import tempfile
        import time
        leases = shared.load('native_resource_leases_v1.py')
        full = shared.profile('aethia-aw16-all8-v2')
        with tempfile.TemporaryDirectory(prefix='aethia-thread-profile-') as tmp:
            root = Path(tmp).resolve()
            pool = leases.ResourcePool(root,
                topology=[dict(cpu=cpu, package_id=0,core_id=cpu//2) for cpu in range(16)],
                total_memory_bytes=full['observed_total_memory_bytes'], memory_floor_bytes=4<<30,
                max_jobs=4,max_job_cpus=8,max_job_memory_bytes=6<<30)
            observer = lambda: dict(observed_at_unix=time.time(),complete=True,
                available_memory_bytes=full['observed_total_memory_bytes'],external_reservations=[])
            with pool.acquire('active-pair',[4,6],4<<30,observer=observer):
                with self.assertRaisesRegex(leases.LeaseBusy,'physical core'):
                    pool.acquire('must-not-claim-all-eight',full['cpus'],6<<30,observer=observer)
                self.assertFalse((root/'must-not-claim-all-eight.lease.lock').exists())
            with pool.acquire('all-eight-now-free',full['cpus'],6<<30,observer=observer) as held:
                self.assertEqual(len(held.receipt['physical_cores']),8)


if __name__ == '__main__':
    unittest.main()
