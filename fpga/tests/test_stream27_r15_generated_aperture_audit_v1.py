import unittest
from fpga.reference.stream27_r15_generated_aperture_audit_v1 import audit


class ApertureAudit(unittest.TestCase):
    def test_actual_generated_alias_is_not_a_range_pass(self):
        result = audit()
        self.assertEqual(result['status'], 'BLOCKED_FULL64_ADDRESS_ALIAS')
        self.assertEqual(result['invalid_byte_address'], 0x100000000)
        self.assertEqual(result['agent_byte_address'], 0)
        self.assertFalse(result['native_execution_claim'])
