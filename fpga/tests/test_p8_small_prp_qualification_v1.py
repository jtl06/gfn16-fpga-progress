import unittest
from fpga.reference import p8_small_prp_qualification_v1 as m

class P8Corpus(unittest.TestCase):
    def test_complete_prps(self):
        text,meta,expected=m.corpus()
        self.assertEqual(meta['operations'],5000)
        self.assertEqual(meta['host_cycles'],637672)
        self.assertEqual(sum(c['label']=='prime' for c in meta['cases']),3)
        self.assertEqual(min(c['base'] for c in meta['cases']),173)
        self.assertEqual(meta['base_floor'],172)
        for c in meta['cases']:
            self.assertEqual(int(''.join(map(str,c['bits'])),2),c['base']**32)
        self.assertIn('reads=256',expected)
        self.assertTrue(text.startswith('5 8\n'))
    def test_proof_rejects_wrong_factor(self):
        with self.assertRaises(ValueError):m.oracle.prove_label(173,'composite',7)
    def test_normal_does_not_execute_faults(self):
        cpp=(m.ROOT/m.CPP).read_text()
        self.assertNotIn('feed_fault(',cpp)
        self.assertNotIn('feed_abort(',cpp)
        self.assertIn('long_production(d,p);long_compare(d,p,c)',cpp)
        self.assertEqual(cpp.count('reset(d);'),1)

if __name__=='__main__':unittest.main()
