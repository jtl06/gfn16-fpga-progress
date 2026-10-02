"""Load root phases once; verify repeated cached squares on aethia only."""
from __future__ import annotations
import argparse
import json
import random
import re
import socket
import subprocess
from pathlib import Path
from .ntt_parallel_regression import ParallelLab
from .ntt_difdit_regression import bitreverse
from .engine_regression import dif
from .rns_reference import GENEFER_SIGNED_PRIMES, RADIX, centered_crt


def encode(a: list[int], b: int) -> int:
    if len(a)==1:return a[0]
    h=len(a)//2;return encode(a[:h],b)+pow(b,h)*encode(a[h:],b)


def digits_of(x: int,b: int,n: int) -> list[int]:
    if n==1:return [x]
    h=n//2;hi,lo=divmod(x,pow(b,h));return digits_of(lo,b,h)+digits_of(hi,b,h)


def square_digits(a: list[int],b: int) -> list[int]:
    m=pow(b,len(a))+1;x=pow(encode(a,b),2,m)
    return [-1]+[0]*(len(a)-1) if x==m-1 else digits_of(x,b,len(a))


def cases_for(aw: int) -> list[tuple[str,list[int],int]]:
    n=1<<aw;rng=random.Random(0xcac4e+aw);cases=[]
    if aw<16:
        cases += [('zero',[0]*n,1024),('minus-one',[-1]+[0]*(n-1),1024),('max',[1023]*n,1024)]
    cases.append(('base2',[rng.randrange(2) for _ in range(n)],2))
    a=[rng.randrange(604832956) for _ in range(n)]
    for j in range(3 if aw<16 else 2):
        cases.append((f'recurrent{j}',a,604832956));a=square_digits(a,604832956)
    return cases


