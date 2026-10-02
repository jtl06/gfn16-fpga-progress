import hashlib
import unittest

from fpga.reference.stream27_shared_field_v1 import (
    geometry,prepare,term_index,term_roots_source,term_weight)
from fpga.reference.stream_ntt_model import FIELDS,bit_reverse
from fpga.reference.stream27_p16c_physical_probe_v1 import compile_probe


class SharedWarm(unittest.TestCase):
    def test_same_transform_sources_in_probe_and_warm(self):
        for p in (8,16):
            for field in range(3):
                warm=prepare(256,p,field);probe=prepare(256,p,field,mode='probe')
                for name,text in probe['files'].items():
                    if name.startswith(('genefer_stream28_merged_','genefer_stream27_square_')):
                        self.assertEqual(warm['files'][name],text)
                self.assertEqual(probe['files'],compile_probe(256,p,field)['files'])
                self.assertEqual(warm['parameters'],dict(AW=8,P=p,CONTEXTS=1,FIELD=field))
                self.assertFalse(warm['full_N_numeric_NTT_performed'])

    def test_parameter_guards_and_full_size_geometry(self):
        with self.assertRaisesRegex(ValueError,'CONTEXTS1'):
            prepare(256,contexts=2)
        with self.assertRaisesRegex(ValueError,'T_GE_P'):
            geometry(64,16)
        g=geometry()
        self.assertEqual((g['physical_first'],g['sink_accept'],g['warm_interval'],g['cache_margin']),
            (8415,8416,8459,66))
        self.assertEqual(geometry(256)['correction_cache_latency'],42)

    def test_segmented_term_matches_direct_root_in_all_fields(self):
        # Scalar term/root proof, no NTT. Exercise the short AW8 segments and
        # the registered four-edge feedback/reseed boundary at larger N.
        for p in (8,16):
            for n in (256,512,1024,2048):
                for field,(prime,g) in enumerate(FIELDS):
                    rows=n//p;rw=n.bit_length()-1-(p.bit_length()-1)
                    omega=pow(g,(prime-1)//n,prime);Rinv=pow(1<<32,-1,prime)
                    coefficients=[(k*k+11*k+7)%prime for k in range(p)]
                    terms=[tuple(coefficients[term_index(n,p,r)]*term_weight(n,p,field,r,l)*Rinv%prime
                                 for l in range(p)) for r in range(rows)]
                    for row in range(rows-4):
                        target=row+4
                        if term_index(n,p,row)==term_index(n,p,target):
                            delta=bit_reverse(target,rw)-bit_reverse(row,rw)
                            factor=pow(omega,delta,prime)*(1<<32)%prime
                            self.assertEqual(tuple(x*factor*Rinv%prime for x in terms[row]),terms[target])
                        else:
                            self.assertNotEqual(row>>(rw-(p.bit_length()-1)),target>>(rw-(p.bit_length()-1)))
                    name,source=term_roots_source(n,p,field)
                    self.assertIn(name,source)
                    self.assertNotIn('next_coeff/old',source)

    def test_source_inventory_and_registered_terminal_rules(self):
        b=prepare(256);top=b['files'][b['top']+'.sv']
        self.assertIn('in_slot_valid(addA_slot && term_join_valid)',top)
        self.assertIn('if(protocol_commit)begin commit_valid<=1',top)
        self.assertNotIn('&& !fault_pending',top)
        self.assertIn('protocol_pw_row',top)
        self.assertTrue(all(hashlib.sha256(text.encode()).hexdigest()==b['generated_sha256'][name]
                            for name,text in b['files'].items()))
        self.assertIn('genefer_stream27_term_context_param_v1.sv',b['rtl_sources'])
        self.assertIn('genefer_stream27_row_arithmetic_param_v1.sv',b['rtl_sources'])

    def test_small_dif_input_is_static_bit_reversed_natural_corrections(self):
        # The N=P special case still consumes reverse(lane,PW)*T+row.
        # Natural c0/c1 pins need the same static input-lane permutation as
        # the full transform. The missing permutation was native v1's bug.
        for p in (8,16):
            b=prepare(256,p);top=b['files'][b['top']+'.sv'];pw=p.bit_length()-1
            for lane in range(p):
                block=bit_reverse(lane,pw)
                self.assertIn(f'ordered_c0[{32*lane}+:32]=c0_in[{32*block}+:32]',top)
                self.assertIn(f'ordered_high[{32*lane}+:32]=high_correction[{32*block}+:32]',top)


if __name__=='__main__':unittest.main()
