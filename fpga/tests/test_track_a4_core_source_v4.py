import itertools
import unittest
from fpga.reference.track_a4_core_source_v4 import ROOT,verify,admission_edge
from fpga.reference.track_a4_registered_schedule_v1 import registered_schedule


class RegisteredAdmissionTests(unittest.TestCase):
    def test_exact_isolated_delta(self):
        result=verify()
        self.assertEqual(result['exact_successors'],3)
        self.assertEqual(result['normal_backend_cycle_delta'],1)
        text=(ROOT/'rtl/kernel/genefer_track_a4_square_backend_v4.sv').read_text()
        self.assertIn('(* preserve, dont_merge *) logic ntt_admission;',text)
        self.assertIn('assign compute_configure=start_ntt && !was_prefilled;',text)
        # Arithmetic/input range/cancel children/final-tail branches are frozen.
        self.assertIn('genefer_track_a4_cold_prefill_v1 #',text)
        self.assertIn('genefer_track_a4_field_transfer_v2 #',text)
        self.assertIn('if(fault || raw_admission_fault)begin ntt_admission<=0;state<=FAILED;',text)

    def test_normal_arm_then_launch_once(self):
        arm=admission_edge('NTT_START',False)
        self.assertFalse(arm['launch']);self.assertTrue(arm['token'])
        launch=admission_edge(arm['state'],arm['token'])
        self.assertTrue(launch['launch']);self.assertFalse(launch['token'])
        self.assertEqual(launch['state'],'NTT_WAIT')
        self.assertFalse(admission_edge(launch['state'],launch['token'])['launch'])

    def test_all_arm_fault_ready_quiet_cancel_combinations(self):
        for ready,quiet,fault,raw,cancel in itertools.product((False,True),repeat=5):
            result=admission_edge('NTT_START',False,ready=ready,quiet=quiet,fault=fault,raw=raw,cancel=cancel)
            self.assertFalse(result['launch'])
            self.assertEqual(result['token'],ready and quiet and not(fault or raw or cancel))
            if cancel:self.assertEqual(result['state'],'IDLE')
            elif fault or raw:self.assertEqual(result['state'],'FAILED')

    def test_late_registered_fault_and_cancel_suppress_launch(self):
        for fault,raw,cancel in itertools.product((False,True),repeat=3):
            result=admission_edge('NTT_LAUNCH',True,fault=fault,raw=raw,cancel=cancel)
            self.assertEqual(result['launch'],not(fault or cancel))
            self.assertFalse(result['token'])
            if raw:self.assertFalse(result['admitted_transfer'])
            if raw or fault or cancel:self.assertTrue(result['children_cancel_after'])
            # A raw ownership error may coincide with a launch, but no transfer
            # is admitted and backend FAILED cancels children before nextedge.
            if raw and not(fault or cancel):self.assertTrue(result['launch'])

    def test_reset_cancel_epoch_no_stale_token(self):
        # Operation config remains frozen in existing base/generation registers.
        # Cancel clears the sole pending token; a later operation must arm anew.
        old=admission_edge('NTT_LAUNCH',True,cancel=True)
        self.assertFalse(old['launch'] or old['token'])
        self.assertFalse(admission_edge('IDLE',old['token'])['launch'])
        new=admission_edge('NTT_START',old['token'])
        self.assertFalse(new['launch']);self.assertTrue(new['token'])

    def test_named_mutant_witnesses(self):
        # These directed contracts must also be bound to actual RTL in the
        # next native pilot; Python witnesses are not native mutant evidence.
        self.assertFalse(admission_edge('NTT_START',False)['launch']) # bypass register would launch
        self.assertFalse(admission_edge('NTT_LAUNCH',True,fault=True)['launch']) # removefault guard
        self.assertFalse(admission_edge('NTT_LAUNCH',True,cancel=True)['token']) # retain canceledtoken
        a=admission_edge('NTT_LAUNCH',True,raw=False)
        b=admission_edge('NTT_LAUNCH',True,raw=True)
        self.assertEqual(a['launch'],b['launch']) # rawfault re-gating recreates cone

    def test_source_budget_no_arithmetic_or_transfer_delta(self):
        for aw in (5,8,16):
            old=registered_schedule(1<<aw)
            self.assertEqual(old['ram_to_ram_displacement'],52)
            self.assertEqual(old['cold_prefill_child_cycles'],(1<<aw)//16+10)
        full=registered_schedule()
        self.assertEqual(full['warm_backend_cycles']+1,24721)
        self.assertEqual(full['warm_host_latency']+1,24723)
        self.assertEqual(full['warm_backend_cycles']+full['cold_backend_penalty']+1,28829)


if __name__=='__main__':unittest.main()
