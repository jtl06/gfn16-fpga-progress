"""Python-only preparation/bootstrap tests; never execute HDL or a compiler."""
import ast
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from reference import core27_prefetch_r2_host_broadcast_regression as r


class HostBroadcastCoreRunnerTests(unittest.TestCase):
    root=Path(__file__).resolve().parents[1]

    def prepared(self,out):
        with contextlib.redirect_stdout(io.StringIO()):return r.prepare(out)

    def test_closed_43_sources_and_fresh_archive(self):
        with tempfile.TemporaryDirectory() as temporary,patch.object(r.subprocess,'Popen',side_effect=AssertionError('no execution')):
            out=Path(temporary)/'prepared';manifest=self.prepared(out)
            self.assertEqual(len(manifest['sources']),43)
            self.assertEqual(manifest['supported_aw'],[1,5,7,16])
            self.assertEqual(manifest['top'],r.TOP)
            self.assertEqual(manifest['archive_sha256'],r.sha(out/'source.tar.gz'))
            with tarfile.open(out/'source.tar.gz') as archive:
                self.assertEqual(set(archive.getnames()),{'fpga/'+name for name in manifest['sources']})
                for name,digest in manifest['sources'].items():
                    self.assertEqual(hashlib.sha256(archive.extractfile('fpga/'+name).read()).hexdigest(),digest)
            for aw in (1,5,7,16):
                checked,pins=r.verify_manifest(self.root,out/'manifest.json',r.sha(out/'manifest.json'),aw)
                self.assertEqual(checked,manifest);self.assertEqual(pins,manifest['sources'])
            with self.assertRaises(FileExistsError):self.prepared(out)

    def test_manifest_mismatch_rejected_before_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            out=Path(temporary)/'prepared';manifest=self.prepared(out);path=out/'manifest.json'
            with patch.object(r.importlib,'import_module',side_effect=AssertionError('must not import')):
                for aw in (True,0,8,17):
                    with self.assertRaises(ValueError):r.verify_manifest(self.root,path,r.sha(path),aw)
                with self.assertRaises(ValueError):r.verify_manifest(self.root,path,'0'*64,5)
                for key,value in (('top','old_top'),('supported_aw',[1,5]),('target','/wrong'),
                                  ('sources',{}),('status','passed')):
                    path.write_text(json.dumps(dict(manifest,**{key:value})))
                    with self.assertRaises(ValueError):r.verify_manifest(self.root,path,r.sha(path),5)

    def test_tampered_project_bytes_block_before_import(self):
        with patch.dict(r.FIXED_PINS,{'reference/rns_reference.py':'0'*64}),\
             patch.object(r.importlib,'import_module',side_effect=AssertionError('must not import')):
            with self.assertRaisesRegex(ValueError,'pinned source changed'):r.source_pins(self.root)
            with self.assertRaisesRegex(ValueError,'pinned source changed'):r.load_project(self.root,{})

    def test_no_top_level_project_imports(self):
        tree=ast.parse(Path(r.__file__).read_text())
        for node in tree.body:
            if isinstance(node,ast.ImportFrom):self.assertEqual(node.module,'pathlib')
            if isinstance(node,ast.Import):self.assertFalse(any(n.name.startswith('reference') for n in node.names))
        with patch.object(r.importlib,'import_module',side_effect=AssertionError('must not import')):
            with self.assertRaisesRegex(ValueError,'execute directly'):r.load_project(self.root,r.source_pins(self.root),isolated=True)

    def test_source_only_clean_bootstrap_and_original_vectors(self):
        # Standard Python subprocess only. A clean extracted snapshot lets the
        # actual pre-import loader run without trusting local .pyc files.
        with tempfile.TemporaryDirectory() as temporary:
            out=Path(temporary)/'prepared';self.prepared(out)
            snapshot=Path(temporary)/'snapshot';snapshot.mkdir()
            with tarfile.open(out/'source.tar.gz') as archive:archive.extractall(snapshot,filter='data')
            root=snapshot/'fpga';script=root/r.RUNNER
            code='''import json,runpy,sys
from pathlib import Path
d=runpy.run_path(sys.argv[1]); root=Path(sys.argv[1]).resolve().parents[1]
pins=d['source_pins'](root); b,s,sources=d['load_project'](root,pins,isolated=True)
assert len(sources)==16 and s.CANDIDATE==d['TOP']
hashes={1:'0f4a674ed168b123b57df4beced18993d635b6db4afc94b83e9a264027daf740',5:'a5b46cb2f52ce817bed3de90a91dfc6fb038b30215edc7d861514d1106919edd'}
for aw,wanted in hashes.items():
    path=root.parent/('vectors'+str(aw)+'.txt'); info=b.write_vectors(path,aw,20260929,True)
    assert info['sha256']==wanted and info['fusion_invalid_final_row_cases']==4
assert b.ntt_schedule(16)==(20558,815)
assert sys.dont_write_bytecode and sys.pycache_prefix is None
assert not list((root/'reference').rglob('*.pyc'))
print('PASS source-only import, original vectors and unchanged schedule')
'''
            result=subprocess.run([sys.executable,'-B','-c',code,str(script)],capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout,'PASS source-only import, original vectors and unchanged schedule\n')
            # A compiled project cache rejects before importing any project.
            cache=root/'reference/__pycache__';cache.mkdir();(cache/'poison.pyc').write_bytes(b'bad')
            result=subprocess.run([sys.executable,'-B','-c',code,str(script)],capture_output=True,text=True,timeout=60)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('compiled cache must not exist',result.stderr)

    def test_exact_compile_boundary(self):
        root=Path('/snapshot/fpga');sources=[root/'rtl/kernel/a.sv',root/'rtl/kernel/b.sv']
        for aw in (1,5,7,16):
            command=r.compile_command(root,sources,Path('/scratch/build'),aw)
            self.assertEqual(command[:11],['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',r.TOP,f'-GAW={aw}'])
            self.assertEqual(command[11:14],['-GNTT_LANES=64','--Mdir','/scratch/build'])
            self.assertEqual(command[14:-1],list(map(str,sources)))
            self.assertEqual(command[-1],str(root/'rtl/tb/square_core27_stream_prefetch_r2_host_broadcast_threaded.cpp'))
        for bad in (True,8,0):
            with self.assertRaises(ValueError):r.compile_command(root,sources,Path('/scratch/build'),bad)

    def test_off_host_and_unlink_race_guards(self):
        with patch.object(r.socket,'gethostname',return_value='not-aethia'),\
             patch.object(r.importlib,'import_module',side_effect=AssertionError('no imports')),\
             patch.object(r.subprocess,'Popen',side_effect=AssertionError('no processes')):
            with self.assertRaisesRegex(ValueError,'aethia'):r.execute(5,Path('/tmp/out'),Path('/tmp/manifest'),'0'*64)
        with tempfile.TemporaryDirectory() as temporary,patch.object(r.os,'walk',return_value=[(temporary,[],['gone'])]):
            self.assertEqual(r.allocated_bytes(Path(temporary)),0)

    def test_explicit_resource_and_evidence_contract(self):
        source=Path(r.__file__).read_text()
        for required in ('scratch_reservation_bytes=768*MiB','durable_reservation_bytes=64*MiB',
                         'scratch_free_floor_bytes=2*GiB','durable_free_floor_bytes=10*GiB',
                         'command_timeout_seconds=1800','lock_wait_timeout_seconds=1800',
                         "limits['affinity']==[0,2]",'len({tuple(x) for x in limits[\'physical_cores\']})==2',
                         "baseline.validate_output(output,payload.decode(),aw)","baseline.segments(raw)",
                         "out/'approved-manifest.json'",'source drift','durable artifact drift','toolchain drift'):
            self.assertIn(required,source)
        self.assertNotIn('shell=True',source)
        self.assertNotIn('rm -',source)


if __name__=='__main__':unittest.main()
