"""AUTHOR source-only checks, not native direct-load correctness."""
import unittest
from fpga.reference import stream27_r15_direct_cold_native as p

class DirectNormal(unittest.TestCase):
    def test_new_source_and_no_legacy_cold_load(self):
        m,f,b=p.role()
        self.assertEqual(len(b['files']),63)
        self.assertEqual(m['build']['parameters']['DIRECT_COLD'],1)
        self.assertEqual(m['build']['runtime_threads'],1)
        cpp=f[p.CPP].decode()
        self.assertIn('direct_load(d);',cpp)
        self.assertNotIn('S4_HOST_CONTEXT_COLD_LOAD',cpp)
        self.assertIn('R15_NO_LEGACY_LOAD_BYPASS',cpp)
        self.assertIn('R15_DIRECT_COMMIT_ACK_PUBLISH',cpp)
        self.assertIn('uint16_t(d.dc_next_epoch>>(16*ctx))',cpp)
        self.assertNotIn('lane32(d.dc_next_epoch',cpp)
        self.assertIn('read_word(d',cpp)
        self.assertLess(cpp.index('gfn16_runtime::configure(context'),cpp.index('DUT d(&context)'))
        self.assertEqual(b['r15_direct_cold']['global_fault_containment']['masked'],
          ['read_valid','canonical_ready','command_ready','command_accept','operation_accept','done','warm_done','busy'])
        self.assertTrue(all(m['sources']['rtl/'+n]==pin for n,pin in b['generated_sha256'].items()))

    def test_fault_source_separate_with_same_production_and_recovery(self):
        normal,_,parent=p.role();fault,f,b=p.role('fault')
        self.assertEqual(parent['generated_sha256'],b['generated_sha256'])
        self.assertEqual(fault['test_role'],'deliberate_fault')
        self.assertIn('direct_faults(d);run(d);',f[p.CPP].decode())
        self.assertIn('cases=10',fault['steps'][0]['expected_stdout'])
        self.assertEqual(fault['build']['parameters'],normal['build']['parameters'])

if __name__=='__main__':unittest.main()
