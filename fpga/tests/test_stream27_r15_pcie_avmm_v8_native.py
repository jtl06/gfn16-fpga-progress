import unittest
from fpga.reference import stream27_r15_pcie_avmm_v8_native as native
from fpga.reference import stream27_r15_pcie_avmm_v8 as leaf
from fpga.reference import stream27_r15_pcie_avmm_v8_negative as negative


class EndpointV8Native(unittest.TestCase):
    def test_default_normal_captured_source_closure(self):
        m,f=native.role()
        self.assertEqual(f[native.RTL],leaf.source())
        for p,raw in f.items():self.assertEqual(native.hashlib.sha256(raw).hexdigest(),m['sources'][p])
        text=f[native.CPP].decode()
        self.assertIn('d.link_ready=0;d.external_fault_valid=0;',text)
        self.assertLess(text.index('gfn16_runtime::configure(ctx,argc,argv)'),text.index('Bench(int argc,char**argv):d(setup'))
        self.assertIn('crossbus_progress=1',m['steps'][0]['expected_stdout'])
        self.assertFalse(m['scope']['whole_core'])

    def test_four_external_origins_and_exact_negative(self):
        m,f=native.role('external-fault');n,nf=negative.role()
        self.assertEqual(f[native.CPP],nf[native.CPP])
        self.assertEqual(n['steps'][0]['expected_returncode'],1)
        self.assertEqual(n['steps'][0]['expected_stderr'],'R15_AVMM_EXTERNAL_FAULT_VALID_A_LEAK\n')
        self.assertEqual(nf[native.RTL].replace(negative.AFTER,negative.BEFORE,1),f[native.RTL])
        text=f[native.CPP].decode()
        for key in ('EXTERNAL_BEGIN_AUTHORITY','EXTERNAL_ZERO_DRAIN','EXTERNAL_ORDERED_TAIL','EXTERNAL_RESET_RECOVERY'):
            self.assertIn(key,text)
        self.assertFalse(m['scope']['independent_review'])


if __name__=='__main__':unittest.main()
