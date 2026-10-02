import unittest
from fpga.reference import anext_writeback_soak_portable_duration_v1 as d

class ActualAzureF3Duration(unittest.TestCase):
    def test_actual_target_role_and_namespace(self):
        self.assertIn('anext-writeback-continuous-portable-role-v1', str(d.base.ROLE))
        self.assertIn('anext-writeback-pilot-portable-role-v1', str(d.base.PILOT_ROLE))
        self.assertEqual(d.base.ROLE_SHA, 'c4fdb4b4a64ff1cb33aed03a66be4dd18a79b6ca9e899b2cc877c3d9d1fea2f7')
        self.assertIs(d.predict.__globals__, d.base.__dict__)
        self.assertIn('compatible_hosts=[r[', d.text)
        self.assertIn("native['actual_reference_host']==r['host']", d.text)
        self.assertIn("native['actual_runtime_manifest_sha256']==TARGETS[r['host']][1]", d.text)
        self.assertNotIn("r['host']=='gfn16-pilot-c4d'", d.text)

    def test_same_F3_arithmetic_but_not_older_candidate_count(self):
        value=d.predict(400.0,2194717,17.0)
        self.assertEqual(value['continuous_model_ticks'],21947089)
        self.assertEqual(value['margin'],1.75)
        with self.assertRaises(ValueError):d.predict(400.0,2191417,17.0)
        with self.assertRaises(ValueError):d.predict(float('inf'),2194717,17.0)

if __name__=='__main__':
    unittest.main()
