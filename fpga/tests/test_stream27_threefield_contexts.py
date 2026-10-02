import unittest
from fpga.reference import stream27_threefield_contexts as core


class SourceTests(unittest.TestCase):
    def test_real_assembly_and_full_owners(self):
        for n, p in ((32, 8), (256, 8), (32, 16), (256, 16)):
            b = core.prepare(n, p)
            s = b['files'][b['top'] + '.sv']
            self.assertEqual(s.count(' field0 ('), 1)
            self.assertEqual(s.count(' field1 ('), 1)
            self.assertEqual(s.count(' field2 ('), 1)
            self.assertIn('wire [1:0] bank=field_sink_bank[0]', s)
            self.assertNotIn('field_epoch[0][0]', s)
            self.assertNotIn('bank_epoch[epoch_in[0]]', s)
            self.assertIn('bank_live[metadata_free]<=1', s)
            self.assertIn('bank_context[bank]!=field_context[0]', s)
            self.assertIn('crt_tag[0]<={field_context[0],field_epoch[0],field_generation[0],field_row[0]}', s)
            self.assertIn('field_sink_bank[f]!=field_sink_bank[0]', s)
            self.assertIn('genefer_crt3_27_mont_pipe crt', s)
            self.assertIn('genefer_stream27_blockcarry_lane_param_v1 #(.AW(AW),.P(P))', s)
            self.assertIn('crt_tag[0:15]', s)
            self.assertIn('d<16', s)

    def test_profile_snapshot_and_shared_lane_guard(self):
        b = core.prepare(32, 8)
        s = b['files'][b['top'] + '.sv']
        self.assertEqual(b['setup_latency'], 98)
        self.assertIn('profile_reciprocal[0:1]', s)
        self.assertIn('profile_limit[0:1]', s)
        self.assertIn('profile_generation[0:1]', s)
        self.assertIn('if(unit_setup_done && unit_config_valid && !out_error)', s)
        self.assertIn('.base(profile_base[field_context[0]])', s)
        self.assertIn('if(begin_carry && (|lane_busy))carry_bad=1', s)
        self.assertIn('setup_owner_busy', s)
        self.assertIn('carry_context==setup_context', s)
        self.assertIn('context_enabled[carry_context]', s)
        self.assertNotIn('.base(qualified_base),.reciprocal', s)

    def test_invalid_scope_rejected(self):
        with self.assertRaisesRegex(ValueError, 'EXPLICIT_CONTEXTS2'):
            core.prepare(32, 8, contexts=1)

    def test_intrinsic_profile_successor_not_pending_gate(self):
        before = core.prepare(32, 8, profile_admission=0)
        after = core.prepare(32, 8)
        self.assertIn('_profile_qualified_v2', after['top'])
        s = after['files'][after['top'] + '.sv']
        self.assertEqual(s.count('.in_slot_valid(field_input_valid)'), 3)
        self.assertEqual(s.count('.frame_start(frame_start && frame_profile_ok)'), 3)
        self.assertIn('generation_in==profile_generation[context_in]', s)
        self.assertNotIn('frame_profile_ok=', before['files'][before['top'] + '.sv'])
        guard = s[s.index('wire frame_profile_ok='):s.index('assign frame_accept=')]
        self.assertNotIn('fault_pending', guard)
        self.assertNotIn('context_enabled', guard)
        self.assertNotIn('live_generation', guard)
        self.assertEqual(before['geometry'], after['geometry'])


if __name__ == '__main__':
    unittest.main()
