"""Current operator refresh retains the unexecuted application body exactly."""
import json
import unittest
from pathlib import Path

from fpga.reference import stream27_r15_application_v4_operator_refresh_packet_v2 as refresh
from fpga.reference import stream27_r15_protocol_age_azure_packet_v2 as age
from fpga.tools import global_queue_v1 as queue


class CurrentOperatorPacketTests(unittest.TestCase):
    def test_app_logical_identity_and_recovery_fields_preserved(self):
        for stage, pin in refresh.INPUT_PINS.items():
            role = refresh.recovery.own.BASE / 'trackS-r15-shell-application-native-v4' / (stage + '-normal')
            old_path = role / 'quota-retry-packet-v1/global-ticket.json'
            before = json.loads(old_path.read_bytes())
            current = json.loads((role / 'operator-refresh-packet-v2/global-ticket.json').read_bytes())
            self.assertEqual(refresh.sha(old_path.read_bytes()), pin)
            self.assertEqual(queue.expected_identity(before), queue.expected_identity(current))
            for field in ('id', 'created', 'infra_retry_of', 'supersedes_unstarted', 'after', 'on', 'resources'):
                self.assertEqual(current.get(field), before.get(field))
            self.assertFalse({p['worker_id'] for p in before['packages']} &
                             {p['worker_id'] for p in current['packages']})
            for package in current['packages']:
                approved = json.loads((Path(package['archive']).parent / 'manifest.json').read_bytes())
                original = json.loads((role / 'manifest.json').read_bytes())
                self.assertEqual(package['runner_sha256'], refresh.RUNNER_PIN)
                self.assertEqual(package['stager_sha256'], refresh.STAGER_PIN)
                self.assertEqual(approved['steps'], original['steps'])
                self.assertEqual(approved['build'], original['build'])
                self.assertNotIn('ldflags', approved['build'])
                for source, source_pin in original['sources'].items():
                    self.assertEqual(approved['sources'][source], source_pin)

    def test_age_width_v2_uses_own_source_and_normal_dependency(self):
        for stage, (pin, count) in age.ROLES.items():
            role = age.BASE / (stage + '-normal')
            m = json.loads((role / 'manifest.json').read_bytes())
            t = json.loads((role / 'azure-packet-v1/global-ticket.json').read_bytes())
            self.assertEqual(refresh.sha((role / 'manifest.json').read_bytes()), pin)
            self.assertEqual(len(m['build']['sv_sources']), count)
            self.assertEqual(m['build']['parameters']['EPOCH_AGE_REG'], 1)
            self.assertEqual(m['build']['runtime_threads'], 1)
            for package in t['packages']:
                self.assertEqual(package['runner_sha256'], refresh.RUNNER_PIN)
                self.assertEqual(package['stager_sha256'], refresh.STAGER_PIN)
            if stage == 'full':
                self.assertEqual(t['after'], ['s4-p16-r15-protocol-age-aw8-normal-q1-v2'])
                self.assertEqual(t['on'], 'PASS_expected_contracts')
            else:
                self.assertNotIn('after', t)


if __name__ == '__main__':
    unittest.main()
