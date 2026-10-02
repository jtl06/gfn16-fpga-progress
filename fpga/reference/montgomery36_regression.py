"""Isolated six-stage36-bit Montgomery RTL validation; aethia only."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import resource
import socket
import subprocess
import time
from .ntt36_experiment import RADIX,select_basis,validate

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--quick',action='store_true');args=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30))
    root=Path(__file__).resolve().parents[1];out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    rtl=root/'rtl/kernel/genefer_montgomery_mul36_sparse_pipe.sv';cpp=root/'rtl/tb/montgomery36_pipe.cpp'
    report=dict(status='running',host=socket.gethostname(),radix_bits=36,stages=6,initiation_interval=1,
                memory_limit_bytes=6<<30,math=validate(),steps=[],branches={},sources={})
    for path in (rtl,cpp,Path(__file__),root/'reference/ntt36_experiment.py'):
        report['sources'][str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
    def run(name,command,rejection=None):
        then=time.monotonic();proc=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
        (out/f'{name}.log').write_text(proc.stdout)
        passed=proc.returncode==0 if rejection is None else proc.returncode!=0 and any(x in proc.stdout for x in rejection)
        report['steps'].append(dict(name=name,passed=passed,returncode=proc.returncode,seconds=time.monotonic()-then,command=command))
        print(f"{name}: {'PASS' if passed else 'FAIL'} {proc.stdout[-220:]}",flush=True)
        if not passed:raise RuntimeError(proc.stdout[-2000:])
    def build(name,p,q,source=rtl):
        directory=out/f'build-{name}'
        run(f'build-{name}',['verilator','--cc','--exe','--build','-j','2','--top-module','genefer_montgomery_mul36_sparse_pipe',
            '--Mdir',str(directory),f"-GP=36'd{p}",f"-GQ=36'd{q}",str(source),str(cpp)])
        return str(directory/'Vgenefer_montgomery_mul36_sparse_pipe')
    try:
        for field in select_basis()[:1 if args.quick else 3]:
            p,q=field['p'],field['q'];rng=random.Random(0x36cafe+p);rows=[];branches=[0,0]
            inverse=pow(RADIX,-1,p)
            def emit(reset,valid,x,y):
                # Oracle uses ordinary Python big integers and modular inverse,
                # independently of the RTL sparse reduction identity.
                value=x*y*inverse%p
                if reset and valid:
                    assert 0<=x<p and 0<=y<p
                    t=x*y;m=t*q%RADIX;branches[int(t//RADIX<(m*p)//RADIX)]+=1
                rows.append(f'{reset} {valid} {x} {y} {value}\n')
            emit(0,1,RADIX-1,RADIX-1)
            edges=sorted({0,1,2,p//2-1,p//2,p//2+1,p-3,p-2,p-1,RADIX%p,
                          *[x for bit in (17,18,26,27,32,34,35) for x in ((1<<bit)-1,1<<bit,(1<<bit)+1) if x<p]})
            for x in edges:
                for y in edges:emit(1,1,x,y)
            for j in range(5000 if args.quick else 40000):
                reset=j%251!=250;valid=j%7!=6
                x,y=(rng.randrange(p),rng.randrange(p)) if reset and valid else (rng.randrange(RADIX),rng.randrange(RADIX))
                emit(int(reset),int(valid),x,y)
            for depth in range(1,7):
                for j in range(depth):emit(1,1,p-1-j,p-2-j)
                emit(0,1,RADIX-1,RADIX-1)
                for _ in range(12):emit(1,1,rng.randrange(p),rng.randrange(p))
            for _ in range(12):emit(1,0,RADIX-1,RADIX-1)
            assert min(branches)>0;report['branches'][str(p)]=branches
            vectors=out/f'vectors-{p}.txt';vectors.write_text(''.join(rows))
            report['sources'][str(vectors)]=hashlib.sha256(vectors.read_bytes()).hexdigest()
            exe=build(str(p),p,q);run(f'test-{p}',[exe,str(vectors),str(p)])
            for name,x,y in (('lhs-P',p,1),('rhs-P',1,p),('max-lhs',RADIX-1,1),('max-rhs',1,RADIX-1)):
                run(f'reject-{name}-{p}',[exe,'reject',str(p),str(x),str(y)],['noncanonical Montgomery36 input'])
            if not args.quick:
                mutants=[
                    ('variable-high','ab_s1<=lhs*rhs;',"ab_s1<={1'b0,lhs[34:0]}*rhs;"),
                    ('q-shift','m_head_s2<=lo-(lo<<35);','m_head_s2<=lo;'),
                    ('p-shift','sum_low_s4<=m_ext+(m_ext<<S);','sum_low_s4<=m_ext;'),
                    ('wide-m',"{36'b0,m_s3}","{37'b0,m_s3[34:0]}"),
                    ('negative','else result<=corrected[35:0];','else result<=hi_s5-mp_hi_s5;'),
                    ('equality','hi_s5>=mp_hi_s5','hi_s5>mp_hi_s5'),
                    ('latency','out_valid<=valid_pipe[4]','out_valid<=valid_pipe[3]'),
                    ('reset',"valid_pipe<='0","valid_pipe<='1"),
                    ('hold','if(valid_pipe[4])begin',"if(!valid_pipe[4])result<=36'd123;\n            if(valid_pipe[4])begin"),
                ]
                if len(field['shifts'])==3:mutants.append(('extra-q','m_tail_s2<=(lo<<S)+extra_q;','m_tail_s2<=(lo<<S);'))
                for name,old,new in mutants:
                    source=rtl.read_text()
                    if source.count(old)!=1:raise RuntimeError('bad mutation anchor '+name)
                    path=out/f'mutant-{name}-{p}.sv';path.write_text(source.replace(old,new))
                    exe=build(f'{name}-{p}',p,q,path)
                    run(f'reject-mutant-{name}-{p}',[exe,str(vectors),str(p)],['Montgomery arithmetic mismatch','valid/latency mismatch','invalid-cycle result hold mismatch'])
                old='$fatal(1,"noncanonical Montgomery36 input");';path=out/f'mutant-domain-{p}.sv'
                path.write_text(rtl.read_text().replace(old,';'));exe=build(f'domain-{p}',p,q,path)
                run(f'reject-mutant-domain-{p}',[exe,'reject',str(p)],['invalid input assertion missing'])
        if not args.quick:
            for name,p,q,message in (('modulus',3,1,'unsupported sparse Montgomery36 modulus'),
                                    ('inverse',select_basis()[0]['p'],select_basis()[0]['q']^2,'invalid sparse Montgomery36 inverse')):
                exe=build(name,p,q);run('reject-'+name,[exe,'reject',str(p)],[message])
        report['status']='passed'
    except BaseException as error:
        report.update(status='failed',error=repr(error));raise
    finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
