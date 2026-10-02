"""Bounded executor source/bootstrap contracts only; never call HDL tools."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from fpga.reference import rowcompact_reset_probe_regression as r

ROOT=Path(__file__).resolve().parents[1]


def evidence(case):
    kind=case['kind'];variant=case['variant'];age=case['age']
    bank=(2 if variant==0 else 0) if kind=='bf' else 64*variant
    row=256 if kind=='bf' else 1;group=variant if kind=='bf' else 2+variant
    rows=[f'ACCEPT kind={kind} variant={variant} bank={bank} row={row} group={group} edge=80000']
    rows += [f'PRE_RESET field={f} age={age} committed=0 bf_checks=0 mul_checks=128 bf_nonzero=0 mul_nonzero=0' for f in range(3)]
    rows += ['RESET async=1 quiet_edges=8 writes=0']
    rows += [f'SHADOW field={f} '+' '.join(f'{key}={value}' for key,value in r.COUNTS.items()) for f in range(3)]
    rows += [f'PASS reset_probe kind={kind} variant={variant} age={age} bit=0 readbacks=65536 recovery_cycles=41708 edges={80000+age+172791}']
    return '\n'.join(rows)+'\n'


class ResetExecutorTests(unittest.TestCase):
    def test_exact_closure_preserves_frozen_proposal(self):
        pins=r.source_pins(ROOT)
        self.assertEqual(len(pins),68)
        self.assertEqual(r.sha(ROOT/r.PROPOSAL),r.PROPOSAL_SHA)
        self.assertEqual(len(r.proposal(ROOT)['sources']),65)
        self.assertEqual(len(r.proposal(ROOT)['compiled_source_order']),18)

    def test_only_reviewed_eight_cases(self):
        self.assertEqual(len(r.BATCH),8)
        self.assertEqual({tuple(c.values()) for c in r.BATCH},
            {(kind,variant,age,0) for kind in ('bf','mul') for variant in (0,1) for age in (0,6)})
        self.assertEqual(len({r.case_name(c) for c in r.BATCH}),8)
        for bad in (dict(kind='bf',variant=0,age=7,bit=0),dict(kind='mul',variant=1,age=6,bit=1)):
            with self.assertRaises(ValueError):r.case_name(bad)

    def test_compile_threads_warning_and_read_only_observation(self):
        cmd=r.compile_command(ROOT,Path('/scratch/build'))
        self.assertEqual(cmd[4:8],['-j','2','--threads','1'])
        self.assertIn('-GAW=16',cmd);self.assertIn('-GNTT_LANES=64',cmd)
        self.assertIn('-Werror=return-type',cmd[cmd.index('-CFLAGS')+1].split())
        self.assertEqual(cmd[-18:],[str(ROOT/name) for name in r.proposal(ROOT)['compiled_source_order']])
        self.assertNotIn('--public-flat-rw',cmd)
        cpp=(ROOT/'rtl/tb/rowcompact_reset_probe.cpp').read_text()
        self.assertIn('VerilatedContext context;context.threads(1);',cpp)
        self.assertIn('Vrowcompact_reset_probe d{&context}',cpp)
        self.assertIn('return 0;\n}catch',cpp)

    def test_typed_runtime_probe(self):
        good=dict(context_threads=1,model_threads=1,aw=16,lanes=64)
        self.assertEqual(r.check_probe(json.dumps(good)),good)
        for key in good:
            for value in (True,good[key]+1):
                bad=dict(good);bad[key]=value
                with self.assertRaises(ValueError):r.check_probe(json.dumps(bad))

    def test_complete_single_case_evidence(self):
        for case in r.BATCH:
            result=r.check_case(evidence(case),case)
            self.assertEqual(result['readbacks'],65536)
            self.assertEqual(len(result['pre_reset']),3)
            self.assertEqual(result['edges'],252791+case['age'])

    def test_missing_or_mutated_shadow_recovery_rejected(self):
        case=r.BATCH[0];good=evidence(case)
        for old,new in [('field=2','field=1'),('bf=2097152','bf=2097151'),('mul=196608','mul=0'),
                        ('bf_nonzero=2093056','bf_nonzero=0'),('mul_nonzero=196224','mul_nonzero=0'),
                        ('committed=0','committed=1'),('quiet_edges=8','quiet_edges=7'),
                        ('writes=0','writes=1'),('row=256','row=0'),('readbacks=65536','readbacks=65535'),
                        ('recovery_cycles=41708','recovery_cycles=41709'),('edges=252791','edges=252790')]:
            with self.subTest(old=old),self.assertRaises(ValueError):r.check_case(good.replace(old,new),case)
        for text in (good+good,good+'unexpected\n','\n'.join(good.splitlines()[1:]),good.replace('PASS','FAIL')):
            with self.assertRaises(ValueError):r.check_case(text,case)

    def test_offhost_before_subprocess(self):
        with patch.object(r.socket,'gethostname',return_value='not-aethia'),patch.object(r.subprocess,'Popen',side_effect=AssertionError('must not run')):
            with self.assertRaisesRegex(ValueError,'aethia'):r.execute(Path('/tmp/out'),Path('/tmp/manifest'),'0'*64)

    def test_proposal_tamper_precedes_project_import(self):
        with patch.object(r,'PROPOSAL_SHA','0'*64),patch.object(r.importlib,'import_module',side_effect=AssertionError('must not import')):
            with self.assertRaisesRegex(ValueError,'proposal identity'):r.source_pins(ROOT)

    def test_resource_and_timeout_contracts(self):
        source=Path(r.__file__).read_text()
        for token in ('affinity==[0,2]','6*GiB','LOCK.open','os.killpg','start_new_session=True',
                      'case_timeout_seconds=300','batch_timeout_seconds=2400','build_timeout_seconds=1800',
                      'scratch_free_floor_bytes=2*GiB','durable_free_floor_bytes=10*GiB',
                      'host_memory_floor_bytes=4*GiB','timeout=300,deadline=deadline','time.monotonic()+2400',
                      "'verilator_bin'","report['tool_executable_sha256']",'full_matrix_qualified=False',
                      'mutant_sensitivity_qualified=False','native_reset_qualified=False'):
            self.assertIn(token,source)

    def test_prepare_archive_manifest_bootstrap_without_hdl(self):
        with tempfile.TemporaryDirectory() as temporary:
            out=Path(temporary)/'stage'
            result=subprocess.run([sys.executable,'-B',str(ROOT/r.RUNNER),'--prepare',str(out)],capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stderr)
            manifest,pins=r.verify_manifest(ROOT,out/'manifest.json',r.sha(out/'manifest.json'))
            self.assertEqual(manifest['batch'],list(r.BATCH))
            self.assertFalse(manifest['native_reset_qualified'])
            self.assertEqual(manifest['archive_sha256'],r.sha(out/'source.tar.gz'))
            self.assertEqual(manifest['vector']['sha256'],r.sha(out/'vectors-aw16.txt'))
            snapshot=Path(temporary)/'snapshot';snapshot.mkdir()
            with tarfile.open(out/'source.tar.gz') as archive:
                self.assertEqual(set(archive.getnames()),{'fpga/'+name for name in pins})
                self.assertTrue(all(item.isfile() for item in archive.getmembers()))
                archive.extractall(snapshot,filter='data')
            code="""import runpy,sys
from pathlib import Path
d=runpy.run_path(sys.argv[1]);root=Path(sys.argv[1]).resolve().parents[1]
s=d['load_project'](root,d['source_pins'](root),isolated=True)
assert len(s.matrix())==64
assert not list((root/'reference').rglob('*.pyc'))
print('PASS')
"""
            result=subprocess.run([sys.executable,'-B','-c',code,str(snapshot/'fpga'/r.RUNNER)],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout,'PASS\n')
            target=snapshot/'fpga/rtl/tb/rowcompact_reset_probe.cpp'
            target.write_text(target.read_text()+'\n// drift\n')
            with self.assertRaisesRegex(ValueError,'pinned source changed'):r.source_pins(snapshot/'fpga')


if __name__=='__main__':unittest.main()
