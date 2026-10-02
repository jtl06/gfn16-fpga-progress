import itertools
import unittest
from fpga.reference import anext_field_reset_release_v1 as model


class LocalResetRelease(unittest.TestCase):
    def test_pinned_sources_actual_cone_and_real_driver_pattern(self):model.guard()

    def test_async_assert_without_clock_and_two_edge_release(self):
        for kind in ('rst_n','cancel','failed'):
            d=model.Release();d.inputs(rst_n=True);d.edge();d.edge();self.assertTrue(d.ready)
            low={'rst_n':False} if kind=='rst_n' else {kind:True}
            self.assertEqual(d.inputs(**low)['field_rst_n'],[False]*3);self.assertFalse(d.ready)
            d.inputs(**({'rst_n':True} if kind=='rst_n' else {kind:False}))
            e1=d.edge();self.assertFalse(e1['before']['ready']);self.assertFalse(e1['after']['ready'])
            e2=d.edge();self.assertFalse(e2['before']['ready']);self.assertTrue(e2['after']['ready'])
            self.assertTrue(d.edge()['before']['ready'])

    def test_pulse_between_edges_flushes_stale_history(self):
        d=model.Release();d.inputs(rst_n=True);d.edge();d.edge()
        d.inputs(cancel=True);d.inputs(cancel=False)
        self.assertFalse(d.ready);self.assertFalse(d.edge()['after']['ready']);self.assertTrue(d.edge()['after']['ready'])

    def test_raw_same_edge_commit_kill_all_predicate_combinations(self):
        for rst,cancel,failed in itertools.product((False,True),repeat=3):
            d=model.Release(guard_q=[True]*3,driver_q=[True]*3)
            out=d.inputs(rst_n=rst,cancel=cancel,failed=failed)
            live=rst and not cancel and not failed
            self.assertEqual(out['field_allow'],[live]*3);self.assertEqual(out['kill'],not live)

    def test_earliest_transfer_two_boundary_stages_no_drop_or_retime(self):
        d=model.Release();d.inputs(rst_n=True)
        request_pipe=[False,False];leaf_commit=[]
        for edge in range(5):
            before=d.edge()['before'];leaf=request_pipe[1]
            if leaf:self.assertTrue(all(before['field_allow']));leaf_commit.append(edge)
            request_pipe=[edge==0,request_pipe[0]]
        self.assertEqual(leaf_commit,[2])

    def test_abort_each_release_age_and_sticky_failed_barrier(self):
        for age in range(4):
            d=model.Release();d.inputs(rst_n=True)
            for _ in range(age):d.edge()
            d.inputs(failed=True)
            for _ in range(6):self.assertFalse(d.edge()['after']['ready'])
            d.inputs(cancel=True);d.inputs(failed=False);self.assertFalse(d.ready)
            d.inputs(cancel=False);self.assertFalse(d.edge()['after']['ready']);self.assertTrue(d.edge()['after']['ready'])

    def test_negative_early_ready_stale_driver_and_scope(self):
        d=model.Release();d.inputs(rst_n=True)
        e1=d.edge();self.assertFalse(e1['after']['ready'])
        # A one-stage/early-ready mutant or retained guard would accept here.
        self.assertTrue(d.guard_q[0]);self.assertNotEqual(d.guard_q,d.driver_q)
        d.inputs(cancel=True);self.assertEqual(d.guard_q,[False]*3)
        ledger=model.ledger();self.assertEqual(ledger['warm_extra_edges'],0)
        self.assertEqual(ledger['cold_direct_admission_extra_edges'],2)
        self.assertFalse(ledger['physical_benefit_proven']);self.assertFalse(ledger['whole_sources_changed'])


if __name__=='__main__':unittest.main()
