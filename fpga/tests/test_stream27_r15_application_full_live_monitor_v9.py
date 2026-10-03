"""Source/temporal/liveness monitor tests only; no HDL or full-N reference run."""
import json
import unittest
from fpga.reference import stream27_r15_application_full_live_monitor_v9 as own


class LiveMonitorTests(unittest.TestCase):
    def test_actual_work_cannot_be_claimed_from_completed_counter_or_finished_peer(self):
        self.assertTrue(own.live_peer_event(True,0,1,True))
        for args in ((False,0,1,True),(True,1,1,True),(True,0,2,True),(True,0,1,False)):
            self.assertFalse(own.live_peer_event(*args))
        self.assertNotIn('probe_canonical,0',own.NEW_MONITOR)
        self.assertIn('probe_live_canon_busy',own.NEW_MONITOR)

    def test_literal70_header_parameters_reference_and_strict_conjunction(self):
        before=json.loads((own.PARENT/'manifest.json').read_bytes());m,f,b=own.role()
        self.assertEqual(m['build'],before['build'])
        for n,t in b['files'].items():self.assertEqual(f['rtl/'+n],t.encode())
        changed={n for n,h in before['sources'].items() if own.sha(f[n])!=h}
        self.assertEqual(changed,{before['build']['cpp_source'],'rtl/'+before['build']['top']+'.sv'})
        text=f[m['build']['cpp_source']].decode()
        self.assertIn('done_edges[0]<done_edges[1]&&waiting_b&&capture_copy==EXPECT_CAPTURE_COPY&&canonical_peer',text)
        self.assertIn('i<432ull*N',text)
        self.assertIn('R15_APPLICATION_ALL_SIGNED96_REFERENCE',text)
        self.assertEqual(f['rtl/tb/s4_p16_two_context_full_config.h'],
                         (own.PARENT/'source/fpga/rtl/tb/s4_p16_two_context_full_config.h').read_bytes())

    def test_source_schedule_and_validator_reject_no_live_peer_wrong_publish_missing_words(self):
        p=own.temporal_proof();self.assertEqual(p['first_live0_model'],25325)
        self.assertEqual(p['peer_overlap_margin'],129)
        trace=dict(first=[25325,684789],peer_edges=129,publication_edges=[680689,1340153],signed96_words=262144,error=0)
        def output(t):return own.parent.FOOTERS['full']+'R15_APPLICATION_LIVE_CANONICAL '+json.dumps(t)+'\n'
        self.assertEqual(own.validate(output(trace),'',0,own.config(),{})['status'],'PASS_expected_contracts')
        for update in (dict(peer_edges=0),dict(first=[25454,684789]),dict(publication_edges=[680690,1340153]),dict(signed96_words=262143)):
            with self.assertRaises(ValueError):own.validate(output(dict(trace,**update)),'',0,own.config(),{})


if __name__=='__main__':unittest.main()
