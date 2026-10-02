import unittest
from fpga.reference import stream27_p8_r75_continuous_qualification as q

class R75ContinuousQualification(unittest.TestCase):
    def test_exact_full_source_and_own_calendar(self):
        paired,fitted=q.source.full_source()
        for ops in (1,100):
            m,files=q.role(ops)
            self.assertEqual(len(m['build']['sv_sources']),65)
            for n,t in fitted['files'].items():self.assertEqual(files['rtl/'+n],t.encode())
            c=m['continuous']['counts_ordinary_source_projection']
            self.assertEqual(c['candidate_cycles'],680316+(ops-1)*16654)
            self.assertEqual(c['final_rows'],8192)
            self.assertEqual(c['doubles'],0 if ops==1 else 50)
    def test_same_sources_build_and_reference_different_finite_count(self):
        short,sf=q.role(1);pilot,pf=q.role(100)
        for key in ('build','probe','sources'):self.assertEqual(short[key],pilot[key])
        self.assertEqual(sf,pf)
        self.assertEqual(short['steps'][0]['argv'],['{exe}','1'])
        self.assertEqual(pilot['steps'][0]['argv'],['{exe}','100'])
        self.assertNotEqual(short['continuous']['operations'],pilot['continuous']['operations'])
    def test_no_unmeasured_long_or_bool(self):
        for ops in (True,0,99,1000):
            with self.subTest(operations=ops),self.assertRaises(ValueError):q.role(ops)

if __name__=='__main__':unittest.main()
