"""Pure qualification recipe/packet rejection tests, never native execution."""
import hashlib
import gzip
import io
import importlib.util
import json
from pathlib import Path
import re
import shutil
import tempfile
import tarfile
import types
import unittest
from fpga.reference import core27_prefill_pipe_qualification_v1 as recipe
from fpga.reference import core27_prefill_pipe_qualification_prepare_v1 as prep
from fpga.reference import core27_prefill_pipe_v1_mutations as mutations

spec=importlib.util.spec_from_file_location('native_t5b_qualification',prep.ROOT/'tools/native_t5b_qualification_v1.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


class Recipes(unittest.TestCase):
    def test_reuse_predecessor_rejects_wrong_configuration_and_elf(self):
        # Synthetic nonexecuted ELF-shaped bytes exercise the read-only
        # predecessor verifier; no tool or HDL model is invoked.
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp).resolve();root=base/'root';root.mkdir();out=base/'out';out.mkdir()
            paths={}
            for key in ('taskset','verilator','python'):
                paths[key]=base/key;paths[key].write_bytes(key.encode())
            def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
            def expand(argv,exe,root):return [s.replace('{exe}',str(exe)).replace('{root}',str(root)) for s in argv]
            helper=types.SimpleNamespace(tools_for=lambda profile:paths,PROFILES={'aethia':{}},expand=expand)
            source={'s.sv':b'// source','b.cpp':b'// bench'}
            pins={name:hashlib.sha256(data).hexdigest() for name,data in source.items()}
            manifest=dict(sources=pins,build=dict(top='Probe',parameters=dict(AW=16,NTT_LANES=64),
                cflags=['-std=c++17','-Werror=return-type'],sv_sources=['s.sv'],cpp_source='b.cpp'),
                probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
                steps=[dict(name='case',argv=['{exe}','{root}/vector'],expected_returncode=0,expected_stdout='PASS\n',expected_stderr='')])
            (out/'approved-manifest.json').write_text(json.dumps(manifest));manifest_sha=sha(out/'approved-manifest.json')
            def archive(path,members):
                with tarfile.open(path,'w:gz') as tar:
                    for name,data in members.items():
                        info=tarfile.TarInfo(name);info.size=len(data);tar.addfile(info,io.BytesIO(data))
            archive(out/'sources.tar.gz',source);archive(out/'generated-sources.tar.gz',{'model.cpp':b'generated'})
            model=b'\x7fELFtest-only-not-executable'
            with gzip.open(out/'model.gz','wb') as stream:stream.write(model)
            (out/'case.log').write_text('PASS\n');(out/'case.stderr.log').write_text('')
            prefix=[str(paths['taskset']),'-c','4,6'];directory=Path('/dev/shm/gfn16-source-gate-test/build');exe=directory/'VProbe'
            command=prefix+[str(paths['verilator']),'--cc','--exe','--build','-j','2','--threads','1','--top-module','Probe',
                '-GAW=16','-GNTT_LANES=64','-CFLAGS','-std=c++17 -Werror=return-type','--Mdir',str(directory),str(root/'s.sv'),str(root/'b.cpp')]
            steps=[dict(name=name,returncode=0,error=None,command=[]) for name in ('verilator-version','compiler-version','build','probe','case')]
            steps[2]['command']=command;steps[3]['command']=prefix+expand(manifest['probe']['argv'],exe,root)
            steps[4]['command']=prefix+expand(manifest['steps'][0]['argv'],exe,root)
            report=dict(status='completed_native_commands_unreviewed',manifest_sha256=manifest_sha,sources=pins,
                artifacts={p.name:sha(p) for p in out.iterdir()},generated_source_sha256={'model.cpp':hashlib.sha256(b'generated').hexdigest()},
                tool_sha256={str(p):sha(p) for p in paths.values()},steps=steps,scratch=str(directory.parent),
                probe=manifest['probe']['expected_json'],executable_sha256=hashlib.sha256(model).hexdigest())
            def save():(out/'report.json').write_text(json.dumps(report))
            save();self.assertEqual(runner.completed_report(out,manifest,manifest_sha,helper,root),report)
            steps[2]['command']=command.copy();steps[2]['command'][steps[2]['command'].index('-GAW=16')]='-GAW=5';save()
            with self.assertRaisesRegex(ValueError,'RTL/harness/config'):runner.completed_report(out,manifest,manifest_sha,helper,root)
            steps[2]['command']=command
            with gzip.open(out/'model.gz','wb') as stream:stream.write(b'foreign')
            report['artifacts']['model.gz']=sha(out/'model.gz');save()
            with self.assertRaisesRegex(ValueError,'ELF archive identity'):runner.completed_report(out,manifest,manifest_sha,helper,root)

    def test_unsafe_archive_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'unsafe.tar.gz'
            with tarfile.open(path,'w:gz') as tar:
                entry=tarfile.TarInfo('../escape');entry.size=1;tar.addfile(entry,io.BytesIO(b'x'))
            with self.assertRaisesRegex(ValueError,'safe unique regular'):runner.archive_inventory(path)

    def test_complete_nonaliasing_aw16_matrix(self):
        anchor,groups=recipe.full_matrix();cases=anchor+[s for rows in groups.values() for s in rows]
        self.assertEqual(len(cases),93);self.assertEqual(len({s['name'] for s in cases}),93)
        self.assertEqual(len(anchor),9)
        for fault in ('reset','host-error','carry-error'):
            for row,index in [('first',0),('middle',2048),('final',4095)]:
                selected=[s for s in cases if s['name'].startswith(fault+'-'+row+'-e')]
                self.assertEqual({int(s['argv'][3]) for s in selected},set(range(10)))
                self.assertTrue(all(f'row_index={index} middle_aliases_final=0' in s['expected_stdout'] for s in selected))

    def test_aw16_harness_exact_small_delta(self):
        text=(prep.ROOT/recipe.AW16_BENCH).read_text()
        self.assertEqual(text,recipe.aw16_harness())
        self.assertIn('fast?0:4105',text);self.assertIn('n==65536',text)
        self.assertNotIn('non-final emission probes target commit E0 only',text)

    def test_all_eight_have_same_normalized_control(self):
        control,mutants,contracts=recipe.shared_mutants()
        self.assertEqual(len(mutants),8)
        self.assertNotIn('T5_EMIT_SIGNED32_REPRESENTATION',control[mutations.CARRY])
        for name,changed in mutants.items():
            differences={key for key in control if control[key]!=changed[key]}
            self.assertEqual(differences,{mutations.CARRY} if name in mutations.TEE_MUTANTS else {mutations.CORE,mutations.BRIDGE})
            self.assertEqual(contracts[name]['expected_signal'],6)

    def test_typed_rejection_not_generic_failure(self):
        _,_,contracts=recipe.shared_mutants();c=contracts['late_host_error']
        line=c['lines'][0]
        text=f"[123] %Error: /source/{c['observer']}:{line}: Assertion failed in {c['required_scope']}: {c['fatal']}\n"
        self.assertEqual(runner.typed_fatal(text,-6,c)['fatal'],c['fatal'])
        for output,code in [(text,0),(text,1),(text.replace(str(line)+':',str(line+1)+':'),-6),
                            (text.replace(c['fatal'],'OTHER_FATAL'),-6),(text+'T5_TARGET_PASS x\n',-6),
                            (text.replace(c['required_scope'],'TOP.foreign'),-6),(text+text,-6)]:
            with self.assertRaises(ValueError):runner.typed_fatal(output,code,c)

    def test_fresh_packet_complete_sources_roles_and_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp).resolve()/'packet';report=prep.prepare(out)
            bundle,roles=runner.verify_bundle(out/'manifest.json',report['manifest_sha256'],out/'source/fpga')
            self.assertEqual(len(roles),10);self.assertEqual(len(roles['shared-control']['steps']),8)
            self.assertEqual(roles['aw16-anchor']['build'],bundle['reuse_build'])
            self.assertEqual(roles['aw16-anchor']['build']['parameters'],dict(AW=16,NTT_LANES=64))
            actual=runner.archive_inventory(out/'source.tar.gz')
            self.assertEqual(actual,{'fpga/'+name:pin for name,pin in bundle['sources'].items()})
            for role,m in roles.items():
                self.assertTrue(all(p in bundle['sources'] for p in m['build']['sv_sources']+[m['build']['cpp_source']]))
                self.assertTrue(all(re.fullmatch('[a-z][a-z0-9-]*',s['name']) for s in m['steps']))
                if role in mutations.NAMES:
                    self.assertEqual(m['steps'][0]['expected_returncode'],-6)
                    control=next(s for s in roles['shared-control']['steps'] if s['name']=='control-'+role.replace('_','-'))
                    self.assertEqual(m['steps'][0]['argv'],control['argv'])
            with self.assertRaisesRegex(ValueError,'fresh qualification stage'):prep.prepare(out)

    def test_packet_tamper_rejected_before_helper_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp).resolve()/'packet';report=prep.prepare(out)
            (out/'source/fpga/extra.py').write_text('raise RuntimeError("must never import")\n')
            with self.assertRaisesRegex(ValueError,'source closure before imports'):
                runner.verify_bundle(out/'manifest.json',report['manifest_sha256'],out/'source/fpga')

    def test_bad_manifest_hash_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'manifest.json';p.write_text('{}')
            with self.assertRaisesRegex(ValueError,'approved file SHA'):runner.read_pinned(p,'0'*64)

    def test_vector_reused_not_generated(self):
        path=prep.ROOT/recipe.AW16_VECTOR
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),recipe.AW16_VECTOR_SHA)
        values=path.read_text().split()
        self.assertEqual(values[:3],['65536','604832956','1000000000'])
        self.assertEqual(len(values),3+4*65536)


if __name__=='__main__':unittest.main()
