"""G4 source/preparation contracts only. No HDL/cloud execution."""
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from fpga.reference import core27_prefetch_r2_rootfused_crtmont_regression as r
from fpga.reference import core27_prefetch_r2_rootfused_crtmont_structure as s
from fpga.reference import core27_prefetch_r2_regression as baseline

ROOT=Path(__file__).resolve().parents[1]


class RootfusedCrtMontTests(unittest.TestCase):
    def test_exact_two_substitution_core_and_frozen_dependency_pins(self):
        s.validate_files(ROOT);pins=r.source_pins(ROOT)
        self.assertEqual(len(pins),65)
        old=(ROOT/'rtl/kernel'/(s.ANCESTOR+'.sv')).read_text()
        new=(ROOT/'rtl/kernel'/(s.CANDIDATE+'.sv')).read_text()
        self.assertEqual(new.replace(s.CANDIDATE,s.ANCESTOR).replace('genefer_crt3_27_mont_pipe crt (','genefer_crt3_27_pipe crt ('),old)
        self.assertEqual(len(s.KERNEL_PINS),16)
        self.assertNotIn('genefer_crt3_27_pipe.sv',s.KERNEL_PINS)

    def test_bench_expected_tail_and_live_crt_abort_only(self):
        old=(ROOT/'rtl/tb'/(s.OLD_BENCH+'.cpp')).read_text()
        new=(ROOT/'rtl/tb'/(s.NEW_BENCH+'.cpp')).read_text()
        self.assertEqual(new,s.bench_source(old))
        self.assertIn('d.crt_cycles>=18',new);self.assertIn('(n+15)/16+17+',new)
        for guard in ('abort did not interrupt requested live phase','busy host read leaked','square mismatch',
                      'error quarantine mismatch','fused conversion counter mismatch','d.final();return 0;'):
            self.assertIn(guard,new)

    def test_compile_model_runtime_flags_and_order(self):
        sources=[ROOT/'rtl/kernel'/name for name in r.COMPILED_ORDER]
        for aw in (5,16):
            cmd=r.compile_command(ROOT,sources,Path('/tmp/build'),aw)
            self.assertEqual(cmd[4:8],['-j','2','--threads','1'])
            self.assertIn('-Werror=return-type',cmd[cmd.index('-CFLAGS')+1])
            self.assertIn('-DCORE27_PREFETCH_R2_RUNTIME_THREADS=1',cmd[cmd.index('-CFLAGS')+1])
            self.assertEqual(cmd[-17:-1],list(map(str,sources)))
            self.assertTrue(cmd[-1].endswith(s.NEW_BENCH+'_threaded.cpp'))
        with self.assertRaises(ValueError):r.compile_command(ROOT,sources,Path('/tmp/build'),1)

    def test_exact_parent_minus45_metrics_and_validator(self):
        evidence=r.parent_evidence(ROOT)
        for aw in (5,16):
            rows=evidence[str(aw)]['metrics'];wanted=[dict(row,cycles=row['cycles']-45,crt=row['crt']-45) for row in rows]
            r.check_matched_metrics(wanted,rows)
            row=wanted[0];line=row['case']+' '+' '.join(f'{key}={row[key]}' for key in baseline.FIELDS)
            text=line+f'\nPASS n={1<<aw} squares=1 readbacks=1 aborts=0\n'
            parsed=r.validate_output(text,f"RUN {row['case']} 0\n",aw,baseline)
            self.assertEqual(parsed,[row])
            for key in ('cycles','crt','carry','ntt','conversion','passes','profile_hits'):
                bad=[dict(x) for x in wanted];bad[0][key]+=1
                with self.subTest(aw=aw,key=key),self.assertRaises(ValueError):r.check_matched_metrics(bad,rows)
        self.assertEqual(evidence['16']['metrics'][0]['cycles']-45,41663)
        self.assertEqual(evidence['16']['metrics'][1]['cycles']-45,32920)

    def test_g2_complete_receipt_and_source_binding(self):
        report=r.check_g2(ROOT/r.G2_REPORT)
        self.assertEqual(report['status'],'passed_required_mutations_and_fresh_controls')
        with patch.object(r,'G2_SHA','0'*64):
            with self.assertRaisesRegex(ValueError,'G2'):r.check_g2(ROOT/r.G2_REPORT)

    def test_no_offhost_execution(self):
        with patch.object(r.socket,'gethostname',return_value='not-aethia'),patch.object(r.subprocess,'Popen',side_effect=AssertionError('no execution')):
            with self.assertRaises(ValueError):r.execute(5,Path('/tmp/newout'),Path('/tmp/manifest'),'0'*64)

    def test_fresh_closed_preparation_and_clean_snapshot_bootstrap(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage=Path(temporary)/'stage'
            result=subprocess.run([sys.executable,'-B',str(ROOT/r.RUNNER),'--prepare',str(stage)],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            manifest,pins=r.verify_manifest(ROOT,stage/'manifest.json',r.sha(stage/'manifest.json'),5)
            self.assertEqual(manifest['compiled_source_order'],list(r.COMPILED_ORDER))
            self.assertEqual(r.sha(stage/'g2-report.json'),r.G2_SHA)
            snapshot=Path(temporary)/'snapshot';snapshot.mkdir()
            with tarfile.open(stage/'source.tar.gz') as tar:
                self.assertEqual(set(tar.getnames()),{'fpga/'+name for name in pins})
                self.assertTrue(all(member.isfile() for member in tar.getmembers()))
                tar.extractall(snapshot,filter='data')
            code="""import runpy,sys
from pathlib import Path
d=runpy.run_path(sys.argv[1]);root=Path(sys.argv[1]).resolve().parents[1]
b,s,sources=d['load_project'](root,d['source_pins'](root),isolated=True)
assert len(sources)==16
assert not list((root/'reference').rglob('*.pyc'))
print('PASS')
"""
            result=subprocess.run([sys.executable,'-B','-c',code,str(snapshot/'fpga'/r.RUNNER)],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout,'PASS\n')


    def test_broadcast_preparation_and_exact_r3_identity_preserved(self):
        stage=ROOT/'results/throughput-20260929/core27-prefetch-r2-host-broadcast-crtmont-stage-v1'
        self.assertEqual(r.sha(stage/'manifest.json'),'e48f896046af4e36c2c6ed76549a3d10892dc0d9b154181aebb452419ded3bd1')
        self.assertEqual(r.sha(stage/'source.tar.gz'),'bdab3502ada1b875a52036e08c85f1475fdeca7efbbac8ed326c8692d4504263')
        self.assertEqual(r.FIXED_PINS['docs/briefs/2026-09-30-answers-B20260930-r3.md'],'39acc1d9537aff429f00ce2c23161be2df9553eecb0fba03b7c7907ba6a367ee')
        parent=r.parent_evidence(ROOT)
        self.assertEqual(parent['5']['metrics'][0]['cycles'],3460)
        self.assertEqual(parent['5']['metrics'][1]['cycles'],371)
        self.assertEqual(parent['5']['vectors']['squares'],568)
        self.assertEqual(parent['16']['vectors']['squares'],12)
        self.assertIn('genefer_ntt_banked27_prefetch_r2_orient8_rootfused_engine.sv',r.COMPILED_ORDER)
        self.assertNotIn('genefer_ntt_banked27_prefetch_r2_engine.sv',r.COMPILED_ORDER)


if __name__=='__main__':unittest.main()
