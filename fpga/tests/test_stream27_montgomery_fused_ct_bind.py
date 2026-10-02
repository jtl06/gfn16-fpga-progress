from copy import deepcopy
import unittest
from fpga.reference import stream27_shared_field_v4 as parent
from fpga.reference import stream27_montgomery_factored_bind as factored
from fpga.reference import stream27_montgomery_fused_ct_bind as s


class CTOnlyBinding(unittest.TestCase):
    def test_forward_identifier_only_all_small_fields_and_exact_boundaries(self):
        for n in (32,256):
            for field in range(3):
                base=factored.bind(parent.prepare(n,16,field,mode='warm',contexts=1));saved=deepcopy(base)
                off=s.bind(base,CT_FUSED_REDUCTION=0);on=s.bind(base)
                self.assertEqual(base,saved);self.assertEqual(off,base);self.assertIsNot(off['files'],base['files'])
                metadata=on['montgomery_fused_ct'];changed=set(metadata['identifier_changes'])
                self.assertEqual(len(changed),1)
                self.assertEqual(metadata['forward_instances'],(n.bit_length()-1)*8)
                self.assertEqual((metadata['scalar_latency_edges'],metadata['II']),(5,1))
                for name,text in base['files'].items():
                    if name not in changed:self.assertEqual(on['files'][name],text)
                self.assertTrue(any('canonical_spectrum' in text for text in base['files'].values()))
                self.assertTrue(any('canonical_u0' in text and 'canonical_v0' in text for text in base['files'].values()))
                self.assertFalse(metadata['GS_changed']);self.assertFalse(metadata['calendar_changed'])
                for key in ('top','geometry','parameters','mode'):self.assertEqual(on[key],base[key])

    def test_wrong_baseline_form_hash_and_double_binding_rejected(self):
        original=parent.prepare(32,16,0,mode='warm',contexts=1);base=factored.bind(original)
        with self.assertRaises(ValueError):s.bind(original)
        for flag in (-1,2,True,'1'):
            with self.assertRaises(ValueError):s.bind(base,CT_FUSED_REDUCTION=flag)
        corrupt=deepcopy(base);name=next(name for name in corrupt['files'] if name.startswith('genefer_stream28_merged_ct_'))
        corrupt['files'][name]=corrupt['files'][name].replace(".gs(1'b0)",".gs(1'b1)",1)
        corrupt['generated_sha256'][name]=s.sha(corrupt['files'][name].encode())
        with self.assertRaises(ValueError):s.bind(corrupt)
        corrupt=deepcopy(base);corrupt['generated_sha256'][name]='0'*64
        with self.assertRaises(ValueError):s.bind(corrupt)
        with self.assertRaises(ValueError):s.bind(s.bind(base))


if __name__=='__main__':unittest.main()
