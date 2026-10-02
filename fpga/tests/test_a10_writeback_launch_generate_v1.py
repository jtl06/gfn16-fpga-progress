import unittest
from fpga.reference import a10_writeback_launch_generate_v1 as gen


class WritebackSource(unittest.TestCase):
    def test_exact_reversible_internal_bundle_and_physical_completion(self):
        source = gen.source()
        restored = source
        for old,new in reversed(gen.changes()): restored = restored.replace(new,old)
        self.assertEqual(restored,(gen.ROOT/gen.PARENT).read_text())
        self.assertIn('.write_en(ram_write_en)',source)
        self.assertIn('write_launch_row<=data_wa[bank];write_launch_word<=data_w[bank];',source)
        self.assertIn('bf_writeback_valid && !writeback_cancel',source)
        self.assertIn('mul_writeback_valid && !writeback_cancel',source)
        self.assertIn('state==IDLE ? data_we[bank]',source)
        self.assertIn('if(data_re[bank] && ram_write_en && data_ra[bank]==ram_write_addr)',source)

    def test_source_derived_drain_delta_all_geometry(self):
        for aw,transform,point,total,whole in ((5,55,10,600,126),(8,96,13,1025,211),(16,8352,1033,88685,17743)):
            result = gen.ledger(aw)
            self.assertEqual((result['transform_cycles'],result['point_cycles'],result['engine_work_cycles'],result['whole_controller_ntt_cycles']),
                             (transform,point,total,whole))
            self.assertEqual(result['whole_cycle_delta'],2*aw+1)
            self.assertFalse(result['hold_repair_claim'])

    def test_native_oracle_retained_and_new_pending_realRAM_contract(self):
        cpp = gen.cpp_source()
        for marker in ('A10_INDEPENDENT_SMALL_ORACLE_AGREEMENT','A10_INDEPENDENT_SMALL_CONVOLUTION_AGREEMENT',
                       'A10_F3_PENDING_BEFORE_FIRST_COMMIT','A10_F3_ABORT_FLUSH','A10_F3_QUIET_TAIL','pending-cancel-RAM','cancel-recovery'):
            self.assertIn(marker,cpp)
        self.assertIn('d.cycles==AW*(groups+9)',cpp)
        self.assertIn('d.cycles==(op?point_groups+9:AW*(groups+10))',cpp)
        self.assertIn('assign writeback_pending=|child.writeback_pending_mask;',gen.native_host_source())

    def test_bad_geometry_and_missing_literal_fail_closed(self):
        for aw in (4,17,True):
            with self.assertRaises(ValueError): gen.ledger(aw)
        with self.assertRaisesRegex(ValueError,'SINGLE_LITERAL_SITE'):
            gen.transform('unrelated source',gen.changes())


if __name__ == '__main__':
    unittest.main()
