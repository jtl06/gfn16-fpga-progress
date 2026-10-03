import importlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
m=importlib.import_module('fpga.reference.stream27_protected_relay13_barrier_native')


class BarrierFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.normal,cls.files=m.role('normal')

    def test_actual58_retained_and_raw_origins_reversible(self):
        fixture=self.normal['relay13_barrier_fixture']
        self.assertEqual(len(self.normal['build']['sv_sources']),65)
        self.assertTrue(fixture['production58_unchanged'])
        self.assertEqual(len(fixture['diagnostic_clones']),6)
        for row in fixture['diagnostic_clones']:
            text=self.files['rtl/'+row['diagnostic']+'.sv'].decode()
            for before,after in reversed(row['changes']):text=m.once(text,after,before)
            self.assertEqual(text.encode(),self.files['rtl/'+row['parent']+'.sv'])
        self.assertNotIn('force ',self.files[m.CPP].decode())

    def test_normal_and_fault_sources_same_and_expected_negative(self):
        fault,files=m.role('faults')
        self.assertEqual(files,self.files)
        self.assertEqual(fault['build'],self.normal['build'])
        self.assertEqual(fault['probe'],self.normal['probe'])
        self.assertEqual(fault['steps'][1]['expected_returncode'],1)
        self.assertEqual(fault['steps'][1]['expected_stderr'],'RELAY13_BARRIER_EXTERNAL_MASK\n')
        self.assertEqual(fault['test_role'],'deliberate_fault')
        self.assertEqual(len(self.normal['steps']),1)

    def test_cpp_runtime_reference_and_private_flags_scope(self):
        text=self.files[m.CPP].decode()
        self.assertLess(text.index('gfn16_runtime::configure(context,argc,argv)'),text.index('DUT d(&context)'))
        self.assertEqual(text.count('DUT d(&context)'),1)
        self.assertIn('PRIVATE published/done are deliberately not asserted zero',text)
        self.assertIn('N+4',self.files['rtl/tb/stream27_host_contexts.cpp'].decode())
        self.assertIn('probe_newjob',self.files['rtl/tb/stream27_protected_relay13_barrier_probe.sv'].decode())
        self.assertFalse(self.normal['relay13_barrier_fixture']['independent_review'])
        self.assertIn('RELAY13_BARRIER_ARITH_REPORT_EXACT_LAG2',text)
        self.assertIn('RELAY13_BARRIER_STICKY_FAST_REPORT_NO_STOP_REQUALIFICATION',text)
        self.assertIn('fault_case(d,0,1,true)',text)

    def test_all_build_parameters_forwarded_to_actual_child(self):
        shell=self.files['rtl/tb/stream27_protected_relay13_barrier_probe.sv'].decode()
        for parameter in self.normal['build']['parameters']:
            self.assertIn('.'+parameter+'('+parameter+')',shell)
        self.assertIn('.EPOCH_SEED0(EPOCH_SEED0)',shell)
        self.assertIn('.EPOCH_SEED1(EPOCH_SEED1)',shell)

    def test_occupied_relays_and_reset_scope_not_private_flush(self):
        fixture=self.normal['relay13_barrier_fixture']
        self.assertFalse(fixture['FIELD100_native_result_inherited'])
        self.assertFalse(fixture['R14_source_or_result_inherited'])
        self.assertTrue(fixture['HOST_watchdog_is_not_field_flush'])
        self.assertEqual(fixture['new_relay_occupied_fault_windows'],
            ['forward_slot_q','pair_slot_q','inverse_slot_q'])
        shell=self.files['rtl/tb/stream27_protected_relay13_barrier_probe.sv'].decode()
        for field in range(3):
            for signal in ('forward_slot_q','pair_slot_q','inverse_slot_q'):
                self.assertIn('field'+str(field)+'.'+signal,shell)
        cpp=self.files[m.CPP].decode()
        self.assertIn('for(unsigned seam=0;seam<8;seam++)',cpp)
        self.assertIn('relay_reset_case(d,origin,seam)',cpp)
        self.assertIn('RELAY13_BARRIER_RELAY_RESET_NO_STALE_AUTHORITY',cpp)
        self.assertIn('private_pulses_allowed=1',cpp)
        self.assertNotIn('need(!d.probe_relay_slots',cpp.split('static void quiet',1)[1].split('static void seek',1)[0])


if __name__=='__main__':unittest.main()
