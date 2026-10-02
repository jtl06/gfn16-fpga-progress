import json
from pathlib import Path
import tempfile
import unittest

from fpga.reference.stream27_field_physical_probe_v1 import compile_probe,prepare,verify_project,embedded_rom
from fpga.reference.stream27_field_plan import topology
from fpga.reference.stream_ntt_model import bit_reverse,FIELDS
from fpga.reference.stream_ntt_schedule import transform


class FieldPhysicalProbeV1(unittest.TestCase):
    def test_full_constants_require_explicit_source_authority(self):
        with self.assertRaisesRegex(ValueError,'EXPLICIT_AUTHORITY'):compile_probe(65536)
        for aw in (5,16):
            p=topology(1<<aw);physical=14+2*p['first_output_edge']
            self.assertEqual(physical,(82 if aw==5 else 16612))

    def test_exact_small_datapath_domains_and_order(self):
        n=32
        for field,(prime,generator) in enumerate(FIELDS):
            psi=pow(generator,(prime-1)//(2*n),prime);r=1<<32;rinv=pow(r,-1,prime)
            values=[(i*i+13*i+7)%prime for i in range(n)]
            x=transform(n,8,field=field,values=[value*pow(psi,i,prime)%prime for i,value in enumerate(values)])['output_values']
            squares=[value*value*rinv%prime for value in x]
            inv=transform(n,8,field=field,inverse=True,values=squares)['output_values']
            actual=[value*n%prime*pow(psi,-i,prime)*pow(n,-1,prime)*r%prime for i,value in enumerate(inv)]
            expected=[0]*n
            for a in range(n):
                for b in range(n):expected[(a+b)%n]=(expected[(a+b)%n]+values[a]*values[b]*(1 if a+b<n else -1))%prime
            self.assertEqual(actual,expected)
            p=compile_probe(n,field);source=p['files'][p['top']+'.sv']
            self.assertIn('pointwise_square',source);self.assertIn('fused_untwist_normalize',source)
            self.assertNotIn('epoch_protocol',source);self.assertEqual(p['calendar']['first_terminal_sample'],82)
            self.assertEqual(sum(r['period']*r['width']//27 for r in p['rom_ledger']),118)

    def test_embedded_rom_prefetch_shape_no_unpinned_hex(self):
        p=compile_probe(32);rom=p['files']['genefer_stream27_p2_initialized_roms_aw5_f0_v1.sv']
        self.assertNotIn('$readmem',rom);self.assertIn('ramstyle = "M20K"',rom)
        self.assertIn('if(rst_n && in_slot_valid)prefetched<=roots[following_row]',rom)
        self.assertIn('frame_start ? 216\'h',rom)
        self.assertEqual(p['resource_basis']['DSP_proxy'],64)
        self.assertFalse(p['full_N_numeric_NTT_performed'])

    def test_portable_project_closure_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'new';r=prepare(path,n=32);project=path/'project'
            self.assertEqual(verify_project(project)['status'],'passed_source_closure_only')
            m=json.loads((project/'manifest.json').read_text())
            self.assertFalse(m['bitstream_generation']);self.assertFalse(m['warm_control_qualified'])
            qsf=(project/'probe.qsf').read_text()
            self.assertIn('SEED 1',qsf);self.assertIn('VIRTUAL_PIN ON -to {data_in[*]}',qsf)
            self.assertIn('period 10',(project/'probe.sdc').read_text())
            self.assertEqual(set(r['project_input_sha256']),{'manifest.json','probe.qsf','probe.qpf','probe.sdc','run.tcl',*('rtl/'+k for k in m['source_sha256'])})
            # Temporary generated artifact only, not a live/frozen source edit.
            (project/'probe.sdc').write_text('bad clock\n')
            with self.assertRaisesRegex(ValueError,'CONTROL_DRIFT'):verify_project(project)


if __name__=='__main__':unittest.main()
