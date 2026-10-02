import unittest
from fpga.reference import stream27_shared_field_flags as fields
from fpga.reference import stream27_shared_field_v5 as frozen
from fpga.reference import stream27_host_chain_flags as host
from fpga.reference import stream27_host_chain_param_v3 as old_host


class BoundaryFlagTests(unittest.TestCase):
    def test_zero_is_complete_parent(self):
        self.assertEqual(fields.prepare(256, 8, 0), frozen.prepare(256, 8, 0))
        self.assertEqual(host.prepare(256, 8, paired=True, canonical_pipe_stages=1),
                         old_host.prepare(256, 8, paired=True, canonical_pipe_stages=1))

    def test_field_only_ingress_and_calendar_delta(self):
        for p in (8, 16):
            for f in range(3):
                before = fields.prepare(256, p, f)
                after = fields.bind(before, boundary_inputreg=1)
                changed = {name for name, text in before['files'].items()
                           if after['files'].get(name) != text}
                self.assertEqual(changed, {before['top'] + '.sv'})
                a, b = before['geometry'], after['geometry']
                for key in ('pointwise_accept', 'sink_accept', 'first_digit', 'carry_done', 'warm_interval'):
                    self.assertEqual(a[key], b[key])
                self.assertEqual(b['correction_cache_latency'], a['correction_cache_latency'] + 1)
                self.assertEqual(b['next_cache_capture'], a['next_cache_capture'] + 1)
                self.assertEqual(b['cache_margin'], a['cache_margin'] - 1)
                root = after['files'][after['top'] + '.sv']
                self.assertIn('.quarantine(stop),.in_valid(boundary_slot)', root)
                self.assertIn('.correction(accepted_correction ?', root)
                self.assertIn('.payload_in(boundary_owner)', root)
                self.assertNotIn('BOUNDARY_INPUTREG', before['parameters'])

    def test_small_recalendar_rejected(self):
        with self.assertRaisesRegex(ValueError, 'INPUTREG_(FRONTEND_PADDING|WARM_RECALENDAR)_REQUIRED'):
            fields.prepare(32, 8, 0, boundary_inputreg=1)

    def test_full_calendar_no_main_delay(self):
        for p in (8, 16):
            before = frozen.geometry(65536, p)
            after = fields.boundary_geometry(before)
            self.assertEqual(after['warm_interval'], before['warm_interval'])
            self.assertEqual(after['pointwise_accept'], before['pointwise_accept'])
            self.assertEqual(after['correction_cache_latency'], before['correction_cache_latency'] + 1)

    def test_host_all_three_and_pair_source_join(self):
        standalone = host.prepare(256, 8, canonical_pipe_stages=1, boundary_inputreg=1)
        paired = host.prepare(256, 8, paired=True, canonical_pipe_stages=1, boundary_inputreg=1)
        for name, text in standalone['files'].items():
            self.assertEqual(paired['files'].get(name), text)
        roots = [name for name in standalone['files'] if name.startswith('genefer_stream27_shared_warm_')]
        self.assertEqual(len(roots), 3)
        for name in roots:
            self.assertIn('_boundary_inputreg_v1', name)
            self.assertIn('genefer_stream27_signed_boundary_inputreg_v1 #(', standalone['files'][name])
        old = old_host.prepare(256, 8, canonical_pipe_stages=1)
        self.assertEqual(standalone['cycle_contract'], old['cycle_contract'])
        self.assertEqual(standalone['canonical_cost'], old['canonical_cost'])
        self.assertEqual(standalone['parameters']['BOUNDARY_INPUTREG'], 1)

    def test_descriptor_only_changes_real_host_storage(self):
        before = host.prepare(256, 8, canonical_pipe_stages=1, boundary_inputreg=1)
        after = host.bind(before, descriptor_fifo_ff=1)
        old_real = next(name for name, text in before['files'].items() if 'feed_index[0:3]' in text)
        changed = {name for name, text in before['files'].items() if after['files'].get(name) != text}
        self.assertEqual(changed, {old_real})
        root = after['files'][after['top'] + '.sv']
        self.assertNotIn('feed_index[0:3]', root)
        self.assertIn('.clear(state==IDLE && start)', root)
        for token in ('wire ingress_bad=', 'command_index!=next_write_index',
                      'feed_count<3\'d4 || feed_pop', '.command_accept(feed_pop)',
                      'feed_pop && feed_count==0'):
            self.assertIn(token, root)
        self.assertEqual(before['geometry'], after['geometry'])
        self.assertEqual(before['cycle_contract'], after['cycle_contract'])
        paired = host.prepare(256, 8, paired=True, canonical_pipe_stages=1,
                              boundary_inputreg=1, descriptor_fifo_ff=1)
        for name, text in after['files'].items():
            self.assertEqual(paired['files'].get(name), text)


if __name__ == '__main__':
    unittest.main()
