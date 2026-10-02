import unittest
from pathlib import Path

from fpga.reference.stream27_field_square_warm_full_v1_compile import prepare,term_roots_source
from fpga.reference.stream27_field_square_warm_v4_compile import dependency_contract,comb_blocks
from fpga.reference.stream27_term_context_contract_v1 import replay,table_index
from fpga.reference.stream_ntt_schedule import transform
from fpga.reference.stream_ntt_model import bit_reverse


class WarmFullSourceV1(unittest.TestCase):
    def test_all_sources_present_and_full_geometry_not_native_promotion(self):
        root=Path(__file__).resolve().parents[1]
        for n in (256,65536):
            p=prepare(n,allow_full_constants=n>256);s=p['files'][p['top']+'.sv'];tw=n.bit_length()-4
            self.assertEqual(len(p['files']),7)
            self.assertIn(f'logic [{tw}:0] remaining_input',s)
            self.assertIn(f'.PAYLOAD_W({tw+9})',s)
            self.assertIn('.seed_start(seed_running && seed_issue==0)',s)
            self.assertIn('genefer_stream27_term_context_v1',s)
            self.assertNotIn('term_table',s);self.assertNotIn('seed_capture',s)
            self.assertNotIn('$readmemh',s)
            self.assertIn('term_output_row!=addA_row',s)
            self.assertFalse(p['RTL_qualified']);self.assertFalse(p['native_run_performed'])
            self.assertFalse(p['full_N_numeric_NTT_performed'])
            self.assertIn('wire raw_frame_begin=rst_n &&',s)
            self.assertIn('wire accepted_correction=rst_n &&',s)
            self.assertIn('wire accepted=rst_n &&',s)
            # The frozen bounded checker requires its exact candidate spelling;
            # strip only the added reset guard for the unchanged dependency test.
            dependency_contract((root/'rtl/kernel/genefer_stream27_epoch_protocol_v4.sv').read_text(),
                s.replace('wire raw_frame_begin=rst_n && ','wire raw_frame_begin='))
            for name in p['rtl_sources']:
                self.assertTrue(name in p['files'] or (root/name).is_file(),name)
        self.assertEqual(p['geometry']['interval'],16660)
        self.assertEqual(p['geometry']['next_cache_capture'],24889)
        self.assertEqual(p['geometry']['next_pointwise_accept'],24968)

    def test_full_term_selection_does_not_read_resulting_fault_cone(self):
        root=Path(__file__).resolve().parents[1]
        source=(root/'rtl/kernel/genefer_stream27_term_context_v1.sv').read_text()
        selection=next(block for block in comb_blocks(source) if ': select_current_term' in block)
        for forbidden in ('local_bad','fault_pending','quarantine','out_error','product_accept'):
            self.assertNotIn(forbidden,selection)
        self.assertIn('if(bypass)begin current_term=product_data',selection)
        self.assertIn('seed_slot && update_slot',source)
        self.assertIn('bank_owner[prod_bank]!=product_owner',source)

    def test_N256_complete_math_with_actual_context_reseed_contract(self):
        # Numerical transform work stays at the explicitly allowed N256.
        n=256;rows=n//8;p=104857601;r=1<<32;psi=pow(3,(p-1)//(2*n),p);rinv=pow(r,-1,p)
        digits=[(i*i+17*i+1)%517 for i in range(n)]
        c0=(-516,3,0,40,-9,516,0,11);c1=(0,-17,19,0,704,-704,1,-1)
        tables=[]
        for correction in (c0,c1):
            x=transform(8,8,values=[value*pow(psi,k*rows,p)%p for k,value in enumerate(correction)])['output_values']
            tables.append(tuple(x[bit_reverse(k,3)] for k in range(8)))
        term_rows=replay(256,coefficients=tables[1])['output']
        x=transform(n,8,values=[value*pow(psi,i,p)%p for i,value in enumerate(digits)])['output_values']
        corrected=[]
        for row in range(rows):
            for lane in range(8):corrected.append((x[row*8+lane]+tables[0][table_index(n,row)]+term_rows[row][lane])%p)
        inv=transform(n,8,inverse=True,values=[value*value*rinv%p for value in corrected])['output_values']
        actual=[value*pow(psi,-i,p)*r%p for i,value in enumerate(inv)]
        effective=list(digits)
        for k in range(8):effective[k*rows]+=c0[k];effective[k*rows+1]+=c1[k]
        expected=[0]*n
        for a in range(n):
            for b in range(n):expected[(a+b)%n]=(expected[(a+b)%n]+effective[a]*effective[b]*(1 if a+b<n else -1))%p
        self.assertEqual(actual,expected)

    def test_next_row_root_prefetch_and_bypass_are_explicit(self):
        _,s=term_roots_source(65536)
        self.assertIn("following_target=pw_row+13'd5",s)
        self.assertIn('following_target[12-:3]',s)
        self.assertIn('seed_R_roots=seed_start ?',s)
        self.assertIn('next_seed_R_roots=pw_start ?',s)
        self.assertNotIn('$readmem',s)


if __name__=='__main__':unittest.main()
