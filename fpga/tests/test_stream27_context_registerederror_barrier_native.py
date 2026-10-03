import importlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
m=importlib.import_module('fpga.reference.stream27_context_registerederror_barrier_native')


class BarrierFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.normal,cls.files=m.role('normal')

    def test_actual55_retained_and_raw_origins_reversible(self):
        fixture=self.normal['r9_barrier_fixture']
        self.assertEqual(len(self.normal['build']['sv_sources']),62)
        self.assertTrue(fixture['production55_unchanged'])
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
        self.assertEqual(fault['steps'][1]['expected_stderr'],'R9_BARRIER_EXTERNAL_MASK\n')
        self.assertEqual(fault['test_role'],'deliberate_fault')
        self.assertEqual(len(self.normal['steps']),1)

    def test_cpp_runtime_reference_and_private_flags_scope(self):
        text=self.files[m.CPP].decode()
        self.assertLess(text.index('gfn16_runtime::configure(context,argc,argv)'),text.index('DUT d(&context)'))
        self.assertEqual(text.count('DUT d(&context)'),1)
        self.assertIn('PRIVATE published/done are deliberately not asserted zero',text)
        self.assertIn('N+4',self.files['rtl/tb/stream27_host_contexts.cpp'].decode())
        self.assertIn('probe_newjob',self.files['rtl/tb/stream27_context_registerederror_barrier_probe.sv'].decode())
        self.assertFalse(self.normal['r9_barrier_fixture']['independent_review'])

    def test_all_build_parameters_forwarded_to_actual_child(self):
        shell=self.files['rtl/tb/stream27_context_registerederror_barrier_probe.sv'].decode()
        for parameter in self.normal['build']['parameters']:
            self.assertIn('.'+parameter+'('+parameter+')',shell)
        self.assertIn('.EPOCH_SEED0(EPOCH_SEED0)',shell)
        self.assertIn('.EPOCH_SEED1(EPOCH_SEED1)',shell)


if __name__=='__main__':unittest.main()
