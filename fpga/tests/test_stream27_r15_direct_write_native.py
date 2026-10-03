"""Pure packaging/fixture checks, not native correctness or RAM mapping PASS."""
import unittest
from fpga.reference import stream27_r15_direct_write_native as n

class Contract(unittest.TestCase):
    def test_shapes_and_source_join(self):
        for size in (32,256):
            manifest,files=n.role(size)
            self.assertEqual(len(manifest['build']['sv_sources']),4)
            self.assertEqual(manifest['build']['parameters']['AW'],size.bit_length()-1)
            self.assertEqual(manifest['sources'],{p:n.sha(b) for p,b in files.items()})
            self.assertIn(f'reads={4*size}',manifest['steps'][0]['expected_stdout'])
            self.assertNotIn('gcp',str(manifest))
    def test_actual_ram_and_acks_not_grant(self):
        m,f=n.role();s=f[n.SV].decode()
        self.assertIn('genefer_stream27_r15_host_image_ack_v1',s)
        self.assertIn('(!body || host_write_ready)',s)
        self.assertIn('transport_empty && all_acked',s)
        self.assertIn('ack_count==',s)
        self.assertNotIn('host_write_ack)',s.split('wire grant=')[1].split(';')[0])
    def test_runtime_before_dut_and_separate_fault(self):
        normal,f=n.role();fault,_=n.role(mode='fault');cpp=f[n.CPP].decode()
        self.assertLess(cpp.index('C c;'),cpp.index('Vstream27_r15_direct_write_guard d;'))
        self.assertIn('c(a,v),d(&c)',cpp)
        self.assertEqual(normal['steps'][0]['argv'],['{exe}'])
        self.assertEqual(fault['steps'][0]['argv'],['{exe}','--fault'])
        self.assertEqual(fault['test_role'],'deliberate_fault')
    def test_prohibited_shapes(self):
        with self.assertRaises(ValueError):n.role(65536)
    def test_correction_index_explicitly_five_bits_under_guard_range(self):
        for size in (32,256):
            m,f=n.role(size)
            self.assertEqual(m['direct_write']['fixture_version'],2)
            self.assertIn("[5'(bank_index- (AW+2)'(N))]",f[n.SV].decode())
            self.assertEqual([(index-size)&31 for index in range(size,size+32)],list(range(32)))
            self.assertEqual(m['direct_write']['production_pins'],{p:pin for p,pin in n.PINS.items() if p.endswith('.sv')})

if __name__=='__main__':unittest.main()
