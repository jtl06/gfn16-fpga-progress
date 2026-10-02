"""Regression for actual generated-parent callable usage, no HDL/model/math."""
import json
from pathlib import Path
import platform
import sys
import tempfile
import unittest
from unittest.mock import patch

from fpga.reference import core27_t5b_thread_wide_pilot_v1 as recipe
from fpga.tools import native_threaded_wide_v1 as preserved
from fpga.tools import native_threaded_wide_v2 as runner


class WideCallableBindingTests(unittest.TestCase):
    def test_preserved_failure_and_final_class_callable_real_harmless_child(self):
        broken = preserved.parent(preserved.PROFILE_ID)
        self.assertFalse(callable(broken.MeasuredPopen))
        with self.assertRaises(TypeError): broken.MeasuredPopen([])
        module = runner.parent(runner.PROFILE_ID)
        self.assertTrue(callable(module.MeasuredPopen))
        self.assertIsInstance(module.MeasuredPopen, type)
        self.assertIs(module.execute.__globals__['MeasuredPopen'], module.MeasuredPopen)
        # A bounded standard-library Python child exercises the actual class
        # selected by the generated executor. It performs no arithmetic/model.
        child = module.MeasuredPopen([sys.executable, '-B', '-c', 'pass'])
        self.assertEqual(child.wait(timeout=10), 0)
        self.assertIsNotNone(child.native_usage)
        if platform.system() == 'Linux':
            receipt = child.resource_receipt()
            self.assertEqual(receipt['schema'], 'native-wait4-child-usage-v1')
            self.assertEqual(receipt['pid'], child.pid)
            self.assertEqual(receipt['returncode'], 0)
            self.assertGreater(receipt['peak_rss_kib'], 0)
        else:
            with self.assertRaisesRegex(ValueError, 'Linux child resource'): child.resource_receipt()

    def test_new_self_namespace_and_only_binding_identity_delta(self):
        selected = runner.profile(runner.PROFILE_ID)
        self.assertEqual(selected, preserved.profile(preserved.PROFILE_ID))
        self.assertEqual(runner.sha(runner.HERE / 'native_threaded_wide_v1.py'), runner.PRESERVED_WIDE_V1_SHA)
        self.assertEqual(runner.PINS, dict(preserved.PINS, **{preserved.SELF: runner.PRESERVED_WIDE_V1_SHA}))
        module = runner.parent(runner.PROFILE_ID)
        for name in ('execute', 'load_manifest', 'check_sources', 'tools_for'):
            self.assertIs(getattr(module, name).__globals__, module.__dict__)
        self.assertEqual(module.SELF, runner.SELF)
        self.assertEqual(Path(module.__file__).name, 'native_threaded_wide_v2.py')
        module.LEASE_FDS = (11, 23)
        self.assertEqual(module.execute.__globals__['LEASE_FDS'], (11, 23))
        static = runner.base().source_policy().host.static_module()
        raw = static.pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes()
        old, new = preserved.adapted_source(raw, selected), runner.adapted_source(raw, selected)
        self.assertEqual(new.replace(runner.SELF, preserved.SELF), old)
        for count in (2, 4, 8):
            _, manifest = recipe.recipe(count)
            self.assertEqual(runner.validate_threaded(manifest), count)

    def test_real_unpacked_closedsource_loader_with_own_v2_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary).resolve(); root = folder / 'source/fpga'; root.mkdir(parents=True)
            content, manifest = recipe.recipe(8)
            for name in (*runner.PINS, runner.SELF): content[name] = (recipe.ROOT / name).read_bytes()
            for name, raw in content.items():
                path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
            manifest['sources'] = {name: recipe.digest(raw) for name, raw in content.items()}
            manifest.update(host=runner.profile(runner.PROFILE_ID)['host'], cpu_profile=runner.PROFILE_ID,
                source_root=str(root), output_parent=str(folder))
            path = folder / 'manifest.json'; path.write_text(json.dumps(manifest))
            module = runner.parent(runner.PROFILE_ID)
            module.__file__ = str(root / runner.SELF)
            module.PROFILES = {manifest['host']: dict(runner.profile(runner.PROFILE_ID), base=str(folder))}
            with patch.object(module.socket, 'gethostname', return_value=manifest['host']):
                self.assertEqual(module.load_manifest(path, runner.sha(path))[0], manifest)
            module.__file__ = str(root / preserved.SELF)
            with patch.object(module.socket, 'gethostname', return_value=manifest['host']):
                with self.assertRaisesRegex(ValueError, 'launcher inside pinned snapshot'): module.load_manifest(path, runner.sha(path))


if __name__ == '__main__':
    unittest.main()
