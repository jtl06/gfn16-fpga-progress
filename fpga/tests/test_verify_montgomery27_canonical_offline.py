"""Independent vector/receipt fixtures; no simulator or generator imports."""
import copy
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from reference import verify_montgomery27_canonical_offline as v

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'results/throughput-20260929/mont27-canonical-stage-v2'


def vector_fixture(p):
    """Deterministic arithmetic samples, not the runner's PRNG sequence."""
    R=1<<32;inv=pow(R,-1,p);rows=[]
    def emit(reset,valid,a,b):rows.append(f'{reset} {valid} {a} {b} {a*b*inv%p}\n')
    def fill():emit(1,1,p-17,p-29)
    emit(0,1,R-1,R-1)
    edges=sorted({0,1,2,p//2-1,p//2,p//2+1,p-3,p-2,p-1,(1<<26)-1,1<<26,(1<<26)+1,R%p})
    for a in edges:
        for b in edges:emit(1,1,a,b)
    for i in range(30000):emit(int(i%251!=250),int(i%7!=6),(i*7919+17)%p,(i*65537+29)%p)
    for age in range(4):
        emit(0,0,R-1,R-1);emit(1,1,p-1,p-1)
        for _ in range(age):emit(1,0,R-1,R-1)
        emit(0,1,R-1,R-1)
        for _ in range(5):emit(1,0,R-1,R-1)
        for _ in range(8):fill()
    for depth in range(1,5):
        for j in range(depth):emit(1,1,p-1-j,p-2-j)
        emit(0,1,R-1,R-1)
        for _ in range(8):fill()
    for _ in range(8):emit(1,0,R-1,R-1)
    return ''.join(rows)


def make_tar(path,members):
    with tarfile.open(path,'w:gz') as tar:
        for name,payload in members.items():
            m=tarfile.TarInfo(name);m.size=len(payload);tar.addfile(m,io.BytesIO(payload))


def fixture(root):
    """Synthetic full receipt tests plumbing, not actual compiler execution."""
    (root/'approved-manifest.json').write_bytes((STAGE/'manifest.json').read_bytes())
    with tarfile.open(STAGE/'sources.tar.gz') as t:
        sources={name:t.extractfile('fpga/'+name).read() for name in v.PINS}
    make_tar(root/'sources.tar.gz',sources)
    scratch='/dev/shm/gfn16-mont27-canonical-fixture';remote=str(Path(v.SOURCE).parent.parent/'gate-fixture')
    report=dict(status='passed_standalone_helper',sources=v.PINS,manifest_sha256=v.MANIFEST_SHA,
                fields=[list(f) for f in v.FIELDS],stages=4,initiation_interval=1,compile_workers=2,model_threads=1,radix_bits=32,
                limits=dict(affinity=[0,2],memory_max_bytes=6<<30,cpu_max=['200000','100000'],physical_cores=[[0,0],[0,1]]),
                scratch=scratch,compiler_temporary_directory=scratch+'/tmp',
                durable_reservation_bytes=32<<20,durable_free_floor_bytes=10<<30,scratch_reservation_bytes=512<<20,
                scratch_free_floor_bytes=2<<30,host_memory_floor_bytes=4<<30,command_timeout_seconds=300,lock_wait_timeout_seconds=900,
                tool_executable_sha256={'/tool/python':'0'*64,'/tool/g++':'1'*64,'/tool/verilator':'2'*64},python_version='synthetic',
                steps=[],builds=[],vectors={})
    def step(name,argv,text,rc=0,assertion=None):
        path=root/(name+'.log');path.write_text(text)
        report['steps'].append(dict(name=name,command=argv,returncode=rc,error=None,seconds=0.01,
                                   log=path.name,sha256=v.sha(path),expected_assertion=assertion))
    for tool in ('verilator','g++'):
        log=tool+' synthetic\n';report[tool+'_version']=log;step(tool+'-version',[tool,'--version'],log)
    specs=[(f'p{i+1}',p,q) for i,(p,q) in enumerate(v.FIELDS)]+[
        ('unsupported-modulus',3,4294967295),('invalid-inverse',v.FIELDS[0][0],v.FIELDS[0][1]^2)]
    rtl=sources['rtl/kernel/'+v.TOP+'.sv'].decode()
    def rejection(name,argv,message):
        line=next(i+1 for i,s in enumerate(rtl.splitlines()) if '$fatal(1,"'+message+'");' in s)
        text=f'[0] %Fatal: {v.TOP}.sv:{line}: Assertion failed in TOP.{v.TOP}: {message}\n'
        text+=f'%Error: {v.SOURCE}/rtl/kernel/{v.TOP}.sv:{line}: Verilog $stop\nAborting...\n'
        step(name,argv,text,-6,message)
    for name,p,q in specs:
        exe='V'+v.TOP+'-'+name;(root/exe).write_bytes(('synthetic '+name).encode())
        generated={'V'+v.TOP+'.cpp':('unsigned V'+v.TOP+'::threads() const { return 1; }').encode(),
                   'V'+v.TOP+'.h':b'//fixture header','V'+v.TOP+'.mk':b'//fixture makefile'}
        make_tar(root/(name+'-generated.tar.gz'),generated)
        report['builds'].append(dict(name=name,p=p,q=q,executable=exe,sha256=v.sha(root/exe),
                                    generated_sources={k:v.digest(x) for k,x in generated.items()}))
        argv=['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',v.TOP,
              '--Mdir',scratch+'/'+name,f'-GP={p}',f'-GQ={q}',v.SOURCE+'/rtl/kernel/'+v.TOP+'.sv',v.SOURCE+'/rtl/tb/montgomery27_canonical_pipe.cpp']
        step('build-'+name,argv,'synthetic build\n')
        if name.startswith('p'):
            path=root/('vectors-'+name+'.txt');path.write_text(vector_fixture(p));summary=v.vector_audit(path.read_text(),p,q)
            report['vectors'][str(p)]={**summary,'sha256':v.sha(path)}
            step('probe-'+name,[remote+'/'+exe,'--runtime-probe'],json.dumps(dict(context_threads=1,model_threads=1,expected_threads=1)))
            footer='PASS P={p} checked={checked} canceled={canceled} hold_checks={hold_checks} cycles={cycles}\n'.format(**summary)
            step('normal-'+name,[remote+'/'+exe,remote+'/'+path.name,str(p)],footer)
            for label,a,b in (('lhs-P',p,1),('rhs-P',1,p),('wide-lhs',1<<27,1),('wide-rhs',1,0xffffffff)):
                rejection('reject-'+name+'-'+label,[remote+'/'+exe,'reject',str(p),str(a),str(b)],'noncanonical Montgomery27 input')
        else:
            rejection('reject-'+name,[remote+'/'+exe,'reject',str(p)],
                      'unsupported sparse Montgomery27 modulus' if name=='unsupported-modulus' else 'invalid sparse Montgomery inverse')
    report['artifacts']={p.name:v.sha(p) for p in root.iterdir()}
    (root/'report.json').write_text(json.dumps(report));return report


class VectorAndDiagnosticTests(unittest.TestCase):
    def test_independent_three_field_vectors(self):
        for p,q in v.FIELDS:
            s=v.vector_audit(vector_fixture(p),p,q)
            self.assertEqual((s['checked'],s['canceled'],s['hold_checks'],s['cycles']),(25527,333,4767,30294))

    def test_corrupt_product_or_reset_semantics_rejected(self):
        p,q=v.FIELDS[0];rows=vector_fixture(p).splitlines()
        changed=rows[:];tokens=changed[1].split();tokens[-1]='1';changed[1]=' '.join(tokens)
        with self.assertRaisesRegex(ValueError,'integer vector oracle'):v.vector_audit('\n'.join(changed),p,q)
        changed=rows[:];tokens=changed[-1].split();tokens[1]='1';tokens[2:4]=['1','1'];tokens[-1]=str(pow(1<<32,-1,p));changed[-1]=' '.join(tokens)
        with self.assertRaises(ValueError):v.vector_audit('\n'.join(changed),p,q)
        with self.assertRaises(ValueError):v.vector_audit('\n'.join(rows[:-1]),p,q)

    def test_parameter_rejections_not_arithmetic_fields(self):
        with self.assertRaisesRegex(ValueError,'valid arithmetic field'):v.vector_audit('',3,4294967295)


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.report=fixture(self.root)
    def tearDown(self):self.temp.cleanup()
    def save(self):(self.root/'report.json').write_text(json.dumps(self.report))

    def test_complete_fixture_distinguishes_roles(self):
        result=v.verify(self.root)
        self.assertEqual((result['valid_arithmetic_fields'],result['normal_outputs'],result['input_assertion_rejections'],result['parameter_assertion_rejections']),
                         (3,76581,12,2))

    def test_failed_v1_cannot_be_promoted(self):
        self.report['status']='failed_or_incomplete';self.save()
        with self.assertRaisesRegex(ValueError,'incomplete helper gate'):v.verify(self.root)

    def test_drift_and_unapproved_source(self):
        (self.root/'vectors-p1.txt').write_text('corrupt')
        with self.assertRaisesRegex(ValueError,'artifact hash'):v.verify(self.root)
        self.report['sources']=dict(self.report['sources']);self.report['sources']['reference/montgomery27_canonical_regression.py']='f'*64;self.save()
        with self.assertRaisesRegex(ValueError,'five-source map'):v.verify(self.root)

    def test_thread_or_parameter_build_mismatch(self):
        step=next(s for s in self.report['steps'] if s['name']=='build-p1');step['command'][step['command'].index('--threads')+1]='8';self.save()
        with self.assertRaisesRegex(ValueError,'command argv'):v.verify(self.root)

    def test_wrong_assertion_trailer_rejected_even_rehashed(self):
        step=next(s for s in self.report['steps'] if s['name']=='reject-p1-lhs-P');path=self.root/step['log']
        path.write_text(path.read_text().replace('Verilog $stop','unrelated fatal'))
        step['sha256']=self.report['artifacts'][path.name]=v.sha(path);self.save()
        with self.assertRaisesRegex(ValueError,'stop trailer'):v.verify(self.root)

    def test_typed_assertions_and_nonfinite_duration(self):
        step=next(s for s in self.report['steps'] if s['name']=='reject-p1-lhs-P');step['returncode']=True;self.save()
        with self.assertRaisesRegex(ValueError,'assertion process status'):v.verify(self.root)
        step['returncode']=-6;step['seconds']=float('nan');self.save()
        with self.assertRaisesRegex(ValueError,'duration'):v.verify(self.root)

    def test_normal_footer_and_reported_vector_coverage(self):
        self.report['vectors'][str(v.FIELDS[0][0])]['canceled']+=1;self.save()
        with self.assertRaisesRegex(ValueError,'vector coverage metadata'):v.verify(self.root)

    def test_no_extra_command_or_artifact_role(self):
        self.report['steps'].append(dict(self.report['steps'][0]));self.save()
        with self.assertRaisesRegex(ValueError,'duplicate command'):v.verify(self.root)


if __name__=='__main__':unittest.main()
