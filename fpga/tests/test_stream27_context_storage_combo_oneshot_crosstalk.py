import copy
import json
import unittest
from fpga.reference import stream27_context_storage_combo_oneshot_crosstalk as c

class Crosstalk(unittest.TestCase):
    def test_exact_production_and_zero_edge_observer(self):
        m,files=c.role(); original=json.loads((c.DONOR/'manifest.json').read_bytes())
        self.assertEqual(m['build']['parameters'],original['build']['parameters'])
        production=[n for n in original['build']['sv_sources'] if n!='rtl/'+original['build']['top']+'.sv']
        self.assertEqual(len(production),55)
        for name in production:
            self.assertEqual(c.sha(files[name]),original['sources'][name])
        self.assertNotRegex(files['rtl/'+c.TOP+'.sv'].decode(),r'\b(always|always_ff|always_comb|initial)\b')
    def test_exact_comparator_scope_and_negatives(self):
        v=dict(aw=16,p=16,contexts=2,bases=c.BASES,squares=4,peer_verified_words=65536,
            mutated_context=0,mutated_address=17,typed_mismatches=1,signed96=True,peer_bit_identical=True,
            metadata_unchanged=True,native_output_word_only=True,model_threads=1,seconds=100.)
        def run(x): return c.validate('R84_C2_CROSSTALK_PASS '+json.dumps(x)+'\n','',0,c.config(),{})
        self.assertEqual(run(v)['status'],'PASS_expected_contracts')
        for key,value in [('peer_verified_words',65535),('typed_mismatches',0),('metadata_unchanged',False),('seconds',float('inf'))]:
            bad=copy.deepcopy(v);bad[key]=value
            with self.assertRaises(ValueError): run(bad)
        with self.assertRaises(ValueError): c.validate('R84_C2_CROSSTALK_PASS '+json.dumps(v)+'\n','',1,c.config(),{})

if __name__=='__main__': unittest.main()
