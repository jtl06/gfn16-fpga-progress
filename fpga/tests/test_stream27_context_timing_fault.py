import importlib.util
from pathlib import Path
import unittest

from fpga.reference import stream27_context_timing_native as normal

PATH = normal.ROOT / 'results/throughput-20260929/trackS-c2-timing-v1/source-tools/prepare_fault.py'
SPEC = importlib.util.spec_from_file_location('private_context_timing_fault', PATH)
fault = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fault)


class TimingFaultRoleTests(unittest.TestCase):
    def test_external_origin_abort_and_exact_production(self):
        manifest, files = fault.role('external')
        self.assertEqual(manifest['test_role'], 'deliberate_fault')
        self.assertEqual(manifest['steps'][0]['expected_returncode'], 0)
        self.assertIn('origin_abort=3 peer_recovery=0', manifest['steps'][0]['expected_stdout'])
        cpp = files[manifest['build']['cpp_source']]
        self.assertIn(b'd.command_index=mode?65537:1', cpp)
        self.assertIn(b'd.command_generation=mode?1:2', cpp)
        self.assertIn(b'd.clk=1;d.eval();fault_sticky(d)', cpp)
        self.assertTrue(manifest['context_timing']['fault_role']['production_RTL_unchanged'])

    def test_reset_actual_payload_and_two_bounded_fifos(self):
        manifest, files = fault.role('reset')
        cpp = files[manifest['build']['cpp_source']]
        self.assertIn(b'std::min(4u,COUNTS[c]-1)', cpp)
        self.assertIn(b'd.feed_level==34', cpp)
        self.assertIn(b'C2_TIMING_RESET_RAM_RETENTION', cpp)
        self.assertIn('retained_words=512 pending_response_invalid=1 nonempty_fifo=2/4',
                      manifest['steps'][0]['expected_stdout'])

    def test_oracle_control_is_genuine_typed_nonzero(self):
        manifest, _ = fault.role('oracle')
        self.assertEqual(manifest['steps'][0]['expected_returncode'], 1)
        self.assertEqual(manifest['steps'][0]['expected_stderr'],
                         'S4_HOST_CONTEXT_SIGNED96_VALUE ctx=0 address=0\n')
        self.assertEqual(manifest['steps'][0]['argv'], ['{exe}', '--oracle-negative'])

    def test_actual_generated_owner_abi_and_full32_alias_fault(self):
        manifest, files = fault.role('owner')
        cpp = files[manifest['build']['cpp_source']]
        self.assertIn(b'count+=65536', cpp)
        self.assertIn(b'first_fault==first_capture', cpp)
        self.assertIn(b'quarantined(d)', cpp)
        self.assertIn('full32_ordinal_alias=1 epoch=1 generation=1 context=1 global_abort=4',
                      manifest['steps'][0]['expected_stdout'])
        self.assertTrue(manifest['context_timing']['owner_generated_header_sha256'])


if __name__ == '__main__':
    unittest.main()
