"""Metadata/negative source checks only: no HDL or full-N arithmetic."""
import unittest
from unittest.mock import patch

from fpga.reference import core27_crtmont_soak_native_v3 as azure
from fpga.tools import prepare_core27_soak_sequence_v1 as sequence
from fpga.tools import prepare_core27_soak_sequence_v2 as hosts


class SoakSequenceTests(unittest.TestCase):
    def test_all_ten_chunks_fanout_after_same_gates(self):
        value = sequence.plan()
        chunks = [gate for gate in value['gates'] if gate['id'].startswith('chunk-') and gate['kind'] == 'native-gate']
        self.assertEqual(len(chunks), 10)
        self.assertEqual([(row['start'], row['end']) for row in chunks], [(i, i+100) for i in range(0,1000,100)])
        self.assertTrue(all(row['dependencies'] == ['full-reference', 'chunk-runtime-admission'] for row in chunks))
        self.assertTrue(all(row['controls'] == [] and row['independent'] for row in chunks))

    def test_uninterrupted_gate_is_separate_and_bound(self):
        gates = {row['id']:row for row in sequence.plan()['gates']}
        continuous = gates['continuous-1000']
        self.assertEqual(continuous['operations'], 1000)
        self.assertEqual(continuous['reset_count'], 1)
        self.assertEqual(continuous['reloads_between_operations'], 0)
        self.assertNotIn('combine-chunks', continuous['dependencies'])
        self.assertIn('continuous-runtime-admission', continuous['dependencies'])
        self.assertEqual(gates['combine-chunks']['dependencies'], [f'chunk-{i:02d}' for i in range(10)])

    def test_short_prefix_is_same_seed_profile_not_fullsize_numeric(self):
        value = sequence.plan()
        self.assertEqual(value['short_plan']['profile'], value['full_plan']['profile'])
        self.assertEqual(value['short_plan']['seed'], value['full_plan']['seed'])
        self.assertEqual(value['short_plan']['double_bits'], value['full_plan']['double_bits'][:2])
        self.assertNotEqual(value['short_plan']['case_id'], value['full_plan']['case_id'])

    def test_azure_parent_preserved_and_added_to_captures(self):
        module = azure.parent()
        self.assertEqual(module.SELF, azure.SELF)
        self.assertEqual(module.admit_runtime, azure.admit_runtime)
        self.assertEqual(module.base().TOP, sequence.adapter().base().TOP)

    def test_azure_runtime_refuses_mac_before_import(self):
        with patch.object(azure.platform, 'system', return_value='Darwin'):
            with self.assertRaisesRegex(ValueError, 'REFERENCE_LINUX'):
                azure.admit_runtime('{}')

    def test_host_binding_changes_only_runtime_adapter(self):
        gcp = hosts.worker('gfn16-pilot-c4d').plan()
        az = hosts.worker('gfn16-azure-f16').plan()
        self.assertEqual(gcp['full_plan'], az['full_plan'])
        self.assertEqual(gcp['short_plan'], az['short_plan'])
        self.assertIn(azure.SELF, az['source_hashes'])
        with self.assertRaisesRegex(ValueError, 'APPROVED_RUNTIME_HOST'):
            hosts.worker('unadmitted-host')


if __name__ == '__main__':
    unittest.main()
