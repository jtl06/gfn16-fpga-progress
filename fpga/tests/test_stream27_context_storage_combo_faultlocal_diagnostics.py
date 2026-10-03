import json
import unittest
from fpga.reference import stream27_context_storage_combo_faultlocal_crosstalk as c
from fpga.reference import stream27_context_storage_combo_faultlocal_full_wrap as w
class DiagnosticTests(unittest.TestCase):
    def test_crosstalk_preserves_all_production55_and_parameters(self):
        m,files=c.role();old=json.loads((c.DONOR/'manifest.json').read_bytes())
        self.assertEqual(m['build']['parameters'],old['build']['parameters'])
        self.assertEqual(m['build']['parameters']['COMM_OWNER_COMPARE_LOCAL'],1)
        for name in old['build']['sv_sources']:
            if name!='rtl/'+old['build']['top']+'.sv':self.assertEqual(c.sha(files[name]),old['sources'][name])
        self.assertNotRegex(files['rtl/'+c.TOP+'.sv'].decode(),r'\b(always|always_ff|always_comb|initial)\b')
    def test_wrap_preserves_r7_graph_and_only_forces_host_timestamp(self):
        m,files=w.role()
        cap=w.ROOT/'results/throughput-20260929/trackS-c2-storage-combo-faultlocal-native-v1/full-normal'
        old=json.loads((cap/'manifest.json').read_bytes())
        self.assertEqual(m['build']['parameters'],old['build']['parameters'])
        observer='rtl/'+m['build']['top']+'.sv'
        for name in old['build']['sv_sources']:
            if name!=observer:self.assertEqual(w.sha(files[name]),old['sources'][name])
        self.assertNotRegex(files[observer].decode(),r'\b(always|always_ff|always_comb|initial)\b')
        cpp=files[w.CPP].decode()
        self.assertEqual(cpp.count('d.cycles='),1)
        self.assertIn('age==20000||age==20004||age==20008',cpp)
        self.assertIn('R7_FULL_REAL_TABLE_OWNERS',cpp)
        self.assertEqual(len(m['build']['sv_sources']),56)
if __name__=='__main__':unittest.main()
