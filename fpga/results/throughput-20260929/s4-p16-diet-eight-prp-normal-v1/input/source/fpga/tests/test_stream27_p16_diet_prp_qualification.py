"""Only small N32 ordinary integers, source metadata and textual contracts."""
import unittest
from fpga.reference import stream27_p16_diet_prp_qualification as s


class P16DietPRP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.manifest,cls.files=s.role()

    def test_eight_own_proved_labels_full_small_prps(self):
        meta=self.manifest['p16_diet_prp_qualification'];cases=meta['cases']
        self.assertEqual(len(cases),8);self.assertEqual(meta['base_floor'],300)
        self.assertEqual([c['base'] for c in cases[:2]],[300,301])
        self.assertEqual(sum(c['label']=='prime' for c in cases),3)
        for c in cases:
            b=c['base'];e=b**32
            self.assertEqual(c['bits'],list(map(int,bin(e)[2:])))
            self.assertEqual(s.oracle.decode(c['expected'],b),pow(2,e,e+1))
            self.assertEqual(c['cycles'],102+(len(c['bits'])-1)*161+161+2+
                             (10 if c['expected'][0]==-1 else 9)*32+32+4)
            s.oracle.prove_label(b,c['label'],next(x[2] for x in s.SPEC if x[0]==b))
        self.assertEqual(meta['operations'],sum(c['operations'] for c in cases))
        self.assertEqual(meta['host_cycles'],sum(c['cycles'] for c in cases))

    def test_exact_diet69_source_own_configuration(self):
        m=self.manifest;self.assertEqual(len(m['build']['sv_sources']),69)
        self.assertEqual(m['build']['parameters']['P'],16)
        for key,value in (('CORR_SERIAL_BFS',2),('COMM_STAGE_SHARED_MLAB',1),('MONT_FACTORED',1)):
            self.assertEqual(m['build']['parameters'][key],value)
        for name in m['build']['sv_sources']:
            self.assertEqual(s.sha(self.files[name]),m['p16_diet_prp_qualification']['generated_sha256'][name[4:]])
        cfg=self.files[s.CONFIG].decode()
        self.assertIn('MIN_BASE=300,INTERVAL=161,CARRY_DONE=161',cfg)
        self.assertIn('FIRST_DIGIT=156',cfg);self.assertIn('constexpr unsigned P=16;',cfg)
        self.assertEqual(m['probe']['expected_json'],dict(context_threads=1,model_threads=1,expected_threads=1))
        self.assertTrue(m['p16_diet_prp_qualification']['old_native_results_not_inherited'])

    def test_same_numeric_assertions_one_load_per_chain_and_all96(self):
        cpp=self.files[s.CPP].decode();helper=self.files[s.HELPER].decode();scalar=self.files[s.SCALAR].decode()
        self.assertEqual(cpp.count('reset(d);'),1)
        self.assertEqual(cpp.count('load(d,p.initial);'),1)
        body=helper[helper.index('for(uint64_t elapsed=1;'):helper.index('need(next==count')]
        for bad in ('reset(d)','load(d,','d.read_en=1','production('):self.assertNotIn(bad,body)
        self.assertIn('S4_LONG_POW_TYPED',helper);self.assertIn('S4_LONG_T5B_SIGNED96_EQUALITY',helper)
        self.assertIn('x[1]==sign&&x[2]==sign',scalar)
        self.assertIn('(special?10u:9u)*N',helper)
        rows=self.manifest['steps'][0]['expected_stdout'].splitlines()
        self.assertEqual(len(rows),9)
        self.assertEqual(sum(row.startswith('P16_PRP_CASE ') for row in rows),8)
        self.assertIn('rows=16 reads=256',rows[-1])
        self.assertIn('base_floor=300',rows[-1])

    def test_reject_wrong_small_calendar(self):
        geometry=dict(self.manifest['p16_diet_prp_qualification']['geometry'])
        for key in ('first_digit','warm_interval','carry_done','feedback_delay'):
            wrong=dict(geometry);wrong[key]+=1
            with self.subTest(field=key),self.assertRaises(ValueError):s.corpus(wrong)


if __name__=='__main__':unittest.main()
