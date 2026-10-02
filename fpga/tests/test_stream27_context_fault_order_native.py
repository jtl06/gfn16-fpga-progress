import unittest
from fpga.reference import stream27_context_fault_order_native as m


class NativeOrder(unittest.TestCase):
    def test_normal_exact_contract(self):
        for stage in ('aw8-normal', 'full-normal'):
            role, files, bundle = m.role(stage)
            self.assertEqual(bundle['fault_source_order']['unchanged_files'], 55)
            self.assertEqual(role['fault_source_order']['compiled_sv'], 58 if stage == 'aw8-normal' else 59)
            self.assertTrue(role['fault_source_order']['unchanged_bench_probe_parameters_steps'])
            self.assertEqual(role['rtl_readiness']['rtl_ready_at_utc'], m.READY)

    def test_fault_contracts_not_relaxed(self):
        for stage in ('fault-external', 'fault-owner', 'fault-reset', 'fault-oracle', 'fault-early-cache'):
            role, _, _ = m.role(stage)
            self.assertEqual(role['test_role'], 'deliberate_fault')
        oracle, _, _ = m.role('fault-oracle')
        self.assertTrue(any(s['expected_returncode'] != 0 for s in oracle['steps']))
