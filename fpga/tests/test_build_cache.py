import concurrent.futures
import json
import multiprocessing
import os
from pathlib import Path
import socket
import stat
import subprocess
import tempfile
import threading
import time
import unittest
from unittest import mock

from reference.build_cache import (BuildCache,BuildProduct,BuildSpec,CacheError,
                                  InputsChanged,InvalidArtifact,UntrackedDependency,
                                  digest,fingerprint_toolchain)


@unittest.skipUnless(socket.gethostname()=='aethia','cache tests run only on aethia')
class BuildCacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='gfn-cache-test-')
        self.root=Path(self.temporary.name);self.rtl=self.root/'kernel.sv';self.cpp=self.root/'driver.cpp'
        self.rtl.write_text('module kernel; endmodule\n');self.cpp.write_text('int main(){return 0;}\n')
        self.headers=self.root/'include';self.headers.mkdir();(self.headers/'runtime.h').write_text('v1\n')
        self.messages=[];self.cache=BuildCache(self.root/'cache',log=self.messages.append)
        self.builds=0

    def tearDown(self):
        # Cache artifacts are intentionally frozen. Restore permissions only
        # inside this test's fresh TemporaryDirectory before removing it.
        for path in self.root.rglob('*'):
            if not path.is_symlink():path.chmod(0o700 if path.is_dir() else 0o600)
        self.temporary.cleanup()

    def spec(self,**changes):
        arguments=dict(sources={'rtl':self.rtl,'cpp':self.cpp},
            configuration={'top':'kernel','parameters':{'AW':16},'flags':['-O2']},
            toolchain={'version':'fake-1','files':[],'trees':[]},
            environment={'CXXFLAGS':None,'VERILATOR_ROOT':'/tool/runtime'},include_trees=[self.headers])
        arguments.update(changes);return BuildSpec.capture(**arguments)

    def builder(self,work):
        self.builds+=1;executable=work/'sim';executable.write_text('#!/bin/sh\nprintf "oracle-ran\\n"\n')
        executable.chmod(0o755);(work/'generated.cpp').write_text('generated\n')
        return BuildProduct('sim',(self.rtl,self.cpp,self.headers/'runtime.h'))

    def test_verified_hit_and_oracle_always_runs(self):
        spec=self.spec();a=self.cache.obtain(spec,self.builder);b=self.cache.obtain(spec,self.builder)
        self.assertEqual((a.cache_status,b.cache_status,self.builds),('built','hit',1))
        self.assertEqual(a.executable_sha256,digest(b.executable))
        self.assertEqual(subprocess.check_output([a.executable]),b'oracle-ran\n')
        self.assertEqual(subprocess.check_output([b.executable]),b'oracle-ran\n')
        self.assertTrue(any('hit key=' in message for message in self.messages))
        self.assertFalse(a.executable.stat().st_mode&0o222)

    def test_each_input_dimension_invalidates(self):
        original=self.spec().key
        for path in (self.rtl,self.cpp,self.headers/'runtime.h'):
            before=path.read_text();path.write_text(before+'changed\n')
            self.assertNotEqual(original,self.spec().key);path.write_text(before)
        variants=[
            {'configuration':{'top':'other','parameters':{'AW':16},'flags':['-O2']}},
            {'configuration':{'top':'kernel','parameters':{'AW':8},'flags':['-O2']}},
            {'configuration':{'top':'kernel','parameters':{'AW':16},'flags':['-O0']}},
            {'toolchain':{'version':'fake-2','files':[],'trees':[]}},
            {'environment':{'CXXFLAGS':'-DNDEBUG','VERILATOR_ROOT':'/tool/runtime'}},
            {'environment':{'CXXFLAGS':None,'VERILATOR_ROOT':'/different/runtime'}},
        ]
        for variant in variants:self.assertNotEqual(original,self.spec(**variant).key)
        (self.headers/'shadow.h').write_text('new include resolution candidate\n')
        self.assertNotEqual(original,self.spec().key)

    def test_config_order_is_canonical_but_flag_order_matters(self):
        a=self.spec(configuration={'a':1,'b':2});b=self.spec(configuration={'b':2,'a':1})
        self.assertEqual(a.key,b.key)
        self.assertNotEqual(self.spec(configuration=['-DVALUE=1','-UDEBUG']).key,
                            self.spec(configuration=['-UDEBUG','-DVALUE=1']).key)

    def test_stale_spec_and_changes_during_build_rejected(self):
        stale=self.spec();self.rtl.write_text('changed before lookup')
        with self.assertRaises(InputsChanged):self.cache.obtain(stale,self.builder)
        current=self.spec()
        def changing(work):
            product=self.builder(work);self.cpp.write_text('changed during build');return product
        with self.assertRaises(InputsChanged):self.cache.obtain(current,changing)
        self.assertFalse((self.cache.root/'objects'/current.key).exists())
        self.assertEqual(list((self.cache.root/'staging').iterdir()),[])

    def test_mutants_cannot_reuse_baseline(self):
        baseline=self.spec();a=self.cache.obtain(baseline,self.builder)
        mutant=self.root/'mutant.sv';mutant.write_text(self.rtl.read_text().replace('kernel','broken'))
        other=self.spec(sources={'rtl':mutant,'cpp':self.cpp})
        def mutant_builder(work):
            product=self.builder(work);return BuildProduct(product.executable,(mutant,self.cpp,self.headers/'runtime.h'))
        b=self.cache.obtain(other,mutant_builder)
        self.assertNotEqual(a.key,b.key);self.assertEqual(self.builds,2)

    def test_failed_build_is_not_cached(self):
        spec=self.spec()
        def failed(work):
            self.builder(work);raise RuntimeError('compiler failed')
        with self.assertRaisesRegex(RuntimeError,'compiler failed'):self.cache.obtain(spec,failed)
        self.assertFalse((self.cache.root/'objects'/spec.key).exists())
        self.assertEqual(self.cache.obtain(spec,self.builder).cache_status,'built')
        self.assertEqual(self.builds,2)

    def test_concurrent_miss_builds_once_and_publishes_atomically(self):
        spec=self.spec();started=threading.Event();release=threading.Event()
        def slow(work):
            product=self.builder(work);started.set();self.assertTrue(release.wait(5));return product
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(self.cache.obtain,spec,slow);self.assertTrue(started.wait(5))
            self.assertFalse((self.cache.root/'objects'/spec.key).exists())
            second=pool.submit(self.cache.obtain,spec,slow);time.sleep(.1);self.assertFalse(second.done())
            release.set();results=[first.result(5),second.result(5)]
        self.assertEqual(sorted(r.cache_status for r in results),['built','hit']);self.assertEqual(self.builds,1)

    def test_corrupt_executable_is_quarantined_and_rebuilt(self):
        spec=self.spec();first=self.cache.obtain(spec,self.builder)
        first.executable.chmod(0o755);first.executable.write_text('corrupt');first.executable.chmod(0o555)
        second=self.cache.obtain(spec,self.builder)
        self.assertEqual(second.cache_status,'repaired');self.assertEqual(self.builds,2)
        self.assertEqual(len(list((self.cache.root/'quarantine').iterdir())),1)
        self.assertEqual(subprocess.check_output([second.executable]),b'oracle-ran\n')

    def test_independent_processes_share_one_build(self):
        context=multiprocessing.get_context('fork');gate=context.Event();queue=context.Queue()
        count=self.root/'process-builds';spec=self.spec();cache_root=self.root/'process-cache'
        def worker():
            cache=BuildCache(cache_root,log=lambda message:None)
            def build(work):
                with count.open('a') as stream:stream.write('build\n')
                executable=work/'sim';executable.write_text('#!/bin/sh\nexit 0\n');executable.chmod(0o755)
                time.sleep(.15);return BuildProduct('sim')
            gate.wait(5);queue.put(cache.obtain(spec,build).cache_status)
        workers=[context.Process(target=worker) for _ in range(2)]
        for worker_process in workers:worker_process.start()
        gate.set()
        for worker_process in workers:
            worker_process.join(5);self.assertFalse(worker_process.is_alive());self.assertEqual(worker_process.exitcode,0)
        self.assertEqual(sorted(queue.get(timeout=2) for _ in workers),['built','hit'])
        self.assertEqual(count.read_text(),'build\n')

    def test_failed_atomic_publish_leaves_no_entry(self):
        spec=self.spec()
        with mock.patch('reference.build_cache.os.replace',side_effect=OSError('publication failed')):
            with self.assertRaisesRegex(OSError,'publication failed'):self.cache.obtain(spec,self.builder)
        self.assertFalse((self.cache.root/'objects'/spec.key).exists())
        self.assertEqual(list((self.cache.root/'staging').iterdir()),[])
        self.assertEqual(self.cache.obtain(spec,self.builder).cache_status,'built')

    def test_missing_or_nonexecutable_product_rejected(self):
        spec=self.spec()
        with self.assertRaises(InvalidArtifact):self.cache.obtain(spec,lambda work:BuildProduct('missing'))
        def no_execute(work):
            (work/'sim').write_text('not executable');return BuildProduct('sim')
        with self.assertRaises(InvalidArtifact):self.cache.obtain(spec,no_execute)

    def test_forged_key_and_unknown_schema_rejected(self):
        for field,value in (('key','wrong'),('schema',999)):
            cache=BuildCache(self.root/f'tampered-{field}',log=self.messages.append);spec=self.spec()
            result=cache.obtain(spec,self.builder);manifest=json.loads(result.manifest.read_text());manifest[field]=value
            result.manifest.chmod(0o644);result.manifest.write_text(json.dumps(manifest));result.manifest.chmod(0o444)
            self.assertEqual(cache.obtain(spec,self.builder).cache_status,'repaired')

    def test_corrupt_build_output_manifest_or_missing_file_misses(self):
        for defect in ('output','manifest','missing'):
            cache=BuildCache(self.root/f'cache-{defect}',log=self.messages.append);spec=self.spec()
            result=cache.obtain(spec,self.builder)
            if defect=='output':
                path=result.artifact_directory/'generated.cpp';path.chmod(0o644);path.write_text('changed');path.chmod(0o444)
            elif defect=='manifest':
                result.manifest.chmod(0o644);result.manifest.write_text('{broken');result.manifest.chmod(0o444)
            else:
                result.artifact_directory.chmod(0o755);(result.artifact_directory/'generated.cpp').unlink()
            self.assertEqual(cache.obtain(spec,self.builder).cache_status,'repaired')

    def test_symlink_or_path_traversal_output_is_rejected(self):
        spec=self.spec();external=self.root/'external';external.write_text('preserve')
        def link(work):
            (work/'sim').symlink_to(external);return BuildProduct('sim')
        with self.assertRaises(InvalidArtifact):self.cache.obtain(spec,link)
        self.assertEqual(external.read_text(),'preserve')
        for name in ('../external','/bin/sh','.'):
            with self.assertRaises(InvalidArtifact):self.cache.obtain(spec,lambda work:BuildProduct(name))

    def test_undeclared_dependency_rejects_publication(self):
        extra=self.root/'not-keyed.h';extra.write_text('external')
        def unknown(work):
            product=self.builder(work);return BuildProduct(product.executable,(extra,))
        with self.assertRaises(UntrackedDependency):self.cache.obtain(self.spec(),unknown)
        self.assertEqual(list((self.cache.root/'objects').iterdir()),[])

    def test_generated_dependency_inside_build_is_allowed(self):
        def generated(work):
            product=self.builder(work);return BuildProduct(product.executable,(work/'generated.cpp',))
        self.assertEqual(self.cache.obtain(self.spec(),generated).cache_status,'built')

    def test_tool_binary_and_runtime_changes_invalidate(self):
        tool=self.root/'fake-tool';tool.write_text('#!/bin/sh\necho v1\n');tool.chmod(0o755)
        first=fingerprint_toolchain({'compiler':[str(tool),'--version']},trees=[self.headers])
        spec=self.spec(toolchain=first)
        tool.write_text('#!/bin/sh\necho v2\n')
        with self.assertRaises(InputsChanged):self.cache.obtain(spec,self.builder)
        second=fingerprint_toolchain({'compiler':[str(tool),'--version']},trees=[self.headers])
        self.assertNotEqual(spec.key,self.spec(toolchain=second).key)

    def test_input_symlink_change_invalidates(self):
        target=self.root/'replacement.h';target.write_text('v2')
        alias=self.headers/'alias.h';alias.symlink_to(self.headers/'runtime.h');spec=self.spec()
        alias.unlink();alias.symlink_to(target)
        with self.assertRaises(InputsChanged):self.cache.obtain(spec,self.builder)
        self.assertNotEqual(spec.key,self.spec().key)

if __name__=='__main__':unittest.main()
