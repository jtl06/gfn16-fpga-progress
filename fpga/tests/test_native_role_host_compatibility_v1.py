"""Exact soak portability regression: compiler compatibility is not runtime admission."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from fpga.tools import global_queue_v1 as queue
from fpga.tools import native_role_host_scope_v1 as scope

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT / 'queue/variant-preparation/soak-t5b-aw16-chunk-03-q3-v1/expand-1790850694623509000'
PROOF_SHA = 'ccd3602422b315d32806cfae44d6a526efd37a57791d8787135f9dc389373980'


class RoleHostCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.ticket = json.loads((PREP / 'ticket.json').read_text())
        proof = self.ticket['measured_runtime_admission']
        self.assertEqual(proof['sha256'], PROOF_SHA)
        self.assertEqual(hashlib.sha256(Path(proof['path']).read_bytes()).hexdigest(), PROOF_SHA)
        self.assertEqual(json.loads(Path(proof['path']).read_text())['compatible_hosts'], ['gfn16-pilot-c4d'])
        self.azure = queue.load_host(ROOT / 'queue/hosts/azure-f32-q2.json')
        self.gcp = queue.load_host(ROOT / 'queue/hosts/gcp-c4d-q1.json')
        self.azure['enabled'] = self.gcp['enabled'] = True
        self.azure['observed_mem_available_bytes'] = 64 * (1 << 30)

    def eligible(self, ticket, host):
        with patch.object(queue, 'dependency_state', return_value=(True, 'ready')), \
             patch.object(queue, 'rows', return_value=[]):
            try:
                return queue.eligible(ticket, host, host['lanes'][0], now=1790851000)[0]
            except (ValueError, KeyError):
                return False  # A malformed source-bound admission must fail closed.

    def test_actual_compatible_tools_and_eight_gib_cannot_rehost_gcp_runtime(self):
        self.assertTrue(any(p['profile'] == 'azure-burst16-static8g01-v1' for p in self.ticket['packages']))
        self.assertTrue(self.eligible(self.ticket, self.gcp))
        self.assertFalse(self.eligible(self.ticket, self.azure))

    def test_missing_duration_proof_does_not_make_known_gcp_recipe_portable(self):
        ticket = copy.deepcopy(self.ticket)
        ticket.pop('measured_runtime_admission')
        self.assertFalse(self.eligible(ticket, self.azure))

    def test_bad_proof_pin_fails_closed_even_on_original_host(self):
        ticket = copy.deepcopy(self.ticket)
        ticket['measured_runtime_admission']['sha256'] = '0' * 64
        self.assertFalse(self.eligible(ticket, self.gcp))
        self.assertFalse(self.eligible(ticket, self.azure))

    def test_explicit_host_list_can_narrow_but_not_broaden_source_proof(self):
        ticket = copy.deepcopy(self.ticket)
        ticket['allowed_hosts'] = [self.azure['name'], self.gcp['name']]
        self.assertFalse(self.eligible(ticket, self.azure))
        self.assertTrue(self.eligible(ticket, self.gcp))
        ticket['allowed_hosts'] = [self.azure['name']]
        self.assertFalse(self.eligible(ticket, self.gcp))


class PureRoleHostScopeTests(RoleHostCompatibilityTests):
    def eligible(self, ticket, host):
        try:
            return scope.host_allowed(ticket, host['name'])
        except (ValueError, KeyError):
            return False

    def test_failed_or_different_model_proof_does_not_admit(self):
        proof_path = Path(self.ticket['measured_runtime_admission']['path'])
        original = scope.read_pinned
        for change in ({'status': 'FAIL_duration'}, {'source_model_build': {}},
                       {'source_model_pins': {'rtl/fake.sv': '0' * 64}},
                       {'compatible_hosts': []}):
            def altered(path, pin):
                value = original(path, pin)
                if Path(path) == proof_path:
                    value.update(change)
                return value
            with patch.object(scope, 'read_pinned', side_effect=altered):
                self.assertFalse(self.eligible(self.ticket, self.gcp))


if __name__ == '__main__':
    unittest.main()
