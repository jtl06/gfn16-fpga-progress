"""Prepare/vector/guard tests only. Never invoke Verilator or compiled RTL."""
import ast
import hashlib
import json
from pathlib import Path
import re
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from reference import montgomery27_canonical_regression as r

ROOT=Path(__file__).resolve().parents[1]


class CanonicalGateTests(unittest.TestCase):
    def test_all_source_pins_before_execution(self):
        pins=r.source_pins(ROOT)
        self.assertEqual(len(pins),5)
        self.assertEqual(pins['rtl/kernel/genefer_montgomery_mul27_canonical_pipe.sv'],
                         '1d29fffb22b5ab9414d83b2cdde4d4068d605b51d60bda6d7b5d47688e181352')

    def test_prepare_is_only_five_sources_with_fresh_destination(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(r.subprocess,'Popen',side_effect=AssertionError('must not launch')):
            out=Path(tmp)/'prepared';manifest=r.prepare(out)
            self.assertEqual(manifest['status'],'prepared_not_executed')
            self.assertEqual(set(p.name for p in out.iterdir()),{'sources.tar.gz','manifest.json'})
            with tarfile.open(out/'sources.tar.gz') as tar:
                self.assertEqual(set(tar.getnames()),{'fpga/'+p for p in manifest['sources']})
                for name,h in manifest['sources'].items():
                    self.assertEqual(hashlib.sha256(tar.extractfile('fpga/'+name).read()).hexdigest(),h)
            self.assertEqual(r.sha(out/'sources.tar.gz'),manifest['archive_sha256'])
            with self.assertRaises(FileExistsError):r.prepare(out)

    def test_ordinary_integer_vectors_and_independent_scoreboard(self):
        for p,q in r.FIELDS:
            text,summary=r.vectors(p,q);pending=[];checked=canceled=holds=0;inv=pow(1<<32,-1,p)
            both=set();continuous=longest=0
            for clock,line in enumerate(text.splitlines()):
                reset,valid,a,b,value=map(int,line.split())
                self.assertIn(reset,(0,1));self.assertIn(valid,(0,1))
                if not reset:canceled+=len(pending);pending=[]
                elif valid:
                    self.assertTrue(a<p and b<p)
                    self.assertEqual(value,((a*b)%p)*inv%p)
                    pending.append((clock+3,value))
                    t=a*b;m=(t*q)&0xffffffff;both.add((t>>32)<((m*p)>>32))
                if pending and pending[0][0]==clock:pending.pop(0);checked+=1
                else:holds+=1
                continuous=continuous+1 if reset and valid else 0;longest=max(longest,continuous)
            self.assertFalse(pending);self.assertEqual(both,{False,True});self.assertGreater(longest,100)
            self.assertEqual((checked,canceled,holds,clock+1),tuple(summary[k] for k in ('checked','canceled','hold_checks','cycles')))
            self.assertEqual(summary['reset_ages'],[0,1,2,3]);self.assertEqual(summary['reset_occupancies'],[1,2,3,4])
            self.assertGreater(canceled,0)

    def test_normal_footer_exact_and_failure_never_passes(self):
        _,s=r.vectors(*r.FIELDS[0])
        output='PASS P={p} checked={checked} canceled={canceled} hold_checks={hold_checks} cycles={cycles}\n'.format(**s)
        r.check_normal(0,output,s)
        for rc,log in ((True,output),(1,output),(0,output+'extra\n'),(0,output.replace('checked=','checks='))):
            with self.assertRaises(ValueError):r.check_normal(rc,log,s)

    def test_only_correct_retained_assertion_can_reject(self):
        source=(ROOT/'rtl/kernel'/(r.TOP+'.sv')).read_text()
        for msg in ('noncanonical Montgomery27 input','unsupported sparse Montgomery27 modulus','invalid sparse Montgomery inverse'):
            lineno=next(i+1 for i,line in enumerate(source.splitlines()) if '$fatal(1,"'+msg+'");' in line)
            log=f'[0] %Error: {r.SOURCE}/rtl/kernel/{r.TOP}.sv:{lineno}: Assertion failed in TOP.{r.TOP}: {msg}\nAborting...\n'
            self.assertTrue(r.assertion_rejection(-6,log,msg,source))
            for rc,changed in ((True,log),(0,log),(137,log),(-6,log.replace(f':{lineno}:',':999:')),
                               (-6,log.replace(msg,'unrelated assertion')),(-6,log+'PASS invalid\n'),
                               (-6,log+'%Fatal: other failure\n')):
                self.assertFalse(r.assertion_rejection(rc,changed,msg,source))
        self.assertFalse(r.assertion_rejection(1,'bad_alloc / timeout / Segmentation fault','noncanonical Montgomery27 input',source))

    def test_matching_stop_trailer_only(self):
        source=(ROOT/'rtl/kernel'/(r.TOP+'.sv')).read_text();message='noncanonical Montgomery27 input'
        line=next(i+1 for i,s in enumerate(source.splitlines()) if '$fatal(1,"'+message+'");' in s)
        primary=f'[0] %Fatal: {r.TOP}.sv:{line}: Assertion failed in TOP.{r.TOP}: {message}\n'
        trailer=f'%Error: {r.SOURCE}/rtl/kernel/{r.TOP}.sv:{line}: Verilog $stop\n'
        self.assertTrue(r.assertion_rejection(-6,primary+trailer+'Aborting...\n',message,source))
        self.assertTrue(r.assertion_rejection(-6,primary+'Aborting...\n',message,source))
        for bad in (trailer.replace(f':{line}:',':999:'),trailer.replace(r.TOP,'other_module'),
                    trailer.replace('Verilog $stop','unrelated error'),trailer+trailer,
                    trailer+'%Error: unrelated\n'):
            self.assertFalse(r.assertion_rejection(-6,primary+bad+'Aborting...\n',message,source))
        self.assertFalse(r.assertion_rejection(True,primary+trailer,message,source))

    def test_bench_oracle_latency_reset_hold_and_thread_contract(self):
        source=(ROOT/'rtl/tb/montgomery27_canonical_pipe.cpp').read_text()
        for needed in ('context.threads(1)','product(lhs,rhs,p,inverse)','queue.push_back({clock+3,expected_value})',
                       'canceled+=queue.size();queue.clear();held=0','d.result>>27',
                       'invalid-cycle result hold mismatch','truncated vector row','--runtime-probe'):
            self.assertIn(needed,source)
        self.assertLess(source.index('context.threads(1)'),source.index(' d{&context}'))
        self.assertNotIn('m_s2',source);self.assertNotIn('mp_hi',source)

    def test_execute_rejects_non_aethia_before_resources_or_process(self):
        with patch.object(r.socket,'gethostname',return_value='local-mac'), \
             patch.object(r.subprocess,'Popen',side_effect=AssertionError('must not launch')):
            with self.assertRaisesRegex(ValueError,'aethia'):
                r.execute(Path('/tmp/unused'),Path('/tmp/no-manifest'),'0'*64)

    def test_no_project_imports_and_scoped_compile_contract(self):
        source=(ROOT/'reference/montgomery27_canonical_regression.py').read_text();tree=ast.parse(source)
        self.assertFalse(any(isinstance(n,ast.ImportFrom) and n.level for n in ast.walk(tree)))
        for needed in ("affinity==[0,2]","memory!='max' and 0<int(memory)<=6*GiB",
                       "'-j','2','--threads','1'",'with LOCK.open(\'r\')',
                       "dir='/dev/shm'",'32*MiB-allocated(out)','--execute','--prepare'):
            self.assertIn(needed,source)
        self.assertNotIn('ThreadPoolExecutor',source)

    def test_allocated_handles_compiler_temp_disappearance(self):
        class Stat:st_blocks=3
        with patch.object(r.os,'walk',return_value=[('/scratch',[],['gone','kept'])]), \
             patch.object(Path,'lstat',side_effect=[FileNotFoundError('unlinked'),Stat()]):
            self.assertEqual(r.allocated(Path('/scratch')),1536)


if __name__=='__main__':unittest.main()
