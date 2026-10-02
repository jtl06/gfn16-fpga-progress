import json
import unittest
from fpga.reference import a10_writeback_native_replay_v1 as native


class WritebackNativeArchive(unittest.TestCase):
    def test_three_actual_AW5_sources_values_counters_cancel_and_recovery(self):
        pins=('c9c0192ea13ed161a4b17a450eec4bfaba0e703eaf0d867570513164278ccf18',
              '2e9707d0f7eacdb67fa31b930854bf3e799f43f203b7f479aab1ec4591d5c2fa',
              '9fd542b52496988dc06e1b184b26fd75ff3a099a43e93ebf260c777cb0c8b36d')
        for field,pin in enumerate(pins):
            fresh=native.replay(5,field)
            saved=json.loads((native.prep.ROOT/f'results/throughput-20260929/a10-writeback-native-v1/aw5-f{field}/owner-native-replay-v1.json').read_text())
            self.assertEqual(fresh,saved);self.assertEqual(fresh['report_sha256'],pin)
            self.assertEqual(fresh['native_standalone_phase_ledger']['transform_cycles'],55)
            self.assertEqual(fresh['native_standalone_phase_ledger']['point_cycles'],10)
            self.assertIn('cycles=600',fresh['normal_stdout'])
            self.assertIn('pending_cancels=4 recovery_operations=4 recovery_residues=128 recovery_cycles=220',fresh['normal_stdout'])
            self.assertFalse(fresh['promotion_allowed']);self.assertFalse(fresh['hold_repair_claim'])

    def test_invalid_role_before_evidence_lookup(self):
        for aw,field in ((4,0),(17,0),(5,3),(5,True)):
            with self.assertRaisesRegex(ValueError,'REPLAY_ROLE'):native.replay(aw,field)

    def test_all_six_larger_geometry_archives_match_saved_owner_receipts(self):
        full_pins=('92468ae6ae64d7d747c91e7e853b70bebc41c7a81cb34569b01dfe0d85ce2b6b',
                   'f285e556a4eadc8c0eaa38ddfb39e5161e976e47f01f0393a5ab3bbf1e962e95',
                   '755ae1fc81c791681242c2e0c0c7fd4a51c1a35f1d064b8ca1a508fd02fb772d')
        for aw in (8,16):
            for field in (0,1,2):
                fresh=native.replay(aw,field)
                saved=json.loads((native.prep.ROOT/f'results/throughput-20260929/a10-writeback-native-v1/aw{aw}-f{field}/owner-native-replay-v1.json').read_text())
                self.assertEqual(fresh,saved)
                if aw==16:
                    self.assertEqual(fresh['report_sha256'],full_pins[field])
                    self.assertEqual(fresh['native_standalone_phase_ledger']['transform_cycles'],8352)
                    self.assertEqual(fresh['native_standalone_phase_ledger']['point_cycles'],1033)
                    self.assertIn('residues=983040 cycles=88685',fresh['normal_stdout'])
                    self.assertIn('recovery_residues=262144 recovery_cycles=33408',fresh['normal_stdout'])


if __name__=='__main__':unittest.main()
