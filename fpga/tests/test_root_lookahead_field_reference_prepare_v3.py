"""Reference packet source/config checks; never run the numeric worker CLI."""
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from fpga.reference import root_lookahead_field_reference_prepare_v3 as prepare
from fpga.reference import root_lookahead_field_host_v3 as host


class ReferencePrepare(unittest.TestCase):
    def tearDown(self):
        host._profile_id = None
        host._last_limits = None

    def test_closed_regular_archive_and_exact_command_identity_both_gcp_pairs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for lane in ('01', '23'):
                profile = 'gcp-c4d-static'+lane+'-v1'
                identity = 'f2-reference-test-'+lane
                packet = root / identity
                result = prepare.prepare(packet, identity, profile)
                config = json.loads((packet/'reference-config.json').read_text())
                self.assertEqual(config['physical_cpus'], [0,1] if lane == '01' else [2,3])
                self.assertEqual(config['containment']['memory_bytes'], 8*(1<<30))
                self.assertEqual(config['containment']['runtime_seconds'], 1800)
                self.assertEqual(config['containment']['swap_bytes'], 0)
                self.assertEqual(config['argv'][:4], ['/usr/bin/python3.14', '-B', '-m',
                                                       'fpga.reference.root_lookahead_field_data_v3'])
                self.assertFalse(result['numeric_reference_executed'])
                self.assertFalse(result['native_RTL_executed'])
                expected = {'reference-config.json': prepare.sha(packet/'reference-config.json'),
                            **{'source/fpga/'+name: pin for name, pin in config['sources'].items()}}
                with tarfile.open(packet/'source.tar.gz', 'r:gz') as archive:
                    members = archive.getmembers()
                    self.assertEqual(len(members), len(expected))
                    self.assertTrue(all(m.isfile() for m in members))
                    self.assertEqual({m.name: hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                                      for m in members}, expected)
                self.assertEqual(result['archive_sha256'], prepare.sha(packet/'source.tar.gz'))
                with self.assertRaisesRegex(ValueError, 'fresh canonical'):
                    prepare.prepare(packet, identity, profile)

    def test_unrecognized_identity_profile_field_and_relative_output_reject(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for identity, profile, field in [('bad/escape', 'gcp-c4d-static23-v1', 0),
                                              ('good-id', 'unrecognized', 0),
                                              ('good-id', 'gcp-c4d-static23-v1', True)]:
                with self.subTest(identity=identity, profile=profile, field=field), self.assertRaises(ValueError):
                    prepare.prepare(root/'packet', identity, profile, field)
            with self.assertRaisesRegex(ValueError, 'fresh canonical'):
                prepare.prepare(Path('relative-output'), 'good-id', 'gcp-c4d-static23-v1')


if __name__ == '__main__':
    unittest.main()
