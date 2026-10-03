import unittest

from reference import stream27_context_storage_combo_transport11_source_v2 as parent
from reference import stream27_context_feedback12_model as candidate


class Feedback12Model(unittest.TestCase):
    def test_zero_flags_exact_and_retimed_calendar(self):
        for n in (256,65536):
            old=parent.prepare(n,enabled=1,lean_production=1,crt_transport_reg=1,
                inverse_ingress_reg=1,term_join_transport_reg=1,lean_progress_watchdog=1)['geometry']
            self.assertEqual(candidate.geometry(old),old)
            new=candidate.geometry(old,feedback_ingress_reg=1,
                                   auto_correction_ingress_reg=1,c0_admission_direct=1)
            self.assertEqual(new['warm_interval'],old['warm_interval']+1)
            self.assertEqual(new['carry_done'],old['carry_done'])
            self.assertEqual(new['feedback_delay'],old['feedback_delay']+1)
            self.assertEqual(new['correction_cache_latency'],78)
            plan=candidate.schedule(new)
            self.assertLessEqual(plan['lease_peak'],4)
            for witness in plan['storage2_lifetime']:
                self.assertGreater(witness['minimum_gap'],0)
                self.assertLessEqual(witness['logical_peak'],4)
            self.assertEqual(new['next_cache_capture'],new['next_correction_accept']+78)
            if n==65536:
                ledger=candidate.event_calendar(new,1911814)
                self.assertEqual(ledger['pair_completion_cycles'],16182916927)
            else:
                with self.assertRaises(ValueError):candidate.geometry(old,feedback_ingress_reg=1)

    def test_origin_fault_queue_and_c0_full_width(self):
        self.assertEqual(candidate.prove_queue_contract()['queue_priority_cases'],32)
        proof=candidate.prove_c0_identity()
        self.assertGreater(proof['binary_checks'],50000)
        self.assertTrue(candidate.c0_predicates(0x80000000,0)[0])
        self.assertFalse(candidate.SOURCE_READY)


if __name__=='__main__':unittest.main()