class CachedLab(ParallelLab):
    def build_ntt(self, field: int, aw: int=16, lanes: int=4) -> str:
        prime=GENEFER_SIGNED_PRIMES[field]
        exe=self.build(f'build-cached-p{field+1}-aw{aw}-l{lanes}','genefer_ntt_parallel_cached_engine',
            [self.root/'rtl/kernel'/n for n in ('genefer_montgomery_mul32_pipe.sv','genefer_ntt_difdit_engine.sv','genefer_ntt_parallel_cached_engine.sv')],
            self.root/'rtl/tb/ntt_parallel_cached_engine.cpp',
            [f'-GAW={aw}',f'-GLANES={lanes}',f'-GP={prime.p}',f'-GQ={prime.q}','-CFLAGS',f'-DNTT_LANES={lanes}'])
        if aw==16:
            # This verifies elaborated logical array shape, not vendor M20K mapping.
            header=(Path(exe).parent/'Vgenefer_ntt_parallel_cached_engine___024root.h').read_text()
            root_lines=[line for line in header.splitlines() if 'root_mem' in line]
            expected_depth=3*(1<<aw)//(2*lanes)
            if len(root_lines)!=2*lanes or not all(re.search(rf'\b{expected_depth}\b',line) for line in root_lines):
                raise RuntimeError('unexpected elaborated root-memory shape: '+'\n'.join(root_lines))
            self.report.setdefault('root_array_shape',[]).append({'field':field,'banks':2*lanes,
                'words_per_bank':expected_depth,'total_words':3*(1<<aw),'verified':True})
        return exe

    def cached_squares(self,field: int,aw: int,exe: str,cases) -> list[list[int]]:
        prime=GENEFER_SIGNED_PRIMES[field];p=prime.p;n=1<<aw;r=RADIX%p
        psi=pow(prime.generator,(p-1)//(2*n),p);omega=psi*psi%p;inv_n=pow(n,-1,p)
        def powers(w):
            a=[];v=1
            for _ in range(n):a.append(v);v=v*w%p
            return a
        twist=powers(psi);forward=powers(omega);inverse=powers(pow(omega,-1,p));untwist=powers(pow(psi,-1,p))
        tables=[[v*r%p for v in twist],[v*r%p for v in forward],
                [v*r%p for v in inverse],[v*inv_n%p for v in untwist]]
        lines=[str(aw)]
        def emit(cmd,a):lines.append(cmd+'\n'+' '.join(map(str,a)))
        def check(a,mont=True):emit('CHECK',[v*r%p for v in a] if mont else a)
        # Existing generator emits N words for every phase. Upper halves for
        # phases1/2 must be ignored; poison them again after all phases exist.
        for phase,table in enumerate(tables):lines.append(f'PHASE {phase}');emit('ROOTS',table)
        lines+=['PHASE 1','POISON_HALF','PHASE 2','POISON_HALF']
        expected_planes=[]
        for name,digits,base in cases:
            a=[v%p for v in digits];emit('LOAD',[v*r%p for v in a])
            lines+=['PHASE 0','RUN 2 0 0'];a=[v*w%p for v,w in zip(a,twist)];check(a)
            lines+=['PHASE 1','ORDER 1','RUN 0 0 0'];a=bitreverse(dif(a,p,prime.generator));check(a)
            lines.append('RUN 1 0 0');a=[v*v%p for v in a];check(a)
            lines+=['PHASE 2','ORDER 0','RUN 0 0 0'];a=[v*n%p for v in dif(bitreverse(a),p,prime.generator,True)];check(a)
            lines+=['PHASE 3','RUN 2 0 0'];a=[v*w*inv_n%p for v,w in zip(a,untwist)];check(a,False)
            lines.append('DUMP');expected_planes.append(a)
        name=f'cached-squares-p{field+1}-aw{aw}';path=self.output/f'{name}.txt';path.write_text('\n'.join(lines)+'\n')
        output=self.output/f'{name}-residues.txt';self.run(name,[exe,str(path),str(output)])
        words=list(map(int,output.read_text().split()))
        planes=[words[i*n:(i+1)*n] for i in range(len(cases))]
        if len(words)!=n*len(cases) or planes!=expected_planes:raise RuntimeError('cached square dump mismatch')
        return planes

    def reject_mutants(self) -> None:
        cases=[
            ('upper-write-alias',' && !half_write_illegal',''),
            ('phase-capture','active_root_base+RRW\'(address_w[lane]>>KW)',
             'host_root_base+RRW\'(address_w[lane]>>KW)'),
            ('phase-overlap',"2: phase_base=RRW'(DEPTH+HALF_DEPTH);","2: phase_base=RRW'(DEPTH);"),
        ]
        for name,old,new in cases:
            directory=self.output/f'mutation-{name}';directory.mkdir(exist_ok=True)
            text=(self.root/'rtl/kernel/genefer_ntt_parallel_cached_engine.sv').read_text()
            if old not in text:raise RuntimeError('missing cache mutation anchor')
            path=directory/'genefer_ntt_parallel_cached_engine.sv';path.write_text(text.replace(old,new))
            exe=self.build(f'build-mutation-{name}','genefer_ntt_parallel_cached_engine',
                [self.root/'rtl/kernel/genefer_montgomery_mul32_pipe.sv',self.root/'rtl/kernel/genefer_ntt_difdit_engine.sv',path],
                self.root/'rtl/tb/ntt_parallel_cached_engine.cpp',['-GAW=4'])
            proc=subprocess.run([exe,str(self.output/'cached-squares-p1-aw4.txt'),str(directory/'dump.txt')],
                cwd=self.root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
            (self.output/f'reject-mutation-{name}.log').write_text(proc.stdout)
            passed=proc.returncode!=0 and 'NTT mismatch' in proc.stdout
            self.report['steps'].append({'name':f'reject-mutation-{name}','passed':passed,'returncode':proc.returncode})
            print(f"reject-mutation-{name}: {'PASS' if passed else 'FAIL'}",flush=True)
            if not passed:raise RuntimeError(proc.stdout[-2000:])


def main() -> None:
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--quick',action='store_true');args=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('Run simulation on aethia only')
    lab=CachedLab(args.output,'verilator')
    try:
        for aw in ((4,) if args.quick else (1,4,16)):
            cases=cases_for(aw);all_planes=[]
            for field in range(1 if args.quick else 3):
                exe=lab.build_ntt(field,aw);all_planes.append(lab.cached_squares(field,aw,exe,cases))
                # Root phase0 alone also retains general transform semantics.
                lab.transform_test(field,aw,exe,f'-cached-aw{aw}')
                if aw>=5:lab.resets(field,exe)
            if not args.quick:
                for i,(name,digits,base) in enumerate(cases):
                    coeff=[centered_crt((all_planes[f][i][j] for f in range(3)),GENEFER_SIGNED_PRIMES) for j in range(1<<aw)]
                    m=pow(base,1<<aw)+1
                    if encode(coeff,base)%m!=pow(encode(digits,base),2,m):raise RuntimeError('cached whole-integer square mismatch')
                    if aw<=4:
                        school=[0]*(1<<aw)
                        for j,a in enumerate(digits):
                            for k,b in enumerate(digits):school[(j+k)%len(digits)]+=a*b if j+k<len(digits) else -a*b
                        if coeff!=school:raise RuntimeError('cached schoolbook mismatch')
                    lab.report.setdefault('cached_integer_squares',[]).append({'aw':aw,'name':name,'base':base,'passed':True})
        if not args.quick:lab.reject_mutants()
        lab.report['status']='passed'
    except Exception:
        lab.report['status']='failed';raise
    finally:(lab.output/'report.json').write_text(json.dumps(lab.report,indent=2)+'\n')


if __name__=='__main__':main()
