import unittest
from pathlib import Path
from fpga.reference import stream27_r15_dma_aperture_model_v1 as m
from fpga.reference import stream27_r15_pcie_avmm_v7 as endpoint
from fpga.reference import stream27_r15_pcie_avmm_v8 as width_endpoint
from fpga.reference import stream27_r15_dma_aperture_native_v1 as native


class Aperture(unittest.TestCase):
    def test_all_boundaries_high_aliases_and_overflow(self):
        for write,ranges in ((True,m.WRITE_RANGES),(False,m.READ_RANGES)):
            for lo,hi in ranges:
                self.assertTrue(m.allowed(lo,1,write))
                self.assertTrue(m.allowed(hi-32,1,write))
                self.assertFalse(m.allowed(hi-32,2,write))
                self.assertEqual(m.allowed(hi,1,write),any(x==hi for x,_ in ranges))
                for high in (1<<25,1<<32,1<<63):self.assertFalse(m.allowed(lo|high,1,write))
        self.assertFalse(m.allowed(m.LIMIT,31,True))
        self.assertFalse(m.allowed(0,0,True))
        self.assertFalse(m.allowed(0,32,False))
        self.assertFalse(m.allowed(0x1000000,1,False))

    def test_no_extra_vendor_alignment_rule(self):
        self.assertTrue(m.allowed(0x1000004,1,True))
        self.assertTrue(m.allowed(0x1002004,2,True))
        b=m.Burst();self.assertEqual(b.accept(0x1002000,3),(0x1002000,3))
        self.assertEqual(b.accept(m.LIMIT,0),(0x1002000,3))
        self.assertEqual(b.accept(1<<63,31),(0x1002000,3))
        with self.assertRaises(ValueError):b.accept(1<<63,1)

    def test_source64_before_narrowing_and_bounded_storage(self):
        root=Path(__file__).resolve().parents[1]
        rtl=(root/'rtl/kernel/genefer_stream27_r15_dma_aperture_v1.sv').read_text()
        self.assertIn('input logic [63:0] wr_address',rtl)
        self.assertIn('output logic [63:0] down_wr_address',rtl)
        self.assertIn('logic [64:0] e;',rtl)
        self.assertNotIn('[24:0]',rtl)
        self.assertNotIn('[0:N',rtl)
        self.assertIn('terminal?256\'b0:down_rd_readdata',rtl)

    def test_endpoint_v7_sameorigin_ordered_fault(self):
        text=endpoint.source().decode()
        self.assertIn('assign external_fault_ready=!reset && link_ready;',text)
        self.assertIn('if(external_fault_accept)fault();',text)
        self.assertIn('!external_fault_valid &&',text)
        self.assertEqual(text.count('abort_due||resp_valid||external_fault_valid||cmd_valid||waiting'),3)

    def test_endpoint_v8_exact_width_only_reverse(self):
        text=width_endpoint.source().decode()
        self.assertEqual(text.replace(width_endpoint.AFTER,width_endpoint.BEFORE,1).encode(),endpoint.source())
        for n in (32,256,65536):
            for index in (0,n-31,n-1,n,(1<<17)-1):
                for count in range(32):
                    old=((index+count)&((1<<18)-1))>n
                    new=((index+count)&((1<<32)-1))>n
                    self.assertEqual(old,new)

    def test_fault_terminal_admission_and_split_descriptor_slaves(self):
        self.assertFalse(m.allowed(0x1002000-32,2,True))
        rtl=(Path(__file__).resolve().parents[1]/'rtl/kernel/genefer_stream27_r15_dma_aperture_v1.sv').read_text()
        self.assertIn('bad_wr_first=!protocol_error &&',rtl)
        self.assertIn('bad_rd_first=!protocol_error &&',rtl)

    def test_native_source_closure_and_origin_negative_control(self):
        m,f=native.role('normal');fault,ff=native.role('fault');neg,nf=native.role('missing-mask')
        self.assertEqual(f[native.RTL],ff[native.RTL])
        self.assertEqual(f[native.CPP],ff[native.CPP])
        for name,raw in f.items():self.assertEqual(native.hashlib.sha256(raw).hexdigest(),m['sources'][name])
        self.assertEqual(nf[native.RTL].replace(b'rd_readdata=rd_data_q;',b"rd_readdata=terminal?256'b0:rd_data_q;",1),f[native.RTL])
        self.assertEqual(neg['steps'][0]['expected_returncode'],1)
        self.assertEqual(neg['steps'][0]['expected_stderr'],'R15_APERTURE_FAULT_ORIGIN_DATA_LEAK\n')
        self.assertIn('UNACCEPTED_READ_FAKE_COMPLETION',ff[native.CPP].decode())
        self.assertFalse(m['scope']['whole_core'])


if __name__=='__main__':unittest.main()
