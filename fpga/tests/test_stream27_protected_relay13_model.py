import itertools
import unittest
from reference import stream27_protected_field100_bind as parent
from reference import stream27_protected_relay13_model as model


class Relay13Model(unittest.TestCase):
    def test_all_switches_and_literal_feedback_FIFO(self):
        for n in (256,65536):
            before=parent.prepare(n,enabled=1,**{k.lower():1 for k in parent.FLAGS})['geometry']
            self.assertEqual(model.geometry(before),before)
            for inverse,term,forward in itertools.product((0,1),repeat=3):
                g=model.geometry(before,inverse_ingress_reg=inverse,
                    term_join_transport_reg=term,forward_ingress_reg=forward)
                proof=model.schedule(g)
                self.assertLessEqual(proof['lease_peak'],4)
                self.assertEqual(g['feedback_delay'],before['existing_feedback_delay']+1)
                self.assertEqual(g['ct_output_latency'],before['ct_output_latency'])
                self.assertEqual(g['gs_output_latency'],before['gs_output_latency'])
                self.assertEqual(g['pointwise_accept'],before['pointwise_accept']+forward)
                self.assertEqual(g['first_digit'],before['first_digit']+inverse+term+forward)

    def test_primary_calendar_not_brief_estimate(self):
        for n,interval,first,done,read in ((256,218,[204,313],[3225,5809],6065),
                (65536,8464,[204,4436],[680695,1340159],1405695)):
            before=parent.prepare(n,enabled=1,**{k.lower():1 for k in parent.FLAGS})['geometry']
            g=model.geometry(before,inverse_ingress_reg=1,term_join_transport_reg=1,forward_ingress_reg=1)
            self.assertEqual(g['warm_interval'],interval)
            c=model.event_calendar(g,2)
            self.assertEqual(c['first_edges'],first)
            self.assertEqual(c['publication_edges'],done)
            self.assertEqual(c['full_read_completion_cycles'],read)
            self.assertEqual(model.event_calendar(g,1911814)['count_per_context'],1911814)

    def test_tuple_reset_FAST_and_closed_flags(self):
        self.assertEqual(model.prove_tuples()['binary_priority_cases'],36)
        with self.assertRaises(ValueError):model.geometry({},inverse_ingress_reg=True)


if __name__=='__main__':unittest.main()
