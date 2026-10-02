import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from fpga.reference import stream27_commutator_sync_regression as gate
from fpga.reference.stream27_commutator_sync_structure import validate
from fpga.reference.stream27_commutator_sync_vectors import corpus
from fpga.reference.stream27_commutator_sync_model import Pair,Token

ROOT=Path(__file__).resolve().parents[1]


class NativePreparation(unittest.TestCase):
    def test_RTL_source_bound_sync_shape(self):
        self.assertFalse(validate(ROOT)['RAM_payload_reset'])
        self.assertEqual(len(gate.source_pins(ROOT)),12)

    def test_corpus_exact_pins_and_synchronous_replay(self):
        for depth in (1,2,4,16,4096):
            text,counts=corpus(depth);self.assertEqual(counts['sha256'],gate.VECTOR_SHA[depth])
            candidate=Pair(depth,max(8,2*depth),synchronous=True)
            for line in text.splitlines()[1:]:
                r=list(map(int,line.split()))
                pair=(Token(r[3],r[7],r[8],r[5]),Token(r[4],r[7],r[8],r[6])) if r[1] else None
                valid,error,out=candidate.edge(pair,start=bool(r[2]),reset=not r[0],
                     enabled=(bool(r[9]&1),bool(r[9]&2)),generations=(r[10]&255,r[10]>>8))
                self.assertEqual((int(valid),int(error)),tuple(r[11:13]))
                expected=[out[0].data,out[1].data,out[0].index,out[1].index,out[0].context,out[0].generation] if out else [-1]*6
                self.assertEqual(r[13:],expected)

    def test_exact_footer_and_tampering(self):
        _,expected=corpus(1)
        keys=('depth','frame_ticks','events','valid','errors','resets','before_checks','edge_checks')
        line='COMM_SYNC_PASS '+' '.join(f'{k}={expected[k]}' for k in keys)+'\n'
        self.assertEqual(gate.check_output(line,expected),{k:expected[k] for k in keys})
        for k in keys:
            with self.assertRaises(ValueError):gate.check_output(line.replace(f'{k}={expected[k]}',f'{k}={expected[k]+1}'),expected)
        with self.assertRaises(ValueError):gate.check_output(line*2,expected)

    def test_no_native_local_and_inherited_safety_controls(self):
        source=(ROOT/gate.RUNNER).read_text()
        for s in ("socket.gethostname()=='aethia'",'cpus==[4,6]','int(memory)<=4*GIB',
                  'resource.RLIMIT_AS,(4*GIB,4*GIB)','32*MIB','10*GIB','256*MIB','2*GIB',
                  'time.monotonic()-started<900',"LOCK.open('r')",'-Werror=return-type',
                  "'--threads','1'",'os.killpg',"manifest['compiled']==[RTL]"):
            self.assertIn(s,source)
        self.assertNotIn('-Wno',source)
        bench=(ROOT/gate.BENCH).read_text()
        for s in ('COMM_ASYNC_OR_COMBINATIONAL_LEAK','COMM_FALLING_LEAK','COMM_DATA_OR_TAG_MISMATCH',
                  'context.threads(1)','d.final();return 0;'):
            self.assertIn(s,bench)

    def test_fresh_stage_and_isolated_source_import_bootstrap(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);stage=folder/'stage';manifest=gate.prepare(stage)
            with tarfile.open(stage/'source.tar.gz') as tar:
                members=tar.getmembers()
                self.assertEqual(len(members),len(manifest['sources']))
                for member in members:
                    self.assertTrue(member.isfile());self.assertTrue(member.name.startswith('fpga/'))
                    self.assertNotIn('..',Path(member.name).parts)
                    self.assertEqual(hashlib.sha256(tar.extractfile(member).read()).hexdigest(),manifest['sources'][member.name[5:]])
                tar.extractall(folder/'snapshot',filter='data')
            script="import importlib.util,pathlib; p=pathlib.Path(__import__('sys').argv[1]); s=importlib.util.spec_from_file_location('gate',p/'reference/stream27_commutator_sync_regression.py'); m=importlib.util.module_from_spec(s);s.loader.exec_module(m);v=m.load_project(p,m.source_pins(p));assert v.corpus(1)[1]['sha256']==m.VECTOR_SHA[1]"
            result=subprocess.run([sys.executable,'-I','-S','-B','-c',script,str((folder/'snapshot/fpga').resolve())],text=True,capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
