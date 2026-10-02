import hashlib
import unittest
from fpga.reference import stream27_p8_r75_qualification as q

class R75QualificationTests(unittest.TestCase):
    def test_full_frozen_subset_and_exact_root(self):
        paired,fitted=q.full_source()
        self.assertEqual(len(paired['rtl_sources']),65);self.assertEqual(len(fitted['rtl_sources']),54)
        for n,t in fitted['files'].items():self.assertEqual(paired['files'][n],t)
    def test_own_small_cycles_and_assets(self):
        old,oldfiles=q.donor.role('normal');m,files=q.role('normal')
        self.assertEqual(m['r75_qualification']['geometry']['warm_interval'],129)
        self.assertEqual(m['r75_qualification']['geometry']['carry_done'],130)
        self.assertEqual(m['build']['parameters']['FINAL_GS_INPUTREG'],1)
        self.assertEqual(files['assets/p8-eight-prp-v1.txt'],oldfiles['assets/p8-eight-prp-v1.txt'])
        oldmeta=old['p8_prp_qualification'];meta=m['r75_qualification']['oracle']
        self.assertEqual(meta['operations'],5000)
        for a,b in zip(meta['cases'],oldmeta['cases']):
            for k in ('base','bits','expected','proof','label'):self.assertEqual(a[k],b[k])
            self.assertEqual(a['cycles']-b['cycles'],2*(a['operations']-1)+1)
        self.assertEqual(meta['host_cycles']-oldmeta['host_cycles'],9992)
    def test_normal_driver_arithmetic_unchanged(self):
        old=(q.ROOT/q.donor.NORMAL).read_text()
        new=(q.ROOT/q.CPP).read_text()
        expected=old.replace('// Same frozen eight-case PRP driver, source-bound canonical1 helper only.',
            '// Frozen eight-case driver; private r75 source/calendar-bound helper only.').replace(
                'stream27_p8_canonpipe_helpers_v1.h','stream27_p8_r75_helpers_v1.h').replace('P8_PRP_CASE','P8_R75_PRP_CASE').replace('P8_PRP_PASS','P8_R75_PRP_PASS')
        self.assertEqual(new,expected)
    def test_finite_fault_contract_separate(self):
        m,files=q.role('faults')
        self.assertEqual([s['expected_returncode'] for s in m['steps']],[0,1])
        self.assertIn('reset_ages=10,239',m['steps'][0]['expected_stdout'])
        self.assertIn('feed_abort(d,102+INTERVAL+8,c)',files[q.FAULT].decode())
    def test_invalid_mode(self):
        with self.assertRaises(ValueError):q.role('invented')

if __name__=='__main__':unittest.main()
