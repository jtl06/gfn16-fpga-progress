import json
import unittest
from fpga.reference import stream27_crt_tag_delay_bind as bind
from fpga.reference import stream27_r11_density_audit as audit


class DensityTests(unittest.TestCase):
    def test_exact_captured_root_default_and_reverse(self):
        bundle = json.loads(audit.CAPTURE.read_bytes())
        text = next(t for t in bundle['files'].values() if bind.DECL in t)
        self.assertEqual(bind.bind_arithmetic(text, 0), text)
        new = bind.bind_arithmetic(text, 1)
        self.assertEqual(bind.unbind_arithmetic(new), text)
        for protected in ('always_ff @(posedge clk or negedge rst_n)',
                          'wire begin_carry=joined && join_start && !error_barrier;',
                          'if(fault_pending)out_error<=1;'):
            self.assertEqual(new.count(protected), text.count(protected))

    def test_full_address_space_no_collision(self):
        for pointer in range(16):
            self.assertNotEqual(pointer, (pointer + 1) & 15)

    def test_dense_bubble_reset_and_stop_model(self):
        for result in audit.model_checks():
            self.assertGreater(result['comparisons'], 3000)
            self.assertEqual(result['address_collisions'], 0)

    def test_impulse_exact_preedge_sixteen(self):
        model = audit.DelayModel(38)
        model.reset()
        self.assertFalse(model.tick(True, (1 << 38)-1)[0])
        for _ in range(15):
            self.assertFalse(model.tick(False, 0)[0])
        valid, word = model.tick(False, 0)
        self.assertTrue(valid)
        self.assertEqual(word, (1 << 38)-1)

    def test_declared_counts_not_measured_credit(self):
        result = audit.audit()
        self.assertEqual(result['declared_ff']['reduction_upper_bound'], 523)
        self.assertEqual(result['field_to_crt_added_declared_ff'], 1920)
        self.assertFalse(result['native_qualified'])
        self.assertIsNone(result['whole_lab_saving'])


if __name__ == '__main__':
    unittest.main()
