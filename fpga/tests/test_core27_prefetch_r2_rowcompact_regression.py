"""Native runner proposal checks; no HDL tools or remote execution."""
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from fpga.reference import core27_prefetch_r2_rowcompact_regression as r

ROOT=Path(__file__).resolve().parents[1]

class CompactRowRunnerTests(unittest.TestCase):
    def test_closed_sources_and_original_ancestors(self):
        from fpga.reference import core27_prefetch_r2_orient8_regression as old
        baseline=old.source_pins(ROOT);candidate=r.source_pins(ROOT)
        self.assertEqual(len(baseline),51)
        self.assertEqual(len(candidate),58)
        self.assertEqual({k:candidate[k] for k in baseline},baseline)
        self.assertEqual(len(r.validate_benches(ROOT)),2)

    def test_native_bootstrap_and_compiled_closure(self):
        with tempfile.TemporaryDirectory() as temporary:
            out=Path(temporary)/'prepared'
            with contextlib.redirect_stdout(io.StringIO()),patch.object(r.subprocess,'Popen',side_effect=AssertionError('no HDL')):
                manifest=r.prepare(out)
            self.assertEqual(manifest['status'],'prepared_not_executed')
            self.assertEqual(manifest['archive_sha256'],r.sha(out/'source.tar.gz'))
            r.verify_manifest(ROOT,out/'manifest.json',r.sha(out/'manifest.json'),5)
            snapshot=Path(temporary)/'snapshot';snapshot.mkdir()
            with tarfile.open(out/'source.tar.gz') as archive:
                self.assertEqual(len(archive.getnames()),58)
                archive.extractall(snapshot,filter='data')
            code='''import runpy,sys
from pathlib import Path
d=runpy.run_path(sys.argv[1]);root=Path(sys.argv[1]).resolve().parents[1]
b,s,sources=d['load_project'](root,d['source_pins'](root),isolated=True)
assert len(sources)==16
assert sum('rowcompact' in p.name for p in sources)==3
assert not any('rootfused' in p.name for p in sources)
assert sources[-1].name==d['TOP']+'.sv'
assert b.ntt_schedule(16)==(20558,815)
hashes={1:'0f4a674ed168b123b57df4beced18993d635b6db4afc94b83e9a264027daf740',5:'a5b46cb2f52ce817bed3de90a91dfc6fb038b30215edc7d861514d1106919edd'}
for aw,wanted in hashes.items():
    path=root.parent/('vectors'+str(aw)+'.txt');info=b.write_vectors(path,aw,20260929,True)
    assert info['sha256']==wanted and info['fusion_invalid_final_row_cases']==4
assert not list((root/'reference').rglob('*.pyc'))
print('PASS')
'''
            result=subprocess.run([sys.executable,'-B','-c',code,str(snapshot/'fpga'/r.RUNNER)],capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout,'PASS\n')
            with self.assertRaises(FileExistsError):r.prepare(out)

    def test_off_host_rejected(self):
        with patch.object(r.socket,'gethostname',return_value='not-aethia'),patch.object(r.subprocess,'Popen',side_effect=AssertionError('no HDL')):
            with self.assertRaisesRegex(ValueError,'aethia'):
                r.execute(5,Path('/tmp/out'),Path('/tmp/manifest'),'0'*64)

    def test_source_tamper_rejected_before_import(self):
        with patch.dict(r.FIXED_PINS,{'reference/prefetch_r2_rowcompact_structure.py':'0'*64}),patch.object(r.importlib,'import_module',side_effect=AssertionError('no import')):
            with self.assertRaisesRegex(ValueError,'pinned source changed'):r.source_pins(ROOT)

    def test_compile_and_resource_contract(self):
        command=r.compile_command(ROOT,[],Path('/scratch'),5)
        self.assertEqual(command[4:8],['-j','2','--threads','1'])
        self.assertIn('-GNTT_LANES=64',command)
        self.assertIn('rowcompact_threaded.cpp',command[-1])
        source=Path(r.__file__).read_text()
        for text in ("limits['affinity']==[0,2]",'6*GiB','command_timeout_seconds=1800',
                     'durable_free_floor_bytes=10*GiB','scratch_free_floor_bytes=2*GiB',
                     'LOCK.open','baseline.validate_output(output,payload.decode(),aw)'):
            self.assertIn(text,source)

if __name__=='__main__':unittest.main()
