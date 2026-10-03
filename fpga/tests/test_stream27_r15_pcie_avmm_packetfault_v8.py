import unittest
from fpga.reference import stream27_r15_pcie_avmm_packetfault_v8 as native


class CurrentPacketCorpus(unittest.TestCase):
    def test_literal39_source_and_only_new_input_init(self):
        m,f=native.role()
        donor=native.DONOR/'source/fpga'
        self.assertEqual(f[native.FAULT_CPP],(donor/native.FAULT_CPP).read_bytes())
        self.assertEqual(f[native.NORMAL_CPP].replace(b'd.link_ready=0;d.external_fault_valid=0;',b'd.link_ready=0;',1),(donor/native.NORMAL_CPP).read_bytes())
        self.assertEqual(f[native.RTL],native.leaf.source())
        for p,raw in f.items():self.assertEqual(native.hashlib.sha256(raw).hexdigest(),m['sources'][p])
        self.assertEqual(m['build']['cpp_source'],native.FAULT_CPP)
        self.assertIn('cases=39 invalid_records=33',m['steps'][0]['expected_stdout'])
        self.assertEqual(m['scope']['required_normal_dependency'],'s4-r15-pcie-avmm-normal-q1-v8')
        self.assertFalse(m['scope']['old_native_result_inherited'])

    def test_exact_held_origin_only_mutant(self):
        m,f=native.role();n,nf=native.role(True)
        self.assertEqual(nf[native.RTL].replace(native.AFTER,native.BEFORE,1),f[native.RTL])
        self.assertEqual(nf[native.FAULT_CPP],f[native.FAULT_CPP])
        self.assertEqual(n['steps'][0]['expected_returncode'],1)
        self.assertEqual(n['steps'][0]['expected_stderr'],'R15_AVMM_FAULT_VALID_A_LEAK\n')
        self.assertFalse(n['scope']['independent_review'])


if __name__=='__main__':unittest.main()
