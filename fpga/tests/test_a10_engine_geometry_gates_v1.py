from pathlib import Path
import unittest
from fpga.reference import a10_engine_geometry_gates_v1 as gates
from fpga.reference import merged_negacyclic27_model as math

def conventional(a,f,inverse=False):
    n=len(a);data=list(a);psi=math.psi_for(n,f);omega=psi*psi%f.p
    if not inverse:
        data=[x*pow(psi,j,f.p)%f.p for j,x in enumerate(data)];span=n
        while span>=2:
            half=span//2;step=pow(omega,n//span,f.p)
            for start in range(0,n,span):
                w=1
                for j in range(half):
                    u,v=data[start+j],data[start+j+half]
                    data[start+j]=(u+v)%f.p;data[start+j+half]=(u-v)*w%f.p;w=w*step%f.p
            span//=2
    else:
        span=2
        while span<=n:
            half=span//2;step=pow(omega,-n//span,f.p)
            for start in range(0,n,span):
                w=1
                for j in range(half):
                    u,t=data[start+j],data[start+j+half]*w%f.p
                    data[start+j]=(u+t)%f.p;data[start+j+half]=(u-t)%f.p;w=w*step%f.p
            span*=2
        data=[x*pow(n,-1,f.p)*pow(psi,-j,f.p)%f.p for j,x in enumerate(data)]
    return data

class GeometryTests(unittest.TestCase):
    def test_unchanged_parent_and_exact_bench_generation(self):
        gates.source_guard()
        self.assertEqual((gates.ROOT/gates.BENCH).read_text(),gates.bench_source())
        self.assertIn('if constexpr(AW<=8)',gates.bench_source())
        self.assertIn('A10_INDEPENDENT_SMALL_ORACLE_AGREEMENT',gates.bench_source())
        self.assertIn('A10_INDEPENDENT_SMALL_CONVOLUTION_AGREEMENT',gates.bench_source())

    def test_three_field_small_independent_transform(self):
        for n in (32,256):
            for f in math.FIELDS:
                a=[(j*2654435761+104729)%f.p for j in range(n)]
                spectrum=conventional(a,f)
                self.assertEqual(spectrum,math.direct_spectrum(a,f))
                self.assertEqual(conventional(spectrum,f,True),a)
                squared=[x*x%f.p for x in spectrum]
                self.assertEqual(conventional(squared,f,True),math.field_square(a,f))

    def test_symbolic_aw8_rom_bank_geometry_and_full_source_only(self):
        expected={5:(1,50,8,31,0,540),8:(2,88,11,256,14,935),16:(512,8336,1031,69632,7680,88515)}
        for aw,wanted in expected.items():
            r=gates.ledger(aw)
            self.assertEqual(tuple(r[k] for k in ['groups','transform_cycles','point_cycles','roots_per_transform','ROM_reads_per_transform','engine_work_cycles']),wanted)
        self.assertEqual(gates.ledger(16)['residues'],983040)
        self.assertEqual(gates.ledger(16)['whole_controller_ntt_cycles'],17709)
        with self.assertRaisesRegex(ValueError,'A10_NATIVE_GEOMETRY'):gates.ledger(9)

if __name__=='__main__':unittest.main()
