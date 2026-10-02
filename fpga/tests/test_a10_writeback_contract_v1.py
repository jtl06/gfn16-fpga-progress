import unittest
from fpga.reference import a10_writeback_contract_v1 as contract


class WritebackAddressCalendar(unittest.TestCase):
    def test_all_small_stages_and_full_size_index_only_boundary_stages(self):
        for aw,stages in ((5,None),(8,None),(16,[0,7,15])):
            result=contract.check(aw,stages=stages)
            self.assertEqual(result['internal_read_to_physical_commit_edges'],9)
            self.assertEqual(result['point_unique_addresses'],1<<aw)
            self.assertFalse(result['numeric_full_N_NTT_performed'])
        self.assertEqual(result['concurrent_read_write_edges_checked'],3*(512-9))

    def test_stale_row_bundle_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'ONE_VISIT_PER_STAGE'):
            contract.check(8,mutant='stale-row')

    def test_bad_calendar_geometry_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'STAGES'):contract.check(8,stages=[0,0])
        with self.assertRaisesRegex(ValueError,'GEOMETRY'):contract.check(17)


if __name__=='__main__':unittest.main()
