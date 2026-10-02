import unittest
from fpga.reference.stream27_threefield_carry_v1 import prepare
from fpga.reference.stream27_shared_field_v2 import prepare as field
from fpga.reference.stream_ntt_blockcarry_model import proposal
from fpga.reference.stream27_threefield_carry_native_v2 import serial_bench


class ThreeFieldSource(unittest.TestCase):
    def test_exact_fields_real_components_and_static_natural_route(self):
        for n in (32,256):
            b=prepare(n);s=b['files'][b['top']+'.sv']
            for f in range(3):
                a=field(n,16,f)
                for name,text in a['files'].items():self.assertEqual(b['files'][name],text)
                self.assertIn(a['top']+' #(.AW(AW),.P(P),.CONTEXTS(CONTEXTS))',s)
            self.assertIn('genefer_crt3_27_mont_pipe crt',s)
            self.assertIn('genefer_track_a4_setup_v1 #(.AW(AW)) shared_setup',s)
            self.assertIn('genefer_track_a4_blockcarry_lane_v1 #(.AW(AW)) carry',s)
            self.assertIn('wire signed [32:0] signed_low',s)
            self.assertIn("32'(-signed_low)",s)
            self.assertEqual(b['parameters']['P'],16)

    def test_no_silent_carry_geometry_fallback(self):
        with self.assertRaises(ValueError):prepare(256,8)
        with self.assertRaises(ValueError):prepare(32,16,contexts=2)

    def test_independent_serial_carry_small_seed_chains(self):
        for n in (32,256):
            base=1000000000;p=16;t=n//p;bound=2*n+24*p;modulus=base**n+1
            for kind,count in ((0,1),(1,4),(2,4),(3,2),(4,2)):
                digits=[];state=0x3b7a901d+kind
                for j in range(n):
                    state=(1664525*state+1013904223)&0xffffffff
                    digits.append(int(j in (n-1,3)) if kind==1 else state%base if kind in (2,3) else 0)
                c0=[b%5-2 if kind in (2,3) else 0 for b in range(p)]
                c1=[b%3-1 if kind in (2,3) else 0 for b in range(p)]
                if kind==3:
                    c0=[(base-1)*(1 if b&1 else -1) for b in range(p)]
                    c1=[bound*(1 if b&1 else -1) for b in range(p)]
                if kind==4:c0[0]=-1
                x=proposal.BlockState(tuple(digits),base,tuple(c0),tuple(c1))
                for i in range(count):
                    a=x.effective();c=[0]*n
                    for j,v in enumerate(a):
                        for k,w in enumerate(a):c[(j+k)%n]+=v*w*(1 if j+k<n else -1)
                    if kind==2 and i&1:c=[2*v for v in c]
                    direct=sum(v*base**j for j,v in enumerate(a))%modulus
                    serial,_=proposal.carry_serial(c,base,p);split,_=proposal.carry_split(c,base,p)
                    self.assertEqual(serial,split)
                    represented=sum(v*base**j for j,v in enumerate(serial.effective()))%modulus
                    self.assertEqual(represented,direct*direct*(2 if kind==2 and i&1 else 1)%modulus)
                    x=serial


if __name__=='__main__':unittest.main()
