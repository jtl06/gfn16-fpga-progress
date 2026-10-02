import unittest
from fpga.reference.stream27_field_probe_variants_v1 import compile_probe,accounting
from fpga.reference.stream27_field_compile_param_v1 import compile_transform,topology
from fpga.reference.stream27_field_compile import compile_transform as frozen_transform
from fpga.reference.stream27_field_physical_probe_v1 import compile_probe as frozen_probe
from fpga.reference.stream_ntt_model import FIELDS
from fpga.reference.stream_ntt_schedule import transform


class ProbeVariantTests(unittest.TestCase):
    def test_p8_exact_math_and_control(self):
        for inverse in (False,True):
            a=compile_transform(32,inverse=inverse);b=frozen_transform(32,inverse=inverse)
            self.assertEqual(a['source'],b['source']);self.assertEqual(a['rom_files'],b['rom_files'])
        a=compile_probe(32);b=frozen_probe(32)
        for name in a['files'].keys()&b['files'].keys():
            expected=b['files'][name]
            if '_dif_' in name or '_dit_' in name:expected=expected.replace('genefer_stream27_mdc_commutator_slots_v2','genefer_stream27_mdc_commutator_slots_sm1_v1')
            self.assertEqual(a['files'][name],expected,name)
        self.assertTrue(all(value==b['calendar'][key] for key,value in a['calendar'].items()))
        self.assertEqual(a['calendar']['first_terminal_sample'],82)

    def test_p16_canonical_domains_against_schoolbook(self):
        for field,(prime,generator) in enumerate(FIELDS):
            n=32;psi=pow(generator,(prime-1)//(2*n),prime);rinv=pow(1<<32,-1,prime)
            values=[(i*i+13*i+7)%prime for i in range(n)]
            x=transform(n,16,field=field,values=[v*pow(psi,i,prime)%prime for i,v in enumerate(values)])['output_values']
            inv=transform(n,16,field=field,inverse=True,values=[v*v*rinv%prime for v in x])['output_values']
            actual=[v*pow(psi,-i,prime)*(1<<32)%prime for i,v in enumerate(inv)]
            expected=[0]*n
            for i in range(n):
                for j in range(n):expected[(i+j)%n]=(expected[(i+j)%n]+values[i]*values[j]*(1 if i+j<n else -1))%prime
            self.assertEqual(actual,expected)
            b=compile_probe(n,field,16,False)
            self.assertIn('[431:0] data_in',b['files'][b['top']+'.sv'])
            for inverse in (False,True):
                text=compile_transform(n,field,16,inverse=inverse)['source']
                self.assertIn('logic [7:0] bf_valid;',text)
                self.assertIn('sh_generation[7]!=sh_generation[0]',text)
                self.assertNotIn('bf_valid!={4{',text)

    def test_full_geometry_no_numeric(self):
        for p,count,bits in ((8,80,37696),(16,160,75392)):
            s=accounting(65536,p,[],True)
            self.assertEqual(s['small_M20K_arrays_replaced'],count)
            self.assertEqual(s['additional_register_data_bits'],bits)
            self.assertEqual(s['DSP_proxy'],p*19)
            self.assertEqual(topology(65536,p)['p'],p)
        with self.assertRaises(ValueError):compile_probe(65536,parallelism=16)


if __name__=='__main__':unittest.main()
