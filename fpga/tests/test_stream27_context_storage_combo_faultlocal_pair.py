import unittest
from fpga.reference import stream27_context_storage_combo_faultlocal_pair as p
class PairTests(unittest.TestCase):
    def test_exact_source_and_full_generation_transport(self):
        m,f=p.role();top=f['rtl/'+p.TOP+'.sv'].decode();cpp=f['rtl/tb/r7_comm_pair_normal.cpp'].decode()
        self.assertEqual(top.count('.GEN_W(25)'),32)
        self.assertEqual(top.count('.diag_head_xor('),32)
        self.assertIn('output wire [3199:0] old_generation',top)
        self.assertIn('uint32_t gen=0x1555500u+5+f',cpp)
        self.assertIn('g*25,25',cpp)
        self.assertNotIn('get(d.new_generation,g*8,8)',cpp)
        self.assertNotIn('get(d.old_generation,i*8,8)',cpp)
        self.assertTrue(m['r7_pair']['normal_injection_zero'])
        self.assertEqual(len(m['build']['sv_sources']),6)
    def test_corrupt_leaf_pin_fails_closed(self):
        raw=(p.ROOT/'rtl/kernel'/(p.OLD+'.sv')).read_text()
        with self.assertRaises(ValueError):p.clone(raw+'\n',p.OLD,'old')
    def test_full_tag_faults_use_real_occupied_phase_and_unchanged_sv(self):
        m,f=p.fault_role()
        cpp=f[m['build']['cpp_source']].decode()
        self.assertIn('bit<27',cpp)
        self.assertIn('phase<2',cpp)
        self.assertIn('R7_TAG_NO_INPUT_MALFORMED_CONFOUND',cpp)
        self.assertIn('R7_TAG_ADMITTED_EDGE_THEN_QUIET',cpp)
        self.assertIn('get(d.old_generation,i*25,25)',cpp)
        normal=p.BASE/'paired-normal-v1'
        for name in m['build']['sv_sources']:
            self.assertEqual(f[name],(normal/'source/fpga'/name).read_bytes())
        self.assertEqual(m['r7_pair']['tag_cases'],864)
if __name__=='__main__':unittest.main()
