from copy import deepcopy
import unittest
from fpga.reference import stream27_shared_field_v4 as parent
from fpga.reference import stream27_montgomery_factored_bind as s

class FactoredBinding(unittest.TestCase):
    def test_off_and_identifier_only_on_all_small_geometries(self):
        for n in (32,256):
            for field in range(3):
                b=parent.prepare(n,16,field,mode='warm',contexts=1)
                saved=deepcopy(b);off=s.bind(b,MONT_FACTORED=0);on=s.bind(b)
                self.assertEqual(off,b);self.assertIsNot(off,b);self.assertIsNot(off['files'],b['files'])
                self.assertEqual(b,saved)
                for key in ('top','geometry','parameters','mode'):
                    self.assertEqual(on[key],b[key])
                self.assertEqual(on['montgomery_factored']['leaf_latency_edges'],3)
                self.assertEqual(on['montgomery_factored']['source_multiplier_delta'],0)
                for name,text in b['files'].items():
                    if name in on['montgomery_factored']['removed_definitions']:continue
                    if name not in on['montgomery_factored']['identifier_changes']:
                        self.assertEqual(on['files'][name],text)
                self.assertTrue(set(b['source_dependencies'])<=set(on['source_dependencies']))
    def test_rejects_wrong_flag_leaf_drift_generated_drift_and_double_binding(self):
        b=parent.prepare(32,16,0)
        for flag in (-1,2,True,'1'):
            with self.assertRaises(ValueError):s.bind(b,MONT_FACTORED=flag)
        for name in s.LEAVES:
            corrupt=deepcopy(b);corrupt['files'][name+'.sv']+='\n'
            corrupt['generated_sha256'][name+'.sv']=s.sha(corrupt['files'][name+'.sv'].encode())
            with self.assertRaises(ValueError):s.bind(corrupt)
        corrupt=deepcopy(b);corrupt['generated_sha256'][b['top']+'.sv']='0'*64
        with self.assertRaises(ValueError):s.bind(corrupt)
        with self.assertRaises(ValueError):s.bind(s.bind(b))

if __name__=='__main__':unittest.main()
