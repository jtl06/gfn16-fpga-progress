"""Pinned payload/negative staging checks; no remote staging or HDL tools."""
import copy
import importlib.util
from pathlib import Path
import tarfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('reset_stager',
    ROOT / 'tools/stage_rowcompact_reset_probe_snapshot.py')
s = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(s)
PAYLOAD = ROOT / 'results/throughput-20260929/rowcompact-reset-probe-stage-aw16-l64-first8-v1'


class ResetStagerTests(unittest.TestCase):
    def test_fixed_payload_inventory_and_first_eight(self):
        manifest, expected = s.inspect_payload(PAYLOAD)
        self.assertEqual(len(expected), 68)
        self.assertEqual(len(manifest['compiled_source_order']), 18)
        self.assertEqual(manifest['batch'], s.BATCH)
        self.assertEqual({c['age'] for c in s.BATCH}, {0, 6})
        self.assertEqual({c['bit'] for c in s.BATCH}, {0})

    def test_hash_tampering_rejected_before_archive_extraction(self):
        with patch.object(s, 'digest', return_value='0' * 64), self.assertRaisesRegex(RuntimeError, 'manifest SHA'):
            s.inspect_payload(PAYLOAD)

    def test_missing_duplicate_and_link_members_rejected(self):
        _, expected = s.inspect_payload(PAYLOAD)
        with tarfile.open(PAYLOAD / 'source.tar.gz', 'r:gz') as archive:
            members = archive.getmembers()
            for altered in (members[:-1], members[:-1] + [members[0]]):
                with patch.object(archive, 'getmembers', return_value=altered), self.assertRaisesRegex(RuntimeError, 'inventory'):
                    s.validate_members(archive, expected)
            link = copy.copy(members[0]); link.type = tarfile.SYMTYPE; link.linkname = '/tmp/escape'
            with patch.object(archive, 'getmembers', return_value=[link] + members[1:]), self.assertRaisesRegex(RuntimeError, 'regular source'):
                s.validate_members(archive, expected)

    def test_offhost_rejects_before_payload_access_or_writes(self):
        with patch.object(s.socket, 'gethostname', return_value='not-aethia'), \
             patch.object(s, 'inspect_payload', side_effect=AssertionError('must not inspect')), \
             self.assertRaisesRegex(RuntimeError, 'aethia'):
            s.stage_snapshot()

    def test_existing_snapshot_rejected_before_extraction_or_copy(self):
        manifest, expected = s.inspect_payload(PAYLOAD)
        read_exists = Path.exists
        def exists(path):
            return True if path == s.DESTINATION else read_exists(path)
        with patch.object(s.socket, 'gethostname', return_value='aethia'), \
             patch.object(Path, 'resolve', lambda path: path), \
             patch.object(Path, 'is_dir', return_value=True), \
             patch.object(s, 'inspect_payload', return_value=(manifest, expected)), \
             patch.object(Path, 'exists', exists), \
             patch.object(tarfile, 'open', side_effect=AssertionError('must not extract')), \
             self.assertRaisesRegex(RuntimeError, 'fresh snapshot'):
            s.stage_snapshot()


if __name__ == '__main__':
    unittest.main()
