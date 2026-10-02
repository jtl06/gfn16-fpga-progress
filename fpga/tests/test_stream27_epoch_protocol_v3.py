import unittest
from fpga.reference.stream27_epoch_protocol_v3 import geometry,scenario,Protocol


class EpochProtocolV3(unittest.TestCase):
    def test_exact_late_correction_deadline_no_stalls_all_sizes(self):
        for aw in range(5,17):
            g=geometry(1<<aw)
            self.assertEqual(g['minimum_stall_required'],0)
            self.assertEqual(g['correction_margin_after_cache_register'],6*aw+(aw-3)-31)
        self.assertEqual(geometry(32)['correction_margin_after_cache_register'],1)
        self.assertEqual(geometry()['correction_margin_after_cache_register'],78)

    def test_full_N_geometry_two_owner_overlap(self):
        result=scenario()
        self.assertIsNone(result['error']);self.assertEqual(result['peak_owners'],2)
        self.assertEqual(result['pointwise_rows'],4*8192)
        self.assertEqual(result['sink_rows'],4*8192)
        self.assertEqual(result['owners_remaining'],0)
        self.assertFalse(result['full_N_numeric_NTT_performed'])

    def test_finite_epoch_wrap_after_old_sink_drained(self):
        result=scenario(32,frames=10,epoch_bits=2,first_epoch=3)
        self.assertIsNone(result['error']);self.assertEqual(result['sink_rows'],40)

    def test_cancel_retains_every_physical_row_and_live_commit_authority(self):
        g=geometry(32)
        result=scenario(32,cancel_at=g['sink_accept'])
        self.assertIsNone(result['error']);self.assertEqual(result['sink_rows'],16)
        self.assertEqual(result['commits'],0)
        self.assertIn('CADENCE',scenario(32,cancel_at=10,drop_canceled=True)['error'])

    def test_late_wrong_cohort_and_register_same_edge_negatives(self):
        self.assertIn('DEADLINE',scenario(32,extra_cache_delay=2)['error'])
        self.assertIn('OWNER_MISSING',scenario(32,wrong_correction=True)['error'])
        p=Protocol(32);p.edge(0,begin=(0,0),correction=(0,0))
        self.assertFalse(p.edge(43,ready=(0,0),pw=(0,0,0)))
        self.assertIn('DEADLINE',p.error)


if __name__=='__main__':unittest.main()
