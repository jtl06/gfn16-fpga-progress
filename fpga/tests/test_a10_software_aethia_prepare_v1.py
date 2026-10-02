"""Small/source-only tests; full-size numeric gate cannot run on the Mac."""
import json
from pathlib import Path
import tempfile
import tarfile
import unittest
from unittest.mock import patch

from fpga.reference import a10_software_aethia_prepare_v1 as prepare
from fpga.tools import run_a10_software_aethia_v1 as run


class A10Preparation(unittest.TestCase):
    def test_original_manifest_unchanged_and_separate_software_profile(self):
        pins = prepare.sources()
        self.assertEqual(len(pins), 16)
        self.assertEqual(pins[run.ORIGINAL_MANIFEST], run.ORIGINAL_SHA)
        profile = prepare.manifest(pins)
        self.assertEqual(profile['cpus'], [0, 2])
        self.assertEqual(profile['memory_max_bytes'], 6 << 30)
        self.assertFalse(profile['HDL_or_native_compiler'])
        self.assertFalse(profile['shared_compile_lock'])

    def test_fresh_exact_archive_and_source_closure(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp) / 'stage'
            receipt = prepare.prepare(stage)
            self.assertEqual(receipt['sources'], prepare.sources())
            self.assertFalse(receipt['deployment_or_dispatch_performed'])
            with tarfile.open(stage / 'source.tar.gz') as archive:
                self.assertTrue(all(m.isfile() for m in archive))
                archive_members = {m.name for m in archive.getmembers()}
            self.assertEqual(archive_members, {'fpga/' + n for n in receipt['sources']})
            self.assertEqual(json.loads((stage / 'approved-manifest.json').read_text()), prepare.manifest(receipt['sources']))
            with self.assertRaisesRegex(ValueError, 'fresh stage'):
                prepare.prepare(stage)

    def test_source_drift_extra_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = root / 'one.py'
            source.write_text('fixture')
            pins = {'one.py': run.sha(source)}
            run.check_sources(root, pins)
            (root / 'extra.py').write_text('fixture')
            with self.assertRaisesRegex(ValueError, 'exact source closure'):
                run.check_sources(root, pins)
            (root / 'extra.py').unlink()
            source.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'source pin'):
                run.check_sources(root, pins)
            source.unlink()
            source.symlink_to(root / 'absent')
            with self.assertRaisesRegex(ValueError, 'source symlink'):
                run.check_sources(root, pins)

    def test_preexecution_host_guard_before_any_path_or_transform(self):
        with patch.object(run.platform, 'system', return_value='Darwin'):
            with self.assertRaisesRegex(ValueError, 'aethia only'):
                run.run(None, None)

    def test_real_limit_contract_rejects_cpu_memory_swap_siblings_and_wrong_pair(self):
        texts = {'/proc/self/cgroup': '0::/test\n', '/sys/fs/cgroup/test/cpu.max': '200000 100000',
                 '/sys/fs/cgroup/test/memory.max': str(6 << 30), '/sys/fs/cgroup/test/memory.swap.max': '0'}
        for cpu, core in [(0, 0), (2, 1)]:
            prefix = f'/sys/devices/system/cpu/cpu{cpu}/topology/'
            texts[prefix + 'physical_package_id'] = '0'
            texts[prefix + 'core_id'] = str(core)
        with patch.object(run.os, 'sched_getaffinity', return_value={0, 2}, create=True), \
             patch.object(Path, 'read_text', lambda path: texts[str(path)]):
            self.assertEqual(run.limits()['physical_cores'], [[0, 0], [0, 1]])
            for name, value in [('/sys/fs/cgroup/test/cpu.max', 'max 100000'),
                                ('/sys/fs/cgroup/test/cpu.max', '300000 100000'),
                                ('/sys/fs/cgroup/test/memory.max', 'max'),
                                ('/sys/fs/cgroup/test/memory.max', str(7 << 30)),
                                ('/sys/fs/cgroup/test/memory.swap.max', '1'),
                                ('/sys/devices/system/cpu/cpu2/topology/core_id', '0')]:
                old = texts[name]
                texts[name] = value
                with self.assertRaises(ValueError):
                    run.limits()
                texts[name] = old
        with patch.object(run.os, 'sched_getaffinity', return_value={4, 6}, create=True):
            with self.assertRaisesRegex(ValueError, 'CPU0/2 affinity'):
                run.limits()


if __name__ == '__main__':
    unittest.main()
