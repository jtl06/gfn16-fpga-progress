"""Private R13 metadata/source proof only; actual numerical gates run remotely."""
import copy
import json
import unittest
from fpga.reference import stream27_protected_relay13_healthy_join as own

class ProtectedRelay13NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle=own.source()

    def test_own_protected_source_and_three_relay_geometry(self):
        b=self.bundle;g=b['geometry']
        self.assertEqual(len(b['files']),58)
        self.assertEqual((g['warm_interval'],g['pointwise_accept'],g['sink_accept'],g['carry_busy_edges']),
                         (8464,4208,8420,4142))
        self.assertEqual(b['parameters']['CRT_TRANSPORT_REG'],0)
        self.assertNotIn('LEAN_PRODUCTION',b['parameters'])
        for key in ('INVERSE_INGRESS_REG','TERM_JOIN_TRANSPORT_REG','FORWARD_INGRESS_REG'):
            self.assertEqual(b['parameters'][key],1)

    def test_source_owned_periodic_and_sample_calendar(self):
        g=self.bundle['geometry']
        for count,total in ((2,1405695),(100,2235167),(1000,9852767)):
            e=own.calendar(g,count)
            self.assertEqual(e['first_edges'],[204,4436])
            self.assertEqual(e['full_read_completion_cycles'],total)
        self.assertEqual(own.calendar(g,1911814)['pair_completion_cycles'],16182916927)
        self.assertEqual(own.calendar(g,1911814,(True,False))['pair_completion_cycles'],16182916927+65536)

    def test_exact_own_footer_rejects_equal_I_ancestor_edges(self):
        e=own.ROOT/'queue/evidence'/own.JOBS[2][0]/'gate-receipt.json'
        v=json.loads(e.read_text())['steps'][0]['validation']['measurements']
        own.validate_footer(v,self.bundle['geometry'],2)
        for key,value in (('interval',8461),('done_edges',[680689,1340153]),
                          ('launches',[[204,8668],[4435,12899]])):
            changed=copy.deepcopy(v);changed[key]=value
            with self.assertRaises(ValueError):own.validate_footer(changed,self.bundle['geometry'],2)

    def test_actual_source_receipts_join_without_clock(self):
        out=own.close()
        self.assertEqual(set(out['jobs']),{'2','100'})
        self.assertTrue(out['native1000_pending'])
        self.assertIsNone(out['selected_period_ns'])
        self.assertFalse(out['promotion_allowed'])

if __name__=='__main__':unittest.main()
