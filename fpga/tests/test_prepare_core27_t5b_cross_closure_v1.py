"""Isolated closed-package source/metadata checks; no numeric replay."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tarfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'tools/prepare_core27_t5b_cross_closure_v1.py'
SPEC = importlib.util.spec_from_file_location('_cross_closure', PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
OLD = ROOT / 'results/throughput-20260929/soak-t5b-aw16-short-cross-burst16-manifest-v1'
NEW = ROOT / 'results/throughput-20260929/soak-t5b-aw16-short-cross-burst16-manifest-v2'


class CrossClosure(unittest.TestCase):
    def test_original_omission_reproduces_without_GMP_or_HDL(self):
        with self.assertRaises(FileNotFoundError):
            MODULE.validate(OLD / 'cross-runtime-manifest.json', OLD / 'source/fpga')

    def test_isolated_corrected_tree_binding(self):
        result = subprocess.run([sys.executable, '-I', '-B', str(PATH), 'validate', '--manifest',
            str(NEW / 'cross-runtime-manifest.json'), '--source-root', str(NEW / 'source/fpga')],
            cwd=tempfile.gettempdir(), capture_output=True, text=True, check=True)
        value = json.loads(result.stdout)
        self.assertEqual(value['status'], 'PASS_closed_package_metadata_binding_not_numeric_or_HDL')
        self.assertEqual(value['sources'], 59)
        self.assertEqual(len(value['bindings']), 3)
        self.assertFalse(value['GMP_imported'])

    def test_exact_eighteen_additions_all_hash_checked(self):
        manifest = json.loads((NEW / 'cross-runtime-manifest.json').read_text())
        added = manifest['parent_closure_successor']['added_sources']
        self.assertEqual(len(added), 18)
        self.assertTrue(manifest['parent_closure_successor']['validator_unchanged'])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'manifest.json'
            for name in added:
                altered = json.loads(json.dumps(manifest))
                altered['sources'][name] = '0' * 64
                path.write_text(json.dumps(altered))
                with self.assertRaisesRegex(ValueError, 'immutable package closure'):
                    MODULE.validate(path, NEW / 'source/fpga')

    def test_actual_unpacked_native_archive_is_self_contained(self):
        archive = ROOT / 'results/throughput-20260929/soak-t5b-aw16-short-cross-burst16-packet-v2/package.tar.gz'
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with tarfile.open(archive, 'r:gz') as packed:
                packed.extractall(directory, filter='data')
            value = MODULE.validate(directory / 'manifest.json', directory / 'capture/source/fpga')
            self.assertEqual(len(value['bindings']), 3)
            self.assertFalse(value['GMP_imported'])


if __name__ == '__main__':
    unittest.main()
