"""Recovery identity/closure tests only; no native execution or retry policy edit."""
import json
import unittest

from fpga.reference import stream27_r15_application_v4_quota_recovery_packet_v1 as recovery
from fpga.tools import global_queue_v1 as queue


class ApplicationQuotaRecoveryTests(unittest.TestCase):
    def test_exact_preserved_initial_quota_and_unclaimed_full(self):
        self.assertEqual(recovery.original('aw8')['result']['status'], 'terminal_failure')
        self.assertEqual(recovery.original('full')['result']['status'],
                         'cancelled_unstarted_dependency_failure')

    def test_one_fresh_worker_pair_and_original_functional_identity(self):
        for stage, (id, pin) in recovery.ROLES.items():
            role = recovery.own.BASE / 'trackS-r15-shell-application-native-v4' / (stage + '-normal')
            m = json.loads((role / 'manifest.json').read_bytes())
            t = json.loads((role / 'quota-retry-packet-v1/global-ticket.json').read_bytes())
            before = recovery.original(stage)
            self.assertEqual(recovery.sha((role / 'manifest.json').read_bytes()), pin)
            self.assertEqual(t['id'], id)
            self.assertEqual(queue.expected_identity(t), queue.expected_identity(before))
            self.assertEqual(t['resources'], before['resources'])
            self.assertEqual(t['test_role'], 'normal')
            self.assertFalse({p['worker_id'] for p in queue.packages(t)} &
                             {p['worker_id'] for p in queue.packages(before)})
            for package in t['packages']:
                path = role / 'quota-retry-packet-v1' / (
                    'packet-' + package['profile'].split('static', 1)[1].split('-', 1)[0]) / 'manifest.json'
                approved = json.loads(path.read_bytes())
                self.assertEqual(approved['steps'], m['steps'])
                self.assertEqual(approved['build']['parameters'], m['build']['parameters'])
                self.assertEqual(approved['build']['sv_sources'], m['build']['sv_sources'])
                for source, pin in m['sources'].items():
                    self.assertEqual(approved['sources'][source], pin)

    def test_only_original_quota_retry_and_genuine_new_normal_full_dependency(self):
        for stage, (id, _) in recovery.ROLES.items():
            role = recovery.own.BASE / 'trackS-r15-shell-application-native-v4' / (stage + '-normal')
            t = json.loads((role / 'quota-retry-packet-v1/global-ticket.json').read_bytes())
            if stage == 'aw8':
                self.assertEqual(t['infra_retry_of'], recovery.own.ROLES['aw8']['id'])
                self.assertNotIn('after', t)
            else:
                self.assertEqual(t['supersedes_unstarted'], recovery.own.ROLES['full']['id'])
                self.assertEqual(t['after'], [recovery.ROLES['aw8'][0]])
                self.assertEqual(t['on'], 'PASS_expected_contracts')
                self.assertNotIn('infra_retry_of', t)


if __name__ == '__main__':
    unittest.main()
