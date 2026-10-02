"""Local paired-gate bootstrap/oracle contracts; never call an HDL tool."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from fpga.reference import root_recurrence27_periodmask_pair_regression as r
from fpga.reference import root_recurrence27_periodmask_pair_structure as s
from fpga.reference import root_recurrence27_periodmask_vectors as v

ROOT=Path(__file__).resolve().parents[1]


class PeriodMaskPairTests(unittest.TestCase):
    def test_source_closure_and_paired_derivatives(self):
        self.assertEqual(len(r.source_pins(ROOT)),20)
        self.assertEqual(len(s.validate_files(ROOT)),3)
        top=(ROOT/'rtl/tb'/ (s.TOP+'.sv')).read_text()
        self.assertEqual(top.count(' !== baseline_'),11)
        self.assertIn('genefer_root_recurrence27 #(',top)
        self.assertIn('genefer_root_recurrence27_periodmask #(',top)
        cpp=(ROOT/'rtl/tb'/s.CPP).read_text()
        self.assertEqual(cpp.count('compare();'),4)
        self.assertIn('d.config_period=(elapsed&1) ? 0u : 131071u;',cpp)
        self.assertIn('c.name.rfind("period-",0)==0',cpp)
        wrapper=(ROOT/'rtl/tb'/s.WRAPPER).read_text()
        self.assertIn('context->threads(1);',wrapper)
        self.assertIn('dut{context}',wrapper)
        self.assertIn('Verilated::threadContextp()',cpp)

    def test_preimport_source_tamper_rejection(self):
        with patch.dict(r.FIXED_PINS,{'reference/root_recurrence27_periodmask_vectors.py':'0'*64}),patch.object(r.importlib,'import_module',side_effect=AssertionError('must not import')):
            with self.assertRaisesRegex(ValueError,'pinned source changed'):r.source_pins(ROOT)

    def test_offhost_is_rejected_before_subprocess(self):
        with patch.object(r.socket,'gethostname',return_value='not-aethia'),patch.object(r.subprocess,'Popen',side_effect=AssertionError('must not execute')):
            with self.assertRaisesRegex(ValueError,'aethia'):r.execute(Path('/tmp/out'),Path('/tmp/manifest'),'0'*64)

    def test_supported_profiles_and_exact_build(self):
        for lanes in (16,64):
            for field in (1,2,3):
                config=r.profile(lanes,field)
                self.assertEqual(config['p']*config['q']%(1<<32),1)
                cmd=r.compile_command(ROOT,Path('/scratch/build'),config)
                self.assertEqual(cmd[4:8],['-j','2','--threads','1'])
                self.assertEqual(cmd[-5:],[str(ROOT/name) for name in r.ORDER])
                self.assertIn('-GTAG_W=32',cmd)
        for lanes,field in ((1,1),(32,1),(64,4),(True,1)):
            with self.assertRaises(ValueError):r.profile(lanes,field)

    def test_typed_runtime_thread_and_parameter_probe(self):
        config=r.profile(64,1);good=dict(context_threads=1,model_threads=1,lanes=64,p=config['p'],q=config['q'])
        r.check_probe(json.dumps(good),config)
        for key in good:
            bad=dict(good);bad[key]=True if key=='context_threads' else good[key]+1
            with self.assertRaises(ValueError):r.check_probe(json.dumps(bad),config)

    def test_normal_coverage_and_cycles_are_strict(self):
        coverage=dict(case_count=322,runs=644,responses=900000,aborts=89,rejects=96)
        counts=dict(lanes=64,cases=322,runs=644,responses=900000,checked_cycles=902676,
                    bubbles=100,seed_checks=5000,aborts=89,rejects=96,pair_checks=2000000)
        def line(row):return 'PASS '+' '.join(f'{k}={row[k]}' for k in r.FOOTER_KEYS)+'\n'
        self.assertEqual(r.check_normal(line(counts),r.profile(64,1),coverage),counts)
        for key in ('cases','runs','responses','aborts','rejects','checked_cycles','lanes'):
            bad=dict(counts);bad[key]+=1
            with self.subTest(key=key),self.assertRaises(ValueError):r.check_normal(line(bad),r.profile(64,1),coverage)
        for text in (line(counts)+line(counts),line(counts)+'unexpected\n',line(counts).replace('PASS','FAIL')):
            with self.assertRaises(ValueError):r.check_normal(text,r.profile(64,1),coverage)

    def test_targeted_all_periods_against_iterative_recurrence(self):
        # Alternative iterative arithmetic oracle checks direct exponent rows.
        for field in (1,2,3):
            p,_=v.FIELDS[field-1];cases=v.targeted_cases(field);seen=[]
            for case in cases:
                seen.append(case['period']);state=[row[0] for row in case['seeds']]
                step=case['step']*pow(v.R,-1,p)%p
                for issued,row in enumerate(case['rows']):
                    if case['period'] and issued%case['period']==0:state=[x[0] for x in case['seeds']]
                    context=issued%len(state)
                    self.assertEqual(row[0],state[context],(field,case['period'],issued))
                    # Periods 1/2/4 re-seed before a context product is consumed.
                    if not case['period'] or case['period']>4:state[context]=state[context]*step%p
                self.assertGreaterEqual(case['groups'],9)
            self.assertEqual(tuple(seen),v.PERIODS)

    def test_small_geometry_vectors_cover_both_root_representations(self):
        cases=list(v.geometry_cases(16,1,sizes=(1,4,8)))
        self.assertEqual(len(cases),32)
        self.assertTrue(any(c['name'].endswith('post1') for c in cases))
        self.assertTrue(any(c['name'].startswith('lg8-inv1') for c in cases))
        self.assertTrue(all(len(c['rows'])==c['groups'] and len(c['seeds'])==c['contexts'] for c in cases))

    def test_safe_resource_contract(self):
        source=Path(r.__file__).read_text()
        for token in ('affinity==[0,2]','6*GiB','LOCK.open','os.killpg','start_new_session=True',
                      'command_timeout_seconds=1800','scratch_free_floor_bytes=2*GiB',
                      'durable_free_floor_bytes=10*GiB','host_memory_floor_bytes=4*GiB',
                      "report['vectors']==manifest['vectors']"):
            self.assertIn(token,source)

    def test_full_preparation_archive_and_clean_bootstrap(self):
        with tempfile.TemporaryDirectory() as temporary:
            out=Path(temporary)/'stage'
            # Direct fresh process avoids prior project imports and never HDL.
            result=subprocess.run([sys.executable,'-B',str(ROOT/r.RUNNER),'--prepare',str(out),'--lanes','64','--field','1'],capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stderr)
            manifest=json.loads((out/'manifest.json').read_text())
            self.assertEqual(manifest['vectors']['case_count'],322)
            self.assertEqual(manifest['vectors']['runs'],644)
            self.assertEqual(manifest['vectors']['sha256'],r.sha(out/'vectors.txt'))
            r.verify_manifest(ROOT,out/'manifest.json',r.sha(out/'manifest.json'),r.profile(64,1))
            snapshot=Path(temporary)/'snapshot';snapshot.mkdir()
            with tarfile.open(out/'source.tar.gz') as archive:
                self.assertEqual(len(archive.getnames()),20)
                archive.extractall(snapshot,filter='data')
            code='''import runpy,sys
from pathlib import Path
d=runpy.run_path(sys.argv[1]);root=Path(sys.argv[1]).resolve().parents[1]
v=d['load_project'](root,d['source_pins'](root),isolated=True)
assert len(v.PERIODS)==18
assert not list((root/'reference').rglob('*.pyc'))
print('PASS')
'''
            result=subprocess.run([sys.executable,'-B','-c',code,str(snapshot/'fpga'/r.RUNNER)],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout,'PASS\n')


if __name__=='__main__':unittest.main()
