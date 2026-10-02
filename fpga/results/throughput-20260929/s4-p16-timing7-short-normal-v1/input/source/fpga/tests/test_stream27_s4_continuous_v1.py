"""Metadata/small-array mocks only; no full-N math or HDL."""
import copy
import json
from unittest.mock import patch
import unittest
from fpga.reference import stream27_s4_continuous_v1 as s

class P8Continuous(unittest.TestCase):
    def fixture(self,count=100,stages=0,boundary=0):
        # Explicit small-array mock, not full-size numerical generation.
        with patch.object(s,'N',32):
            plan=json.dumps(s.plan(stages,boundary))
            rows=[('S4_CONTINUOUS_POP',dict(index=i,age=102+i*s.INTERVAL,bit=s.PATTERN[i%8])) for i in range(1,count)]
            rows.append(('S4_CONTINUOUS_IMAGE',dict(actual=[0]*32,expected=[0]*32)))
            footer=s.counts(count,0,stages,boundary);footer.update(reference_ms=1,candidate_ms=2,read_ms=1)
            rows.append(('S4_CONTINUOUS_PASS',footer))
        return rows,{'plan':plan}

    def output(self,rows):
        return ''.join(prefix+' '+json.dumps(value,separators=(',',':'))+'\n' for prefix,value in rows)

    def config(self,count=100,negative='none',stages=0):
        return dict(operations=count,negative=negative,canonical_pipe_stages=stages)

    def test_exact_cold_ledger_and_one_job(self):
        for count,total in ((1,483707),(100,2132354),(1000,17120054)):
            c=s.counts(count)
            self.assertEqual(c['candidate_cycles'],total)
            self.assertEqual((c['resets'],c['loads'],c['starts'],c['readbacks']),(1,1,1,1))
            self.assertEqual(c['canonical_cycles'],393216)
            self.assertEqual(c['copy_cycles'],65539)
            self.assertEqual(c['candidate_cycles']+65536,s.counts(count,1)['candidate_cycles'])
        self.assertEqual(s.counts(100)['backpressure_edges'],1582038)
        self.assertEqual(s.counts(1000)['backpressure_edges'],16568838)
        self.assertEqual(s.counts(1000)['doubles'],500)
        self.assertEqual(s.counts(100)['doubles'],50)
        for count in (1,100,1000):
            for special in (0,1):
                base=s.counts(count,special,0);pipe=s.counts(count,special,1)
                self.assertEqual(pipe['candidate_cycles']-base['candidate_cycles'],3*s.N)
                self.assertEqual(pipe['canonical_cycles']-base['canonical_cycles'],3*s.N)
                for key in base.keys()-{'case_id','canonical_cycles','candidate_cycles'}:
                    self.assertEqual(base[key],pipe[key])
        self.assertEqual(s.counts(100,0,1)['candidate_cycles'],2328962)
        self.assertEqual(s.counts(1000,0,1)['candidate_cycles'],17316662)
        for bad in (True,0,99,1001):
            with self.assertRaises(ValueError):s.counts(bad)
        for bad in (True,-1,2):
            with self.assertRaises(ValueError):s.plan(bad)

    def test_complete_mocked_rows_and_both_arrays(self):
        for count in (100,1000):
            for stages in (0,1):
                rows,assets=self.fixture(count,stages)
                with patch.object(s,'N',32):
                    result=s.validate(self.output(rows),'',0,self.config(count,stages=stages),assets)
                self.assertEqual(result['operations'],count)
                self.assertEqual(result['canonical_pipe_stages'],stages)
                self.assertEqual(result['uninterrupted_1000_native'],count==1000)
                self.assertEqual(result['final_actual_sha256'],result['final_expected_sha256'])

    def test_boundary_descriptor_counter_and_incomplete_reject(self):
        rows,assets=self.fixture()
        mutants=[]
        q=copy.deepcopy(rows);q[0][1]['age']+=1;mutants.append(q)
        q=copy.deepcopy(rows);q[0][1]['bit']^=1;mutants.append(q)
        q=copy.deepcopy(rows);q[-2][1]['actual'][17]=1;mutants.append(q)
        q=copy.deepcopy(rows);q[-1][1]['loads']=2;mutants.append(q)
        q=copy.deepcopy(rows);q[-1][1]['candidate_cycles']+=1;mutants.append(q)
        q=copy.deepcopy(rows);q[-1][1]['canonical_cycles']*=100;mutants.append(q)
        q=copy.deepcopy(rows);q[-2][1]['actual'].pop();mutants.append(q)
        mutants.append(copy.deepcopy(rows[:-1]))
        for i,q in enumerate(mutants):
            with self.subTest(mutant=i),patch.object(s,'N',32),self.assertRaises(ValueError):
                s.validate(self.output(q),'',0,self.config(),assets)
        with patch.object(s,'N',32),self.assertRaises(ValueError):
            s.validate(self.output(rows),'',0,self.config(),dict(assets,extra='{}'))
        with patch.object(s,'N',32),self.assertRaises(ValueError):
            s.validate(self.output(rows),'',0,self.config(stages=1),assets)

    def test_source_selected_role_no_rtl_rewrite(self):
        pilot,files=s.role(100,1);long,long_files=s.role(1000,1)
        self.assertEqual(pilot['build'],long['build'])
        self.assertEqual(pilot['probe'],long['probe'])
        self.assertEqual(pilot['sources'],long['sources'])
        self.assertEqual(files,long_files)
        self.assertEqual(pilot['build']['parameters']['CANONICAL_PIPE_STAGES'],1)
        self.assertEqual(pilot['sources']['rtl/genefer_stream27_host_chain_aw16_p8_canonreg_v1.sv'],s.PIPE_CORE)
        self.assertIn(b'CANONICAL_PIPE_STAGES=1',files[s.HEADER])
        self.assertEqual(pilot['steps'][0]['validator']['config'],self.config(stages=1))
        self.assertEqual(long['steps'][0]['validator']['config'],self.config(1000,stages=1))

    def test_cpp_one_reset_load_start_no_middle_host_barriers(self):
        cpp=(s.ROOT/s.CPP).read_text()
        self.assertEqual(cpp.count('d.rst_n=0;'),1)
        self.assertEqual(cpp.count('d.start=1;'),1)
        self.assertEqual(cpp.count('d.load_we=1;'),1)
        self.assertEqual(cpp.count('d.read_en=1;'),1)
        body=cpp[cpp.index('for(uint64_t age=1;'):cpp.index('need(next==operations')]
        for forbidden in ('d.rst_n=','d.start=1','d.load_we=1','d.read_en=1','canonical('):
            self.assertNotIn(forbidden,body)
        self.assertNotIn('production(',cpp)
        self.assertIn('s4_full_reference::square(expected,BASE,bit(i))',cpp)
        self.assertIn('x[1]==sign&&x[2]==sign',cpp)
        self.assertIn('gfn16_runtime::configure',cpp)

    def test_boundary_frozen61_is_distinct_but_does_not_move_calendar(self):
        short,short_files=s.role(1,1,1);pilot,pilot_files=s.role(100,1,1);long,long_files=s.role(1000,1,1)
        for m,files in ((short,short_files),(pilot,pilot_files),(long,long_files)):
            self.assertEqual(m['build'],pilot['build'])
            self.assertEqual(m['probe'],pilot['probe'])
            self.assertEqual(files,pilot_files)
            self.assertEqual(m['sources'],pilot['sources'])
            self.assertEqual(len(m['build']['sv_sources']),61)
            self.assertEqual(m['build']['parameters']['BOUNDARY_INPUTREG'],1)
            self.assertEqual(m['continuous']['plan']['candidate_root_sha256'],s.BOUNDARY_CORE)
            self.assertEqual(m['steps'][0]['validator']['config']['boundary_inputreg'],1)
        self.assertNotEqual(s.plan(1)['case_id'],s.plan(1,1)['case_id'])
        for count in (1,100,1000):
            old=s.counts(count,0,1);new=s.counts(count,0,1,1)
            self.assertEqual({k:v for k,v in old.items() if k!='case_id'},
                             {k:v for k,v in new.items() if k!='case_id'})
        for bad in (True,-1,2):
            with self.assertRaises(ValueError):s.plan(1,bad)
        with self.assertRaises(ValueError):s.plan(0,1)
        rows,assets=self.fixture(100,1,1)
        cfg=dict(self.config(stages=1),boundary_inputreg=1)
        with patch.object(s,'N',32):
            result=s.validate(self.output(rows),'',0,cfg,assets)
            self.assertEqual(result['boundary_inputreg'],1)
            with self.assertRaises(ValueError):s.validate(self.output(rows),'',0,self.config(stages=1),assets)
            with self.assertRaises(ValueError):s.validate(self.output(rows),'',0,dict(cfg,boundary_inputreg=0),assets)

    def test_fault_separate_exact_contract_and_unchanged_reference(self):
        assets={'plan':json.dumps(s.plan())}
        result=s.validate('',s.NEGATIVE,1,self.config(1,'oracle'),assets)
        self.assertEqual(result['status'],'PASS_expected_contracts')
        for output in ('missed\n',''):
            with self.assertRaises(ValueError):
                s.validate(output,'',0,self.config(1,'oracle'),assets)
        self.assertEqual(s.sha((s.ROOT/s.REFERENCE).read_bytes()),s.REFERENCE_SHA)
        self.assertEqual(s.sha((s.ROOT/s.NTT).read_bytes()),s.NTT_SHA)

    def test_p16_frozen69_and_own_calendar_no_rtl_change(self):
        roles=[s.role(count,1,0,1) for count in (1,100,1000)]
        donor=json.loads((s.DIET_MODEL/'manifest.json').read_text())
        for role,files in roles:
            self.assertEqual(len(role['build']['sv_sources']),69)
            self.assertEqual(role['build']['parameters'],donor['build']['parameters'])
            self.assertEqual(role['build']['top'],donor['build']['top'])
            for name in donor['build']['sv_sources']:
                self.assertEqual(s.sha(files[name]),donor['sources'][name])
            self.assertEqual(role['continuous']['plan']['profile']['p'],16)
            self.assertEqual(role['continuous']['plan']['geometry'],
                dict(interval=8459,carry_done=12557,first_digit=8458,cold_first=102))
            self.assertEqual(role['continuous']['plan']['candidate_root_sha256'],s.DIET_CORE)
            self.assertEqual(role['steps'][0]['validator']['config']['p16_diet'],1)
            self.assertIn(b'AW=16,P=16,N=65536',files[s.HEADER])
        self.assertEqual(roles[0][1],roles[1][1]);self.assertEqual(roles[1][1],roles[2][1])
        self.assertEqual(roles[0][0]['build'],roles[2][0]['build'])
        for count,total in ((1,668025),(100,1505466),(1000,9118566)):
            ledger=s.counts(count,0,1,0,1)
            self.assertEqual(ledger['candidate_cycles'],total)
            self.assertEqual(ledger['final_rows'],4096)
            self.assertEqual(ledger['conversion_cycles'],4096)
            self.assertEqual(ledger['canonical_cycles'],9*65536)
            self.assertNotEqual(ledger['case_id'],s.counts(count,0,1)['case_id'])
        for bad in (True,-1,2):
            with self.assertRaises(ValueError):s.plan(1,0,bad)
        with self.assertRaises(ValueError):s.plan(0,0,1)
        with self.assertRaises(ValueError):s.plan(1,1,1)

    def test_p16_source_sensitive_mocked_output_rejects_p8_and_reload(self):
        count=100;cfg=dict(self.config(count,stages=1),p16_diet=1)
        with patch.object(s,'N',32):
            case=s.plan(1,0,1);assets={'plan':json.dumps(case)}
            rows=[('S4_CONTINUOUS_POP',dict(index=i,age=102+i*8459,bit=s.PATTERN[i%8])) for i in range(1,count)]
            rows.append(('S4_CONTINUOUS_IMAGE',dict(actual=[0]*32,expected=[0]*32)))
            footer=s.counts(count,0,1,0,1);footer.update(reference_ms=1,candidate_ms=2,read_ms=1)
            rows.append(('S4_CONTINUOUS_PASS',footer))
            result=s.validate(self.output(rows),'',0,cfg,assets)
            self.assertEqual(result['p16_diet'],1)
            self.assertEqual(result['final_actual_sha256'],result['final_expected_sha256'])
            for key in ('loads','resets','candidate_cycles','conversion_cycles','final_rows'):
                wrong=copy.deepcopy(rows);wrong[-1][1][key]+=1
                with self.subTest(field=key),self.assertRaises(ValueError):s.validate(self.output(wrong),'',0,cfg,assets)
            wrong=copy.deepcopy(rows);wrong[0][1]['age']=102+s.INTERVAL
            with self.assertRaises(ValueError):s.validate(self.output(wrong),'',0,cfg,assets)
            wrong=copy.deepcopy(rows);wrong[-2][1]['actual'][17]=1
            with self.assertRaises(ValueError):s.validate(self.output(wrong),'',0,cfg,assets)
            with self.assertRaises(ValueError):s.validate(self.output(rows),'',0,self.config(count,stages=1),assets)
            with self.assertRaises(ValueError):s.validate(self.output(rows),'',0,dict(cfg,boundary_inputreg=1),assets)
            with self.assertRaises(ValueError):s.validate(self.output(rows),'',0,dict(cfg,p16_diet=0),assets)

    def test_p16_timing7_source_bound75_and_own_one_edge_per_operation(self):
        roles=[s.role(count,1,0,1,1) for count in (1,100,1000)]
        donor=json.loads((s.TIMING_MODEL/'manifest.json').read_text())
        for (m,files),count in zip(roles,(1,100,1000)):
            self.assertEqual(len(m['build']['sv_sources']),75)
            self.assertEqual(m['build']['parameters'],donor['build']['parameters'])
            for name in donor['build']['sv_sources']:self.assertEqual(s.sha(files[name]),donor['sources'][name])
            self.assertEqual(m['continuous']['plan']['geometry'],dict(interval=8460,carry_done=12558,first_digit=8459,cold_first=102))
            self.assertEqual(m['continuous']['plan']['candidate_root_sha256'],s.TIMING_CORE)
            self.assertEqual(m['steps'][0]['validator']['config'],dict(operations=count,negative='none',canonical_pipe_stages=1,p16_diet=1,p16_timing=1))
            self.assertEqual(s.counts(count,0,1,0,1,1)['candidate_cycles']-s.counts(count,0,1,0,1)['candidate_cycles'],count)
            self.assertNotEqual(s.plan(1,0,1)['case_id'],s.plan(1,0,1,1)['case_id'])
        self.assertEqual(roles[0][1],roles[1][1]);self.assertEqual(roles[1][1],roles[2][1])
        for args in ((1,0,0,1),(1,1,1,1),(0,0,1,1),(1,0,1,True)):
            with self.assertRaises(ValueError):s.plan(*args)

if __name__=='__main__':
    unittest.main()
