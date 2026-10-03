"""Source-only reversible R12 descriptor-guard fixture; native gates separate."""
import unittest
from pathlib import Path
from fpga.reference import stream27_feedback12_queue_probe_native as own


class QueuedDescriptorFixtureTests(unittest.TestCase):
    def test_same_source_normal_fault_roles_and_literal_production(self):
        normal,files=own.role(False);faults,other=own.role(True)
        self.assertEqual(normal['build'],faults['build'])
        self.assertEqual(files,other)
        self.assertEqual(len(normal['build']['sv_sources']),59)
        self.assertTrue(normal['r12_queued_guard']['production58_unchanged'])
        self.assertTrue(normal['r12_queued_guard']['driver_hooks_reversible'])
        self.assertFalse(normal['r12_queued_guard']['arbitrary_fault_or_RAM_config_protection_claim'])
        observer=files['rtl/'+normal['build']['top']+'.sv'].decode()
        self.assertIn('candidate.engine.queued_command_bad',observer)
        self.assertNotIn('always_ff',observer)
        cpp=files[own.CPP].decode()
        self.assertEqual(cpp.count('DUT d{&context}'),1)
        self.assertLess(cpp.index('gfn16_runtime::configure(context,argc,argv)'),cpp.index('DUT d{&context}'))
        self.assertIn('QUEUED_INDEX^=1u',cpp)
        self.assertIn('QUEUED_GENERATION^=1u',cpp)
        self.assertIn('d.probe_queue_bad&&!d.operation_accept',cpp)
        self.assertIn('R12_QUEUE_ORIGIN_PUBLIC_FENCE',cpp)
        self.assertNotIn('safety_error=',cpp)
        self.assertNotIn('local_error=',cpp)
        self.assertNotIn('feedback_owner_q=',cpp)
        for header in (own.HEADER,own.DRIVER):
            self.assertIn(('#include "'+Path(header).name+'"').encode(),files[own.CPP])
        self.assertEqual(normal['steps'][0]['expected_stdout'],own.NFOOTER)
        self.assertEqual(faults['steps'][0]['expected_stdout'],own.FFOOTER)
        self.assertEqual(faults['steps'][1]['expected_returncode'],1)


if __name__=='__main__':unittest.main()
