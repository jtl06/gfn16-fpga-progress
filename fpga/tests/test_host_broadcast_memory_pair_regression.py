"""Local Python-only runner contracts: no compiler, HDL, or remote execution."""
import ast
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from reference import host_broadcast_memory_pair_regression as r
from reference import host_broadcast_memory_oracle as oracle


class HostMemoryRunnerTests(unittest.TestCase):
    def footer(self, aw=8, field=1):
        return oracle.canonical_footer(oracle.expected_result(aw, field))+'\n'

    def fatal(self, case=('baseline','scalar','p',0), trailer=True):
        instance,kind,payload,quarter=case
        number=0 if instance=='baseline' else 1
        filename=f'{r.CHILD}.sv'
        value=(f'EXPECT_CANONICAL_ASSERT instance={instance} kind={kind} payload={payload} quarter={quarter}\n'
               f'[0] %Fatal: {filename}:395: Assertion failed in TOP.{r.TOP}.instances[{number}].'
               f'{instance}.dut.child.memories[{quarter*16}]: noncanonical NTT27 data write\n')
        if trailer:value+=f'%Error: {r.SOURCE}/rtl/kernel/{filename}:395: Verilog $stop\nAborting...\n'
        return value

    def test_counter_pins_independent_all_profiles(self):
        root=Path(r.__file__).resolve().parents[1]
        self.assertEqual(r.sha(root/r.ORACLE),r.ORACLE_SHA)
        for aw,field in sorted(r.PROFILES):
            with self.subTest(aw=aw,field=field):
                expected=oracle.expected_result(aw,field)['counts']
                self.assertEqual(r.expected_counts(aw,field),expected)
                self.assertEqual(r.check_normal(0,self.footer(aw,field),aw,field),expected)

    def test_each_counter_corruption_rejected(self):
        normal=self.footer()
        for key,value in r.expected_counts(8,1).items():
            with self.subTest(key=key),self.assertRaises(ValueError):
                r.check_normal(0,normal.replace(f'{key}={value}',f'{key}={value+1}'),8,1)
        for bad in (normal+normal,'unrelated\n'+normal,normal+'trailer\n',normal.replace('edges=3656','edges=-1')):
            with self.assertRaises(ValueError):r.check_normal(0,bad,8,1)
        for status in (False,True,1,-6,134,None):
            with self.assertRaises(ValueError):r.check_normal(status,normal,8,1)

    def test_explicit_profile_boundary(self):
        self.assertEqual(r.profile(16,1)['p'],104857601)
        for aw,field in ((16,2),(16,3),(9,1),(8,0),(8,4),(True,1),(8,True)):
            with self.assertRaises(ValueError):r.profile(aw,field)
        self.assertEqual({aw:len(r.illegal_cases(aw)) for aw in (1,5,8,16)}, {1:12,5:18,8:30,16:30})
        for aw in (True,2,9):
            with self.assertRaises(ValueError):r.illegal_cases(aw)

    def test_compile_exact_geometry_threads(self):
        root=Path('/source');config=r.profile(16,1);order=['first.sv','bench.cpp']
        command=r.compile_command(root,Path('/scratch/build'),config,order)
        self.assertEqual(command, ['verilator','--cc','--exe','--build','-j','2','--threads','1',
            '--top-module',r.TOP,'-GAW=16','-GP=104857601','-GQ=4190109697','-CFLAGS',
            '-std=c++17 -DHOST_BROADCAST_AW=16 -DHOST_BROADCAST_P=104857601u -DHOST_BROADCAST_Q=4190109697u',
            '--Mdir','/scratch/build','/source/first.sv','/source/bench.cpp'])

    def test_probe_parameter_and_integer_types(self):
        config=r.profile(8,1)
        wanted=dict(context_threads=1,model_threads=1,aw=8,p=config['p'],q=config['q'])
        r.check_probe(json.dumps(wanted),config)
        for key in wanted:
            for value in (True,0,str(wanted[key])):
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                    r.check_probe(json.dumps(dict(wanted,**{key:value})),config)
        with self.assertRaises(ValueError):r.check_probe(json.dumps(dict(wanted,extra=1)),config)

    def test_exact_all_assertion_roles(self):
        for case in r.illegal_cases(8):
            for status in (1,-6,134):
                self.assertTrue(r.assertion_rejection(status,self.fatal(case),case))
            self.assertTrue(r.assertion_rejection(-6,self.fatal(case,trailer=False),case))

    def test_false_failures_never_count_as_assertion(self):
        case=('candidate','vector','highbit',3);good=self.fatal(case)
        for status in (False,True,0,2,3,-9,-11,None):
            self.assertFalse(r.assertion_rejection(status,good,case))
        for old,new in (('instances[1]','instances[0]'),('memories[48]','memories[0]'),
                        (':395:',':396:'),('payload=highbit','payload=p'),
                        ('noncanonical NTT27 data write','unrelated failure'),('TOP.','OTHER.'),
                        ('Verilog $stop','Verilog $finish')):
            self.assertFalse(r.assertion_rejection(-6,good.replace(old,new),case))
        for bad in (good+'PASS\n',good+'%Error: unrelated\n','Killed\n',
                    good.replace('Aborting...','out of memory'),good.replace('/snapshot-v1/','/snapshot-v2/')):
            self.assertFalse(r.assertion_rejection(-6,bad,case))
        self.assertFalse(r.assertion_rejection(-6,good,('candidate','vector','highbit',True)))

    def test_prepare_is_fresh_fourteen_source_bundle_only(self):
        with tempfile.TemporaryDirectory() as temporary,patch.object(r.subprocess,'Popen',side_effect=AssertionError('no processes')):
            out=Path(temporary)/'prepared';manifest=r.prepare(out)
            self.assertEqual(manifest['profile'],r.profile(8,1))
            self.assertEqual(len(manifest['sources']),14)
            self.assertEqual(len(manifest['compiled_source_order']),10)
            self.assertEqual(manifest['runner_coverage_annotation'],r.COVERAGE_NOTE)
            self.assertEqual(manifest['archive_sha256'],r.sha(out/'sources.tar.gz'))
            with tarfile.open(out/'sources.tar.gz') as archive:
                self.assertEqual(set(archive.getnames()),{'fpga/'+name for name in manifest['sources']})
                for name,h in manifest['sources'].items():
                    self.assertEqual(hashlib.sha256(archive.extractfile('fpga/'+name).read()).hexdigest(),h)
            with self.assertRaises(FileExistsError):r.prepare(out)
            full=r.prepare(Path(temporary)/'full',16,1)
            self.assertEqual(full['expected_counts']['edges'],611608)

    def test_source_oracle_pin_mismatch_blocks_before_prepare(self):
        with tempfile.TemporaryDirectory() as temporary,patch.object(r,'ORACLE_SHA','0'*64):
            out=Path(temporary)/'prepared'
            with self.assertRaisesRegex(ValueError,'pinned source changed'):r.prepare(out)
            self.assertFalse(out.exists())

    def test_no_execution_off_host(self):
        with patch.object(r.socket,'gethostname',return_value='not-aethia'),patch.object(r.subprocess,'Popen',side_effect=AssertionError('must not launch')):
            with self.assertRaisesRegex(ValueError,'aethia'):r.execute(Path('/tmp/out'),Path('/tmp/manifest'),'0'*64)

    def test_allocation_unlink_race_tolerated(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'gone'
            with patch.object(r.os,'walk',return_value=[(temporary,[],['gone'])]):
                self.assertEqual(r.allocated(Path(temporary)),0)
            path.write_bytes(b'x'*1024)
            self.assertGreater(r.allocated(Path(temporary)),0)

    def test_runner_has_no_project_imports(self):
        source=Path(r.__file__).read_text();tree=ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom):self.assertIn(node.module,{'pathlib'})
            if isinstance(node,ast.Import):
                self.assertFalse(any(x.name.startswith(('reference','tools','tests')) for x in node.names))
        self.assertIn("mode.add_argument('--execute',action='store_true')",source)
        self.assertIn('default=8',source)
        self.assertNotIn('shell=True',source)


if __name__=='__main__':unittest.main()
