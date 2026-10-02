import json,unittest
from fpga.reference import anext_upper_qualification_v1 as q
from fpga.reference import anext_upper_small_prp_v1 as p
from fpga.reference.anext_upper_soak_output_v1 import normalise
from fpga.tests.test_anext_soak_v1 import fixture

class UpperQualification(unittest.TestCase):
    def test_exact_delta(self):
        self.assertTrue(q.verify()['reset_reload_loop_unchanged'])
        t=q.expected()['rtl/tb/anext_upper_soak_v1.cpp']
        self.assertEqual(t.count('d.rst_n=0;'),1)
        self.assertIn('No reset/reload between operations',t)
    def test_small_retained_arrays_and_cycles(self):
        text,oracle,ref,err,rc=fixture();rows=[]
        for line in text.splitlines():
            prefix,raw=line.split(' ',1);r=json.loads(raw)
            if prefix=='ANEXT_SOAK_STEP':r['cycles']+=1;r['ntt']+=1
            if prefix=='ANEXT_SOAK_PASS':r['cycles']+=r['operations']
            rows.append(prefix+' '+json.dumps(r))
        good='\n'.join(rows)+'\n';converted,metrics=normalise(good,oracle,ref)
        self.assertEqual(ref.validate_rows(converted,err,rc,{'negative':'none'},oracle)['operations'],4)
        self.assertEqual(metrics['cold_prefill'],2)
        with self.assertRaises(ValueError):normalise(text,oracle,ref)
        with self.assertRaises(ValueError):normalise(good.replace('"prefill": 12','"prefill": 0',1),oracle,ref)
    def test_prp_assets_preserved(self):
        from fpga.reference.anext_small_prp_v1 import corpus
        self.assertEqual(p.corpus(),corpus())
        self.assertIn("wanted=207+(c['operations']-1)*184",q.expected()['reference/anext_upper_small_prp_v1.py'])
        with self.assertRaises(ValueError):p.validate('', '', True, {'mode':'normal'},dict(zip(('corpus','oracle'),(p.corpus()[0],json.dumps(p.corpus()[1])))))

if __name__=='__main__':unittest.main()
