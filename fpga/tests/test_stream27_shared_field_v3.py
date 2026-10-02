import unittest
from fpga.reference import stream27_shared_field_v2 as parent
from fpga.reference.stream27_shared_field_v3 import prepare


class SignedHostInput(unittest.TestCase):
    def test_default_probe_and_warm_sources_exact(self):
        for mode in ('probe','warm'):
            for p in (8,16):
                for f in range(3):
                    a=parent.prepare(256,p,f,mode=mode);b=prepare(256,p,f,mode=mode)
                    self.assertEqual(a['files'],b['files']);self.assertEqual(a['top'],b['top'])

    def test_only_negative_one_admission_arithmetic_unchanged(self):
        for n in (32,256):
            for f in range(3):
                a=parent.prepare(n,16,f);b=prepare(n,16,f,mode='warm_signed')
                s=b['files'][b['top']+'.sv'];self.assertIn("data_in[lane*32+:32]!=32'hffffffff",s)
                for name,text in a['files'].items():
                    if name!=a['top']+'.sv':self.assertEqual(b['files'][name],text)

    def test_signed_seed_magnitude_closed_in_existing_coefficient_bound(self):
        for n in (32,256):
            for base in (max(2*n+5,(2*(2*n+24*16)+2)//3+1),1000000000):
                b=base-1;a=[-1 if j%5==0 else (j*17)%base for j in range(n)]
                self.assertTrue(all(abs(v)<=b for v in a))
                c=[0]*n
                for i,x in enumerate(a):
                    for j,y in enumerate(a):c[(i+j)%n]+=x*y*(1 if i+j<n else -1)
                self.assertLessEqual(max(map(abs,c)),n*b*b)


if __name__=='__main__':unittest.main()
