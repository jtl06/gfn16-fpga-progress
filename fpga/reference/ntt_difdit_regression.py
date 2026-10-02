"""Independent DIF/DIT ordering and negacyclic-square checks; aethia only."""
from __future__ import annotations
import argparse
import json
import random
import socket
import subprocess
from pathlib import Path
from .ntt_stream_regression import StreamLab
from .engine_regression import dif
from .rns_reference import GENEFER_SIGNED_PRIMES, RADIX, naive_ntt, centered_crt


def bitreverse(a: list[int]) -> list[int]:
    lg=len(a).bit_length()-1
    return [a[int(f"{i:0{lg}b}"[::-1],2)] for i in range(len(a))]


class DIFDITLab(StreamLab):
    def build_ntt(self, field: int, aw: int=16) -> str:
        prime=GENEFER_SIGNED_PRIMES[field]
        return self.build(f"build-difdit-p{field+1}-aw{aw}","genefer_ntt_difdit_engine",
            [self.root/"rtl/kernel"/n for n in ("genefer_montgomery_mul32_pipe.sv","genefer_ntt_difdit_engine.sv")],
            self.root/"rtl/tb/ntt_difdit_engine.cpp",[f"-GAW={aw}",f"-GP={prime.p}",f"-GQ={prime.q}"])

    def transform_test(self, field: int, lg: int, exe: str, suffix: str="") -> None:
        prime=GENEFER_SIGNED_PRIMES[field];p=prime.p;n=1<<lg;r=RADIX%p
        root=pow(prime.generator,(p-1)//n,p);invroot=pow(root,-1,p)
        rng=random.Random(0xd1fd17+field*100+lg)
        patterns=[[0]*n,[1]+[0]*(n-1),[p-1]*n,[rng.randrange(p) for _ in range(n)]] if lg<=5 else [[rng.randrange(p) for _ in range(n)]]
        lines=[str(lg)]
        def emit(cmd: str,a: list[int]) -> None:lines.append(cmd+"\n"+" ".join(map(str,a)))
        def mont(a: list[int]) -> list[int]:return [v*r%p for v in a]
        fwdroots=[pow(root,i,p)*r%p for i in range(n)]
        invroots=[pow(invroot,i,p)*r%p for i in range(n)]
        for values in patterns:
            forward=dif(values,p,prime.generator)
            if lg<=5 and forward!=naive_ntt(values,prime):raise RuntimeError("DIF oracle mismatch")
            emit("LOAD",mont(values));emit("ROOTS",fwdroots)
            lines+=['ORDER 1','RUN 0 0 0'];emit("CHECK",mont(bitreverse(forward)))
            emit("ROOTS",invroots);lines+=['ORDER 0',f'RUN 0 1 {pow(n,-1,p)*r%p}'];emit("CHECK",mont(values))
            # Check each direction/order independently, not only round-tripping.
            emit("LOAD",mont(bitreverse(values)));emit("ROOTS",fwdroots)
            lines+=['ORDER 0','RUN 0 0 0'];emit("CHECK",mont(forward))
            emit("ROOTS",invroots);lines+=['ORDER 1',f'RUN 0 1 {pow(n,-1,p)*r%p}'];emit("CHECK",mont(bitreverse(values)))
        name=f"difdit-p{field+1}-n{n}{suffix}";path=self.output/f"{name}.txt"
        path.write_text("\n".join(lines)+"\n")
        self.run(name,[exe,str(path),str(self.output/f"{name}-dump.txt")])

    def reset_and_pointwise(self, field: int, exe: str) -> None:
        prime=GENEFER_SIGNED_PRIMES[field];p=prime.p;r=RADIX%p;n=32;lg=5
        rng=random.Random(723+field);values=[rng.randrange(p) for _ in range(n)]
        root=pow(prime.generator,(p-1)//n,p);roots=[pow(root,i,p)*r%p for i in range(n)]
        lines=[str(lg)]
        def emit(cmd: str,a: list[int]) -> None:lines.append(cmd+"\n"+" ".join(map(str,a)))
        for mode in (0,1):
            lines.append(f"ORDER {mode}")
            for op,when in ((0,1),(0,5),(0,8),(0,24),(0,114),(1,1),(1,5),(1,33),(2,6),(3,34)):
                emit("LOAD",[v*r%p for v in values]);emit("ROOTS",roots)
                lines.append(f"ABORT_AT {op} 0 {r} {when}")
            for op in (1,2,3):
                emit("LOAD",[v*r%p for v in values]);emit("ROOTS",roots)
                lines.append(f"RUN {op} 0 {r if op!=3 else 1}")
                if op==1:expected=[v*v*r%p for v in values]
                elif op==2:expected=[v*pow(root,i,p)*r%p for i,v in enumerate(values)]
                else:expected=values
                emit("CHECK",expected)
        name=f"reset-difdit-p{field+1}";path=self.output/f"{name}.txt"
        path.write_text("\n".join(lines)+"\n")
        self.run(name,[exe,str(path),str(self.output/f"{name}-dump.txt")])

    def square_field(self, field: int, digits: list[int], exe: str, name: str, fused: bool=True) -> list[int]:
        prime=GENEFER_SIGNED_PRIMES[field];p=prime.p;n=len(digits);r=RADIX%p
        psi=pow(prime.generator,(p-1)//(2*n),p);root=psi*psi%p
        lines=[str(n.bit_length()-1)]
        def emit(cmd: str,a: list[int]) -> None:lines.append(cmd+"\n"+" ".join(map(str,a)))
        def powers(root: int) -> list[int]:
            a=[];w=1
            for _ in range(n):a.append(w);w=w*root%p
            return a
        def roots(a: list[int]) -> None:emit("ROOTS",[v*r%p for v in a])
        def check(a: list[int],mont: bool=True) -> None:emit("CHECK",[v*r%p for v in a] if mont else a)
        a=[v%p for v in digits];emit("LOAD",[v*r%p for v in a])
        twist=powers(psi);roots(twist);lines.append("RUN 2 0 0")
        a=[v*w%p for v,w in zip(a,twist)];check(a)
        roots(powers(root));lines+=['ORDER 1','RUN 0 0 0']
        a=bitreverse(dif(a,p,prime.generator));check(a)
        lines.append('RUN 1 0 0');a=[v*v%p for v in a];check(a)
        untwist=powers(pow(psi,-1,p));roots(powers(pow(root,-1,p)));lines.append('ORDER 0')
        a=dif(bitreverse(a),p,prime.generator,True)
        if fused:
            lines.append('RUN 0 0 0');a=[v*n%p for v in a];check(a)
            inv_n=pow(n,-1,p);emit('ROOTS',[w*inv_n%p for w in untwist])
            lines.append('RUN 2 0 0');a=[v*w*inv_n%p for v,w in zip(a,untwist)];check(a,False)
        else:
            lines.append(f'RUN 0 1 {pow(n,-1,p)*r%p}');check(a)
            roots(untwist);lines.append('RUN 2 0 0');a=[v*w%p for v,w in zip(a,untwist)];check(a)
            lines.append('RUN 3 0 1');check(a,False)
        lines.append('DUMP');path=self.output/f'{name}-p{field+1}.txt'
        path.write_text('\n'.join(lines)+'\n');output=self.output/f'{name}-p{field+1}-residues.txt'
        self.run(f'{name}-p{field+1}',[exe,str(path),str(output)])
        got=list(map(int,output.read_text().split()))
        if got!=a:raise RuntimeError('residue dump mismatch')
        return got

    def reject_mutants(self) -> None:
        cases=[
            ('twiddle-direction','root_step<=active_dif ? root_step<<1 : root_step>>1;',
             'root_step<=active_dif ? root_step>>1 : root_step>>1;'),
            ('write-tag','tag_a[6]','tag_a[5]'),
            ('prefix-alignment','prefix_pipe[4]','prefix_pipe[3]'),
            ('dif-subtract','pre_v<=dif ? (u>=v ? u-v : u+P-v) : v;',
             'pre_v<=dif ? (u>=v ? u-v : u+P-v) ^ 1 : v;'),
        ]
        for name,old,new in cases:
            directory=self.output/f'mutation-{name}';directory.mkdir(exist_ok=True)
            text=(self.root/'rtl/kernel/genefer_ntt_difdit_engine.sv').read_text()
            if old not in text:raise RuntimeError('missing mutant anchor')
            path=directory/'genefer_ntt_difdit_engine.sv';path.write_text(text.replace(old,new))
            exe=self.build(f'build-mutation-{name}','genefer_ntt_difdit_engine',
                [self.root/'rtl/kernel/genefer_montgomery_mul32_pipe.sv',path],
                self.root/'rtl/tb/ntt_difdit_engine.cpp')
            proc=subprocess.run([exe,str(self.output/'difdit-p1-n32.txt'),str(directory/'dump.txt')],
                                cwd=self.root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
            (self.output/f'reject-mutation-{name}.log').write_text(proc.stdout)
            passed=proc.returncode!=0 and ('NTT mismatch' in proc.stdout or 'mixed-port collision' in proc.stdout)
            self.report['steps'].append({'name':f'reject-mutation-{name}','passed':passed,'returncode':proc.returncode})
            print(f"reject-mutation-{name}: {'PASS' if passed else 'FAIL'}",flush=True)
            if not passed:raise RuntimeError(proc.stdout[-2000:])


def main() -> None:
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--quick',action='store_true');args=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('Run simulation on aethia only')
    lab=DIFDITLab(args.output,'verilator')
    try:
        executables=[];corner_planes={1:[],4:[]}
        for field in range(1 if args.quick else 3):
            exe=lab.build_ntt(field);executables.append(exe)
            for lg in ((1,4,5) if args.quick else range(1,17)):lab.transform_test(field,lg,exe)
            lab.reset_and_pointwise(field,exe)
            if not args.quick:
                for aw in (1,4):
                    small=lab.build_ntt(field,aw)
                    lab.transform_test(field,aw,small,f'-aw{aw}')
                    digits=[(i*7919+3)%1024 for i in range(1<<aw)]
                    corner_planes[aw].append(lab.square_field(field,digits,small,f'difdit-square-aw{aw}'))
        if not args.quick:
            for aw,planes in corner_planes.items():
                n=1<<aw;digits=[(i*7919+3)%1024 for i in range(n)];expected=[0]*n
                for i,a in enumerate(digits):
                    for j,b in enumerate(digits):expected[(i+j)%n]+=a*b if i+j<n else -a*b
                got=[centered_crt((plane[i] for plane in planes),GENEFER_SIGNED_PRIMES) for i in range(n)]
                if got!=expected:raise RuntimeError('parameter-corner convolution mismatch')
                lab.report.setdefault('corner_convolutions',[]).append({'aw':aw,'passed':True})
            lab.square_checks(executables)
            lab.reject_mutants()
        lab.report['status']='passed'
    except Exception:
        lab.report['status']='failed';raise
    finally:(lab.output/'report.json').write_text(json.dumps(lab.report,indent=2)+'\n')


if __name__=='__main__':main()
