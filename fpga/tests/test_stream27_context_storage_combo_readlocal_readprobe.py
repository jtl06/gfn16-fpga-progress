import unittest
from fpga.reference import stream27_context_storage_combo_readlocal_readprobe as probe
from fpga.reference import stream27_context_storage_combo_readlocal_bind as core


class ReadPairTests(unittest.TestCase):
    def test_exact_old_new_pair(self):
        m,f=probe.role()
        self.assertEqual(core.reverse_leaf(f['rtl/'+probe.LOCAL+'.sv'].decode()).encode(),f['rtl/'+probe.PARENT+'.sv'])
        self.assertEqual(len(m['build']['sv_sources']),4)
        self.assertNotRegex(f['rtl/'+probe.TOP+'.sv'].decode(),r'\b(always|initial)\b')
        self.assertEqual(m['steps'][0]['expected_returncode'],0)

    def test_same_compiled_role_faults_separate(self):
        normal,n=probe.role('normal')
        for mode in ('faults','oracle'):
            m,f=probe.role(mode)
            self.assertEqual(f,n)
            self.assertEqual(m['build'],normal['build'])
            self.assertEqual(m['test_role'],'deliberate_fault')
        self.assertEqual(probe.role('oracle')[0]['steps'][0]['expected_returncode'],1)

    def test_read_and_response_priority_boolean_proof(self):
        self.assertEqual(core.prove_reads()['cases'],8192)
        cpp=(probe.ROOT/probe.CPP).read_text()
        for label in ('R4_READLOCAL_ORIGIN_FAULT_PRIORITY','R4_READLOCAL_RESET_PENDING_QUIET',
                      'R4_READLOCAL_DIRTY_INPUT_E0','R4_READLOCAL_SIGNED96_VALUE'):
            self.assertIn(label,cpp)
        self.assertIn('if(mode>=2)',cpp)
        self.assertIn('h.quarantine(4)',cpp)

    def test_unknown_mode_rejected(self):
        with self.assertRaisesRegex(ValueError,'MODE'):
            probe.role('missing-first')


if __name__=='__main__':unittest.main()
