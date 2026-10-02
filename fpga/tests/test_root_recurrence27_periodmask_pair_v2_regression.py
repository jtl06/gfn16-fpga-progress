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
from fpga.reference import root_recurrence27_periodmask_pair_v2_regression as r
from fpga.reference import root_recurrence27_periodmask_pair_v2_structure as s
from fpga.reference import root_recurrence27_periodmask_vectors as v

ROOT=Path(__file__).resolve().parents[1]


class PeriodMaskPairV2Tests(unittest.TestCase):
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
        self.assertEqual(cpp.count('    return 0;\n}catch(const std::exception& e)'),1)
        self.assertIn('#include "root_recurrence27_periodmask_pair_v2.cpp"',wrapper)

    def test_v1_sources_and_stage_remain_frozen(self):
        frozen={
            'reference/root_recurrence27_periodmask_pair_regression.py':'e33e48d2424f74e97a0cc5dd9c412253b71144b763312eaaf073308c8da50ddc',
            'reference/root_recurrence27_periodmask_pair_structure.py':'d6f0c549b7b63beb6faeecab4801c5e1a43f619cebb5cb33e575498f4e55846e',
            'rtl/tb/root_recurrence27_periodmask_pair.cpp':'2101bf21f39c50064fbb129ff12908170c123c01204277c5fe65c5b1276fd629',
            'rtl/tb/root_recurrence27_periodmask_pair_threaded.cpp':'be4e569d7ae94f075b0ba7a50d64744b156fe7f72e0bf8a285d53bd62053e173',
            'results/throughput-20260929/root-recurrence27-periodmask-pair-stage-l64-p1-v1/manifest.json':'b31968abb12df60dafc4250e69c8721862c1f2ab548b2c09fa13b9ab341bf25e',
        }
        for name,digest in frozen.items():self.assertEqual(r.sha(ROOT/name),digest)
        self.assertIn('snapshot-v2/fpga',str(r.SOURCE))
        self.assertNotIn('rtl/tb/root_recurrence27_periodmask_pair_threaded.cpp',r.ORDER)

    def test_missing_success_return_is_rejected(self):
        original=(ROOT/'rtl/tb/root_recurrence27.cpp').read_text()
        expected=s.expected_cpp(original)
        self.assertNotEqual(expected,expected.replace('    return 0;\n}catch','}catch'))
        # Exact derivative validation rejects both the missing return and a
        # nonzero success result before a new archive can be prepared.
        with tempfile.TemporaryDirectory() as temporary:
            fake=Path(temporary)
            import shutil
            for name in r.source_pins(ROOT):
                target=fake/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
            target=fake/'rtl/tb'/s.CPP
            target.write_text(expected.replace('    return 0;\n}catch','}catch'))
            with self.assertRaises(ValueError):s.validate_files(fake)
            target.write_text(expected.replace('    return 0;\n}catch','    return 1;\n}catch'))
            with self.assertRaises(ValueError):s.validate_files(fake)

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
                self.assertIn('-Werror=return-type',cmd[cmd.index('-CFLAGS')+1].split())
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
