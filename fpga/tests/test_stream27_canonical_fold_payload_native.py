import unittest
from fpga.reference import stream27_canonical_fold_payload_native as n


class FoldPayloadNativeTests(unittest.TestCase):
    def test_exact_paired_protected_source_and_runtime(self):
        m,files=n.role()
        self.assertEqual(len(m['build']['sv_sources']),4)
        old=files['rtl/'+n.bind.OLD+'.sv'].decode()
        new=files['rtl/'+n.bind.NEW+'.sv'].decode()
        self.assertEqual(n.bind.reverse_leaf(new),old)
        cpp=files[n.CPP].decode()
        self.assertIn('context(argc,argv),d(&context)',cpp)
        self.assertIn('small_whole_integer(effective,base)',cpp)
        self.assertIn('h.images==10&&h.reads==2564',cpp)
        self.assertEqual(m['rtl_readiness']['rtl_ready_at_utc'],n.READY)

    def test_negative_role_preserves_all_four_SV(self):
        m,f=n.role('normal');bad,b=n.role('fault')
        self.assertEqual(m['build'],bad['build'])
        for name in m['build']['sv_sources']:self.assertEqual(f[name],b[name])
        self.assertEqual(bad['test_role'],'deliberate_fault')

    def test_actual_generated_header_priority_role(self):
        from fpga.reference import stream27_canonical_fold_payload_priority_native as p
        m,f=n.role();bad,b=p.role()
        for name in m['build']['sv_sources']:self.assertEqual(f[name],b[name])
        self.assertIn('correction0',b[p.CPP].decode())
        self.assertNotIn('LOCAL(value)',b[p.CPP].decode())
        self.assertIn('LOADbase5000',bad['fold_payload']['priority_scope'])
        self.assertTrue(p.datetime and p.timezone)


if __name__=='__main__':unittest.main()
