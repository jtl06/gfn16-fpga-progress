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

    def test_separate_fault_source_and_post_execution_oracle_negative(self):
        m,files=s.role('faults');cpp=files[s.FAULT].decode();meta=m['p16_diet_whole_host_faults']
        self.assertEqual(meta['descriptor_codes'],[1,2,3,4]);self.assertEqual(meta['reset_ages'],[10,271])
        self.assertEqual([row['expected_returncode'] for row in m['steps']],[0,1])
        self.assertLess(cpp.index('chain_run(d,p,false,c);'),cpp.index('if(negative)p.expected[0]=0;'))
        self.assertLess(cpp.index('long_production(d,p);'),cpp.index('if(negative)p.expected[0]=0;'))
        self.assertIn('p.initial[16]=1;p.expected[0]=-1;p.bits={0}',cpp)
        self.assertEqual(pow(300**16,2,300**32+1),300**32)
        self.assertIn('for(unsigned type=0;type<4;++type)',cpp)
        self.assertIn('feed_abort(d,102+INTERVAL+8,c)',cpp)

    def test_aw8_own_dense_state_feedback18_and_independent_pow(self):
        m,files=s.role('aw8');meta=m['p16_diet_aw8_qualification'];b=meta['base'];mod=b**256+1
        self.assertEqual((meta['geometry']['warm_interval'],meta['geometry']['carry_done'],meta['geometry']['first_digit'],meta['geometry']['feedback_delay']),(212,212,193,18))
        self.assertEqual(meta['operations'],256);self.assertEqual(len(meta['initial']),256)
        self.assertEqual((meta['initial'][3],meta['initial'][-1]),(-1,-1))
        value=sum(v*b**i for i,v in enumerate(meta['initial']))%mod
        for bit in meta['bits']:value=value*value*(1<<bit)%mod
        self.assertEqual(tuple(meta['expected']),s.integers.image(value,b,256))
        self.assertEqual(meta['candidate_cycles'],56940)
        self.assertEqual(m['build']['parameters']['AW'],8)
        self.assertIn(b'AW=8,N=256,MIN_BASE=599,INTERVAL=212,CARRY_DONE=212',files[s.CONFIG])
        self.assertEqual(m['steps'][0]['expected_returncode'],0)
        self.assertIn('feedback_rows=18',m['steps'][0]['expected_stdout'])

    def test_timing7_own75_same_inputs_not_inherited_native_result(self):
        baseline,old=s.role();timed,files=s.role('normal',1)
        self.assertEqual(len(timed['build']['sv_sources']),75)
        for key in s.TIMING_FLAGS:self.assertEqual(timed['build']['parameters'][key.upper()],1)
        self.assertEqual(files[s.ASSET],old[s.ASSET])
        self.assertEqual(timed['p16_diet_prp_qualification']['host_cycles'],826737)
        self.assertEqual(timed['p16_diet_prp_qualification']['host_cycles']-baseline['p16_diet_prp_qualification']['host_cycles'],2*5051)
        self.assertTrue(timed['p16_timing_qualification']['baseline_diet_numeric_result_not_inherited'])
        self.assertIn(b'INTERVAL=163,CARRY_DONE=163',files[s.CONFIG])
        aw8,aw8_files=s.role('aw8',1);self.assertEqual(aw8['p16_diet_aw8_qualification']['candidate_cycles'],57452)
        self.assertIn(b'FIRST_DIGIT==195',aw8_files[s.AW8])
        faults,fault_files=s.role('faults',1)
        self.assertEqual(faults['p16_diet_whole_host_faults']['reset_ages'],[10,273])
        self.assertIn('reset_ages=10,273',faults['steps'][0]['expected_stdout'])
        self.assertIn(b'FIRST_DIGIT==158',fault_files[s.FAULT])
        for bad in (True,-1,2):
            with self.assertRaises(ValueError):s.role('normal',bad)


if __name__=='__main__':unittest.main()
