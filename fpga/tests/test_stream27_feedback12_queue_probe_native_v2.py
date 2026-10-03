"""Source-only include repair: preserve failed v1 and all functional bytes."""
import unittest
from fpga.reference import stream27_feedback12_queue_probe_native as old
from fpga.reference import stream27_feedback12_queue_probe_native_v2 as own


class IncludeRepairTests(unittest.TestCase):
    def test_one_config_definition_and_literal_production(self):
        before, prior = old.role(False)
        normal, files = own.role(False)
        faults, other = own.role(True)
        self.assertEqual(normal['build'], faults['build'])
        self.assertEqual(files, other)
        self.assertEqual(normal['build']['parameters'], before['build']['parameters'])
        self.assertEqual(normal['build']['sv_sources'], before['build']['sv_sources'])
        for name in normal['build']['sv_sources'] + [own.DRIVER, own.HEADER,
                'rtl/tb/s4_p16_two_context_full_config.h',
                'rtl/tb/stream27_host_chain_full_reference_v1.h']:
            self.assertEqual(files[name], prior[name])
        redundant=b'#include "s4_p16_two_context_full_config.h"\n'
        self.assertEqual(files[own.CPP], prior[old.CPP].replace(redundant, b'', 1))
        self.assertNotIn(redundant, files[own.CPP])
        self.assertEqual(files[own.DRIVER].count(redundant), 1)
        self.assertEqual(normal['steps'], before['steps'])
        self.assertTrue(normal['r12_queued_guard']['duplicate_config_include_only_repair'])
        self.assertTrue(normal['r12_queued_guard']['predecessor_faults_unstarted'])


if __name__=='__main__': unittest.main()
