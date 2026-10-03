import unittest
from fpga.reference import stream27_context_storage_combo_directbound_native as n


class DirectBoundNativeTests(unittest.TestCase):
    def check_stage(self, stage):
        old, files, parent = n.capture(stage)
        m, new, b = n.role(stage)
        self.assertEqual(m['steps'], old['steps'])
        self.assertEqual(m['probe'], old['probe'])
        self.assertEqual(new[old['build']['cpp_source']], files[old['build']['cpp_source']])
        self.assertEqual(m['build']['parameters'], dict(old['build']['parameters'], CANONICAL_C0_DIRECT=1))
        self.assertEqual(b['geometry'], parent['geometry'])
        self.assertEqual(len(b['files']), 55)
        self.assertTrue(b['context_storage_combo_directbound']['reverse_to_parent_exact'])
        self.assertTrue(b['context_storage_combo_directbound']['c1_live_inputs_fault_priority_load_read_reset_FFs_unchanged'])
        for name, pin in b['source_sha256'].items():
            self.assertEqual(n.sha(new['lineage/' + name]), pin)
        return m, new

    def test_aw8_normal_contract(self):
        self.check_stage('aw8')

    def test_full_transparent_observer(self):
        m, files = self.check_stage('full')
        self.assertEqual(len(m['build']['sv_sources']), 56)
        text = files['rtl/' + m['build']['top'] + '.sv'].decode()
        self.assertNotRegex(text, r'\b(always|always_ff|always_comb|initial)\b')
        self.assertEqual(text.count('.CANONICAL_C0_DIRECT(CANONICAL_C0_DIRECT)'), 1)


if __name__ == '__main__':
    unittest.main()
