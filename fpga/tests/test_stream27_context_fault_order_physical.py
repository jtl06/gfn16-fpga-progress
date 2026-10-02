import json
import unittest

from fpga.reference import stream27_context_fault_order_physical as p


class OrderPhysicalTests(unittest.TestCase):
    def test_same_controls_only_three_field_source_moves(self):
        manifest, files = p.build()
        old = json.loads((p.PARENT/'manifest.json').read_text())
        for name in old['control_sha256']:
            self.assertEqual(files[name], (p.PARENT/name).read_bytes())
        changed = [name for name, pin in manifest['source_sha256'].items() if pin != old['source_sha256'][name]]
        self.assertEqual(len(changed), 3)
        for name in changed:
            self.assertEqual(p.order.reverse_root(files['rtl/'+name].decode()), (p.PARENT/'rtl'/name).read_text())

    def test_own_aw16_gate_and_no_calendar_or_settings_change(self):
        manifest, _ = p.build()
        old = json.loads((p.PARENT/'manifest.json').read_text())
        self.assertEqual(manifest['native_normal_id'], 's4-p16-c2-fault-order-full-normal-q1-v1')
        for key in ('top','geometry','core_parameters','allowed_stages','clock_period_ns','seed','compile_processors','control_sha256'):
            self.assertEqual(manifest[key], old[key])
        self.assertTrue(manifest['fault_source_order']['no_old_full_gate_inheritance'])
        self.assertTrue(manifest['fault_source_order']['warning_removal_is_not_exhaustive_fanin_proof'])


if __name__ == '__main__':
    unittest.main()
