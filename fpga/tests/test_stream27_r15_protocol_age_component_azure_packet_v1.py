"""Source-only tests for bounded component packaging; no HDL execution."""
import json
import unittest

from fpga.reference import stream27_r15_protocol_age_component_azure_packet_v1 as packet


class AgeComponentPacketTests(unittest.TestCase):
    def test_four_literal_author_manifests_and_source_closure(self):
        for stage, (name, pin) in packet.ROLES.items():
            role = packet.BASE / name
            path = role / 'manifest.json'
            m = json.loads(path.read_bytes())
            self.assertEqual(packet.sha(path.read_bytes()), pin)
            self.assertEqual(len(m['build']['sv_sources']), 3)
            self.assertEqual(m['build']['runtime_threads'], 1)
            self.assertEqual(m['build']['parameters'], {})
            for source, digest in m['sources'].items():
                self.assertEqual(packet.sha((role / 'source/fpga' / source).read_bytes()), digest)

    def test_captured_current_azure_roles_keep_dependency_and_author_expectations(self):
        for stage, (name, _) in packet.ROLES.items():
            role = packet.BASE / name
            m = json.loads((role / 'manifest.json').read_bytes())
            t = json.loads((role / 'azure-packet-v1/global-ticket.json').read_bytes())
            self.assertEqual(t['allowed_hosts'], ['gfn16-azure-f16'])
            self.assertEqual(t['test_role'], m['test_role'])
            self.assertEqual(len(t['packages']), 2)
            self.assertEqual(t['resources'], dict(cores=2, threads=1, ram_gib=8, scratch_gib=4))
            if stage == 'normal':
                self.assertNotIn('after', t)
            else:
                self.assertEqual(t['after'], [packet.NORMAL_ID])
                self.assertEqual(t['on'], 'PASS_expected_contracts')
            for package in t['packages']:
                approved = json.loads((role / 'azure-packet-v1' /
                    ('packet-' + package['profile'].split('static', 1)[1].split('-', 1)[0]) /
                    'manifest.json').read_bytes())
                self.assertEqual(approved['steps'], m['steps'])
                self.assertEqual(approved['build']['sv_sources'], m['build']['sv_sources'])
                self.assertEqual(approved['build']['parameters'], m['build']['parameters'])
                for source, digest in m['sources'].items():
                    self.assertEqual(approved['sources'][source], digest)

    def test_mutants_are_expected_rc1_equivalence_witnesses_not_protection_passes(self):
        for stage in ('bad-allocation', 'bad-stop'):
            m = json.loads((packet.BASE / packet.ROLES[stage][0] / 'manifest.json').read_bytes())
            self.assertEqual(m['steps'][0]['expected_returncode'], 1)
            self.assertEqual(m['steps'][0]['expected_stderr'], 'R15_AGE_NATIVE_EQUIVALENCE\n')
            self.assertFalse(m['scope']['full_COMPUTE'])
            self.assertFalse(m['scope']['clock_area'])
            self.assertFalse(m['scope']['promotion_allowed'])


if __name__ == '__main__':
    unittest.main()
