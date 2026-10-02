import unittest
from fpga.reference import stream27_host_contexts_native as native
class HostContextNativeTests(unittest.TestCase):
    def test_resolved_normal_and_independent_whole_integer_vectors(self):
        m,files=native.role();self.assertEqual(len(m['build']['sv_sources']),52);self.assertEqual(len(m['steps']),1)
        self.assertIn('rtl/genefer_sdp_ram32.sv',m['build']['sv_sources'])
        self.assertIn('lineage/rtl/kernel/genefer_sdp_ram32.sv',m['sources'])
        self.assertEqual(m['build']['parameters']['EPOCH_SEED0'],65534)
        contexts=m['host_contexts']['program']['contexts'];self.assertEqual([c['frame_count'] for c in contexts],[3,5])
        self.assertNotEqual(contexts[0]['dependent_steps'][-1]['canonical_signed32'],contexts[1]['dependent_steps'][-1]['canonical_signed32'])
        self.assertFalse(m['host_contexts']['full_N_numeric_locally_performed'])
        for token in (b'S4_HOST_CONTEXT_ACTUAL_FULL_CHAINS',b'S4_HOST_CONTEXT_READ_FULL_OWNER',b'S4_HOST_CONTEXT_SIGNED96_VALUE',b'S4_HOST_CONTEXT_ORDERED_FINAL_CAPTURE'):
            self.assertIn(token,files[native.CPP])
    def test_signed_sentinel_is_separate_normal(self):
        m,_=native.role('sentinel');self.assertEqual(len(m['steps']),1)
        for c in m['host_contexts']['program']['contexts']:self.assertEqual(c['dependent_steps'][-1]['canonical_signed32'],[-1]+[0]*31)
    def test_p16_is_separate_resolved_geometry_and_whole_vector(self):
        m,files=native.role(p=16);g=m['host_contexts']['geometry']
        self.assertEqual(m['build']['parameters']['P'],16);self.assertEqual(g['rows'],2);self.assertEqual(g['warm_interval'],126)
        self.assertEqual(g['feedback_delay'],4);self.assertEqual(len(m['build']['sv_sources']),52)
        self.assertEqual([len(c['initial_c0']) for c in m['host_contexts']['program']['contexts']],[16,16])
        self.assertIn(b'FIRST[2]={204,267}',files[native.HEADER]);self.assertIn(' p=16 ',m['steps'][0]['expected_stdout'])
    def test_p16_diet_fence_actual_calendar_is_separate(self):
        m,files=native.role(p=16,diet=True);g=m['host_contexts']['geometry']
        self.assertEqual(len(m['build']['sv_sources']),53)
        self.assertEqual(m['host_contexts']['diet_flags'],dict(corr_serial_bfs=2,mont_factored=1,cold_launch_fence=1))
        self.assertEqual([g[k] for k in ('pointwise_accept','sink_accept','first_digit','carry_done','warm_interval')],[76,114,156,161,161])
        plan=m['host_contexts']['two_context_schedule'];self.assertEqual(plan['launch_gaps'],[80,81])
        self.assertEqual(plan['frame_starts'],[0,80,161,241,322,402,563,724])
        self.assertIn(b'FIRST[2]={204,284}',files[native.HEADER]);self.assertIn(b'EXPECT_CAPTURE_COPY=false',files[native.HEADER])
        self.assertFalse(m['host_contexts']['expected_capture_during_copy'])
        self.assertIn('capture_during_copy=0',m['steps'][0]['expected_stdout'])
    def test_aw8_p16_dense_long_peer_is_real_overlap_cohort(self):
        m,files=native.role(p=16,diet=True,n=256,counts=(3,14));g=m['host_contexts']['geometry']
        self.assertEqual(g['rows'],16);self.assertEqual(g['warm_interval'],212)
        self.assertEqual([c['frame_count'] for c in m['host_contexts']['program']['contexts']],[3,14])
        self.assertTrue(m['host_contexts']['expected_capture_during_copy'])
        self.assertIn('counts=3/14 chains=2 squares=17 reads=1024 peer_live_reads=256',m['steps'][0]['expected_stdout'])
        self.assertIn(b'FIRST[2]={204,310}',files[native.HEADER]);self.assertIn(b'EXPECT_CAPTURE_COPY=true',files[native.HEADER])
if __name__=='__main__':unittest.main()
