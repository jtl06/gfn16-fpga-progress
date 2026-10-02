"""Native gate preparation/report tests only; no C++/HDL execution."""
from collections import deque
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from reference import stream27_signed_boundary_regression as gate
from reference.stream27_signed_boundary_vectors import corpus

FPGA=Path(__file__).resolve().parents[1]
PRIMES=(104857601,69206017,67239937)


class VectorTests(unittest.TestCase):
    def test_all_words_replayed_with_independent_integer_due_queue(self):
        for aw in (5,16):
            text,expected=corpus(aw);self.assertEqual(expected['sha256'],gate.VECTOR_SHA[aw])
            lines=text.splitlines();self.assertEqual(lines[0],f'SBRED1 {aw} 8 16 9178')
            queue=deque([None]*4);residues=[0,0,0];payload=0;seen=0
            n=1<<aw;k=2*n+192;minimum=max(2*n+5,(2*k+2)//3+1)
            for line in lines[1:]:
                rst,valid,kind,base,word,tag,ev,ee,r0,r1,r2,etag=map(int,line.split())
                if not rst:
                    queue=deque([None]*4);residues=[0,0,0];payload=0;v=e=0
                else:
                    due=queue.popleft();value=word-(1<<32) if word>=1<<31 else word
                    legal=minimum<=base<=10**9 and abs(value)<=(k if kind else base-1)
                    queue.append((legal,value,tag) if valid else None);v=e=0
                    if due:
                        good,x,payload=due;v=int(good);e=int(not good)
                        if good:residues=[x%p for p in PRIMES]
                self.assertEqual((ev,ee,r0,r1,r2,etag),(v,e,*residues,payload));seen+=1
            self.assertEqual(seen,9178);self.assertEqual(expected['field_checks'],27534)
            self.assertEqual((expected['responses'],expected['errors'],expected['bubbles'],expected['resets']),(7922,504,569,53))
            self.assertEqual(expected['typed_coverage']['reset_ages'],31)

    def test_footer_complete_numbers_not_message_presence(self):
        _,expected=corpus(5)
        footer='SIGNED_BOUNDARY_PASS '+' '.join(f'{key}={expected[key]}' for key in gate.KEYS)+'\n'
        self.assertEqual(gate.check_output(footer,expected)['field_checks'],27534)
        for bad in (footer.replace('responses=7922','responses=7921'),footer+footer,footer.replace('edge_checks=9178',''),footer+'SIGNED_BOUNDARY_PASS success\n'):
            with self.assertRaises(ValueError):gate.check_output(bad,expected)

    def test_cpp_and_sv_closed_shape_context_reset_and_explicit_return(self):
        cpp=(FPGA/gate.BENCH).read_text();sv=(FPGA/gate.COMPILED[-1]).read_text();runner=(FPGA/gate.RUNNER).read_text()
        for anchor in ('context.threads(1)','d.threads()==1','d.final();return 0;','SBRED_VALID_OR_LATENCY_MISMATCH','SBRED_INTEGER_OR_HOLD_MISMATCH',
                       'SBRED_ASYNC_OR_COMBINATIONAL_LEAK','SBRED_FALLING_EDGE_LEAK','previous={0,0,{0,0,0},{0,0,0}}',
                       'actual.valid==7*ev && actual.error==7*ee','actual.residue[f]==expected_residue[f] && actual.tag[f]==expected_tag'):
            self.assertIn(anchor,cpp)
        self.assertIn('for(genvar field=0;field<3;',sv)
        self.assertIn('.BLOCKS(8),.PAYLOAD_W(16)',sv)
        self.assertIn("'-j','2','--threads','1'",runner)
        self.assertIn('-Werror=return-type',runner)
        self.assertIn('check_output(run(',runner)
        self.assertNotIn('infra.execute(',runner);self.assertNotIn('infra.prepare(',runner)


class PreparationTests(unittest.TestCase):
    def test_source_pins_and_frozen_resource_infrastructure(self):
        pins=gate.source_pins(FPGA);self.assertEqual(len(pins),13)
        self.assertEqual(pins[gate.INFRA],gate.INFRA_SHA)
        infra=gate.load_infrastructure(FPGA)
        self.assertEqual(str(infra.LOCK),'/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock')
        self.assertEqual(infra.check_probe('{"context_threads":1,"model_threads":1,"expected_threads":1}'),dict(context_threads=1,model_threads=1,expected_threads=1))
        with self.assertRaises(ValueError):infra.check_probe('{"context_threads":2,"model_threads":2,"expected_threads":1}')

    def test_manifest_archive_member_bytes_bootstrap_and_tampered_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            temp=Path(directory).resolve();out=temp/'stage';manifest=gate.prepare(out);digest=gate.sha(out/'manifest.json')
            gate.verify_manifest(FPGA,out/'manifest.json',digest,5);gate.verify_manifest(FPGA,out/'manifest.json',digest,16)
            with tarfile.open(out/'source.tar.gz') as archive:
                names=[member.name for member in archive.getmembers()]
                self.assertEqual(len(names),13);self.assertEqual(set(names),{'fpga/'+name for name in manifest['sources']})
                for member in archive:
                    self.assertTrue(member.isfile());self.assertEqual(hashlib.sha256(archive.extractfile(member).read()).hexdigest(),manifest['sources'][member.name[5:]])
                archive.extractall(temp/'extracted',filter='data')
            root=temp/'extracted/fpga'
            code='import importlib.util,pathlib,sys; r=pathlib.Path(sys.argv[1]); s=importlib.util.spec_from_file_location("gate",r/"reference/stream27_signed_boundary_regression.py"); g=importlib.util.module_from_spec(s); s.loader.exec_module(g); p=g.source_pins(r); v=g.load_project(r,p); assert v.corpus(5)[1]["sha256"]==g.VECTOR_SHA[5]; print("isolated-bootstrap-pass")'
            result=subprocess.run([sys.executable,'-I','-S','-B','-c',code,str(root)],cwd=FPGA.parent,text=True,capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.strip(),'isolated-bootstrap-pass')
            bad=dict(manifest);bad['latency']=3;(out/'manifest.json').write_text(json.dumps(bad))
            with self.assertRaises(ValueError):gate.verify_manifest(FPGA,out/'manifest.json',gate.sha(out/'manifest.json'),5)
            with self.assertRaises(ValueError):gate.prepare(out)


if __name__=='__main__':unittest.main()
