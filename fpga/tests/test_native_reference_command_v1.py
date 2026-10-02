"""Pure reference-envelope tests: no numerical reference or worker execution."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from fpga.tools import native_reference_command_v1 as r
from fpga.tools import native_static_v1 as static

ROOT = Path(__file__).resolve().parents[1]


class ReferenceEnvelope(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'artifacts/f2-aw16-f0-reference-static23-v3/reference-config.json').read_text())

    def test_actual_prepared_config_and_profile_bind(self):
        root, work, out = r.validate(self.config)
        self.assertEqual(root.parent, work)
        self.assertEqual(out.parent, work.parent)
        r.profile_binding(self.config, static.profile(self.config['profile']))

    def test_wrong_command_geometry_namespace_or_scope_rejected(self):
        mutations = [('argv', ['sh', '-c', 'true']), ('aw', True), ('field', 3),
                     ('profile', 'unknown'), ('HDL_executed', True), ('promotion_allowed', True),
                     ('expected_files', ['../escape']), ('expected_output_root', '/tmp/output')]
        for key, value in mutations:
            with self.subTest(key=key):
                config = copy.deepcopy(self.config)
                config[key] = value
                with self.assertRaises(ValueError):
                    r.validate(config)

    def test_caps_runtime_guard_and_lock_drift_rejected(self):
        for key, value in [('runtime_seconds', 1801), ('memory_bytes', 4 << 30), ('swap_bytes', 1)]:
            config = copy.deepcopy(self.config)
            config['containment'][key] = value
            with self.assertRaises(ValueError):
                r.validate(config)
        for key, value in [('runtime_sha256', '0' * 64), ('physical_cpus', [0, 4]), ('locks', [])]:
            config = copy.deepcopy(self.config)
            config[key] = value
            with self.assertRaises(ValueError):
                r.profile_binding(config, static.profile(self.config['profile']))

    def test_actual_snapshot_extra_file_and_source_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / 'fpga'
            for name in self.config['sources']:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            r.check_sources(root, self.config['sources'])
            extra = root / 'extra.py'
            extra.write_text('unexpected')
            with self.assertRaises(ValueError):
                r.check_sources(root, self.config['sources'])
            extra.unlink()
            source = root / 'reference/root_lookahead_field_data_v3.py'
            source.write_text('changed')
            with self.assertRaises(ValueError):
                r.check_sources(root, self.config['sources'])

    def test_coordinator_execution_is_refused_before_import_or_subprocess(self):
        with patch.object(r.platform, 'system', return_value='Darwin'), patch.object(r.subprocess, 'Popen') as child:
            with self.assertRaisesRegex(ValueError, 'Linux worker'):
                r.run(Path('/not-used'), '0' * 64)
            child.assert_not_called()


if __name__ == '__main__':
    unittest.main()
