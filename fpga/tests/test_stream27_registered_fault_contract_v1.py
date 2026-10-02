import unittest
from fpga.reference.stream27_registered_fault_contract_v1 import FaultGate,Protocol,fault_calendar


class FaultContractTests(unittest.TestCase):
    def ready_protocol(self,n=256):
        p=Protocol(n);p.edge(0,begin=(0,7,1000000),correction=(0,7))
        p.edge(36,ready=(0,7));return p

    def test_origin_one_edge_then_stop_and_reset(self):
        p=FaultGate()
        self.assertEqual(p.edge(occupied=True,current_fault=True),dict(advance=True,commit=True,error=True))
        self.assertEqual(p.edge(occupied=True),dict(advance=False,commit=False,error=True))
        self.assertEqual(p.edge(occupied=True,reset=True),dict(advance=False,commit=False,error=False))
        self.assertTrue(p.edge(occupied=True)['commit'])

    def test_immediate_stale_disable_and_owned_tag(self):
        for owner in (False,True):
            for generation in (False,True):
                for enabled in (False,True):
                    p=FaultGate();r=p.edge(occupied=True,current_fault=True,owner_match=owner,
                                          generation_match=generation,enabled=enabled)
                    self.assertEqual(r['commit'],owner and generation and enabled)
                    self.assertTrue(r['advance']);self.assertFalse(p.edge(occupied=True)['commit'])

    def test_unrelated_bad_young_profile_old_sink_origin_commit(self):
        p=self.ready_protocol();tick=p.g['sink_accept']
        # Bad range is external diagnosis; a valid new lease still accepts
        # physically and a correctly owned old sink word may commit once.
        r=p.edge(tick,begin=(1,8,0),sink=(7,True),live_generation=7,external_fault=True)
        self.assertTrue(r.frame_accept);self.assertTrue(r.commit);self.assertTrue(r.error_after)
        self.assertFalse(p.edge(tick+1,sink=(7,False),live_generation=7).commit)

    def test_wrong_sink_generation_and_first_tag_never_commit(self):
        for token in ((8,True),(7,False)):
            p=self.ready_protocol();r=p.edge(p.g['sink_accept'],sink=token,live_generation=token[0])
            self.assertTrue(r.fault_pending);self.assertFalse(r.commit);self.assertTrue(r.error_after)
        p=self.ready_protocol();r=p.edge(p.g['sink_accept'],sink=(7,True),live_generation=8)
        self.assertFalse(r.commit);self.assertFalse(r.error_after)

    def test_duplicate_or_unknown_correction_intrinsically_rejected(self):
        for token in ((0,7),(0,8),(1,7)):
            p=self.ready_protocol();r=p.edge(40,correction=token)
            self.assertFalse(r.correction_accept);self.assertTrue(r.error_after)
        p=Protocol();r=p.edge(0,begin=(0,7,517),correction=(0,7),external_fault=True)
        self.assertTrue(r.frame_accept);self.assertTrue(r.correction_accept);self.assertTrue(r.error_after)

    def test_cache_ready_same_pw_edge_not_usable(self):
        p=Protocol();p.edge(0,begin=(0,7,517),correction=(0,7))
        r=p.edge(p.g['pointwise_accept'],ready=(0,7),pw=(7,True))
        self.assertFalse(r.pointwise_accept);self.assertTrue(r.error_after)

    def test_n256_latest_correction_deadline_55_pass_56_fail(self):
        for correction_tick,expected in ((55,False),(56,True)):
            p=Protocol(256)
            for t in range(p.g['pointwise_accept']+1):
                r=p.edge(t,begin=(0,7,517) if t==0 else None,
                    correction=(0,7) if t==correction_tick else None,
                    ready=(0,7) if t==correction_tick+36 else None,
                    pw=(7,True) if t==p.g['pointwise_accept'] else None)
            self.assertEqual(r.error_after,expected)
            self.assertEqual(r.pointwise_accept,not expected)

    def test_last_commit_origin_fault_retires_only_owned_old_lease(self):
        p=self.ready_protocol();g=p.g
        for t in range(g['sink_accept'],g['last_sink']):
            self.assertTrue(p.edge(t,sink=(7,t==g['sink_accept']),live_generation=7).commit)
        r=p.edge(g['last_sink'],sink=(7,False),live_generation=7,
                 begin=(1,8,0),external_fault=True)
        self.assertTrue(r.commit);self.assertTrue(r.frame_accept);self.assertTrue(r.error_after)
        self.assertEqual([(o.epoch,o.generation) for o in p.owners],[(1,8)])

    def test_full_geometry_late_corrections_and_two_image_owners(self):
        # Scalar/event-only: no full-N numerical transform or coefficient work.
        p=Protocol(65536);g=p.g;peak=commits=0
        starts={0:(65535,7,1000000),g['interval']:(0,7,1000000)}
        corrections={0:(65535,7),g['next_correction_accept']:(0,7)}
        cache={t+36:tag for t,tag in corrections.items()}
        for t in range(g['interval']+g['last_sink']+1):
            def physical(first):
                windows=[t-s-first for s in starts if 0<=t-s-first<g['rows']]
                self.assertLessEqual(len(windows),1)
                return (7,windows[0]==0) if windows else None
            r=p.edge(t,begin=starts.get(t),correction=corrections.get(t),ready=cache.get(t),
                pw=physical(g['pointwise_accept']),sink=physical(g['sink_accept']),live_generation=7)
            self.assertFalse(r.error_after);peak=max(peak,r.owners_after);commits+=r.commit
        self.assertEqual(peak,2);self.assertEqual(commits,2*g['rows']);self.assertEqual(p.owners,[])

    def test_complete_legal_calendar_cancellation_does_not_drop_rows(self):
        for n in (256,65536):
            p=Protocol(n);g=p.g;commits=0
            for t in range(g['last_sink']+1):
                r=p.edge(t,begin=(0,7,1000000) if t==0 else None,
                    correction=(0,7) if t==0 else None,ready=(0,7) if t==36 else None,
                    pw=(7,t==g['pointwise_accept']) if g['pointwise_accept']<=t<g['pointwise_accept']+g['rows'] else None,
                    sink=(7,t==g['sink_accept']) if g['sink_accept']<=t<=g['last_sink'] else None,
                    live_generation=7 if t<g['sink_accept']+3 else 8)
                self.assertFalse(r.error_after);commits+=r.commit
            self.assertEqual(commits,3);self.assertEqual(p.owners,[])
            self.assertEqual(fault_calendar(n)['legal_cycle_delta'],0)

    def test_reset_requests_held_high_have_no_public_admit(self):
        p=Protocol();r=p.edge(0,begin=(0,7,517),correction=(0,7),sink=(7,True),reset=True)
        self.assertFalse(r.frame_accept);self.assertFalse(r.correction_accept);self.assertFalse(r.commit)

    def test_ambiguous_same_generation_calendar_has_no_intrinsic_authority(self):
        # Protocol-only illegal overlapping calendar: top's dense-input check
        # rejects this earlier. Unique public authority is still mandatory.
        p=Protocol(256)
        for t in range(97):
            r=p.edge(t,begin=(0,7,517) if t==0 else ((1,7,517) if t==4 else None),
                correction=(0,7) if t==0 else ((1,7) if t==4 else None),
                ready=(0,7) if t==36 else ((1,7) if t==40 else None),
                pw=(7,t in (92,96)) if t>=92 else None)
            if t<96:self.assertFalse(r.error_after)
        self.assertFalse(r.pointwise_accept);self.assertTrue(r.fault_pending);self.assertTrue(r.error_after)


if __name__=='__main__':unittest.main()
