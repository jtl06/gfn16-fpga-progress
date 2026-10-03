import unittest
from fpga.reference import stream27_context_storage_combo_faultlocal_native as n

class FaultLocalNativeTests(unittest.TestCase):
    def test_small_normal_exact_contract(self):
        old,files,parent=n.capture('aw8')
        m,new,b=n.role('aw8')
        self.assertEqual(m['steps'],old['steps'])
        self.assertEqual(m['probe'],old['probe'])
        self.assertEqual(new[old['build']['cpp_source']],files[old['build']['cpp_source']])
        self.assertEqual(m['build']['parameters'],dict(old['build']['parameters'],COMM_OWNER_COMPARE_LOCAL=1))
        self.assertEqual(b['geometry'],parent['geometry'])
        self.assertEqual(len(b['files']),55)
        self.assertEqual(b['context_storage_combo_faultlocal']['stage_instances'],24)
        for name,pin in b['source_sha256'].items():
            self.assertEqual(n.sha(new['lineage/'+name]),pin)
    def test_no_wrong_tool_identity(self):
        source=(n.ROOT/n.SELF).read_text()
        self.assertIn("tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1'",source)
        self.assertNotIn('verilator6032',source)
    def test_full_transparent_observer_and_exact_normal_contract(self):
        old,files,parent=n.capture('full')
        m,new,b=n.role('full')
        self.assertEqual(m['steps'],old['steps'])
        self.assertEqual(m['probe'],old['probe'])
        self.assertEqual(new[old['build']['cpp_source']],files[old['build']['cpp_source']])
        self.assertEqual(m['build']['parameters'],dict(old['build']['parameters'],COMM_OWNER_COMPARE_LOCAL=1))
        self.assertEqual(b['geometry'],parent['geometry'])
        self.assertEqual(b['context_storage_combo_faultlocal']['stage_instances'],72)
        self.assertEqual(len(m['build']['sv_sources']),56)
        text=new['rtl/'+m['build']['top']+'.sv'].decode()
        self.assertNotRegex(text,r'\b(always|always_ff|always_comb|initial)\b')
        self.assertEqual(text.count('.COMM_OWNER_COMPARE_LOCAL(COMM_OWNER_COMPARE_LOCAL)'),1)

if __name__=='__main__':unittest.main()
