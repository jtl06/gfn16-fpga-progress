"""Shared butterfly/pointwise multiplier validation; simulation on aethia only."""
from __future__ import annotations
import argparse
import json
import resource
import socket
import subprocess
from pathlib import Path
from .engine_regression import Lab,dif
from .ntt_difdit_regression import bitreverse
from .ntt27_experiment import select_basis,prove_basis
import random
from .ntt_banked_regression import schedule_check
from .ntt_cached_regression import cases_for,encode
from .rns_reference import RADIX,centered_crt,naive_ntt

assert RADIX == 1<<32, '27-bit operands do not change Montgomery radix'
EXPERIMENT_PRIMES=select_basis()


class NTT27Lab(Lab):
    def run(self,name,command,reject=None):
        if name.startswith(('difdit-','reset-ntt27-')):
            command=['env','NTT_SKIP_HOST_FUZZ=1',*command]
        return super().run(name,command,reject)

    def build_ntt(self,field: int,aw: int=16,lanes: int=64) -> str:
        prime=EXPERIMENT_PRIMES[field]
        return self.build(f'build-ntt27-p{field+1}-aw{aw}-l{lanes}','genefer_ntt_banked27_engine',
            [self.root/'rtl/kernel'/n for n in ('genefer_montgomery_mul27_sparse_pipe.sv','genefer_sdp_ram32.sv','genefer_ntt_banked27_engine.sv')],
            self.root/'rtl/tb/ntt_banked27_engine.cpp',
            [f'-GAW={aw}',f'-GLANES={lanes}',f'-GP={prime.p}',f'-GQ={prime.q}','-CFLAGS',f'-DNTT_LANES={lanes} -DNTT_AW={aw} -DNTT_P={prime.p}u'])

    def cached_squares(self,field: int,aw: int,exe: str,cases) -> list[list[int]]:
        prime=EXPERIMENT_PRIMES[field];p=prime.p;n=1<<aw;r=RADIX%p
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


    def transform_test(self, field: int, lg: int, exe: str, suffix: str="") -> None:
        prime=EXPERIMENT_PRIMES[field];p=prime.p;n=1<<lg;r=RADIX%p
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


    def resets(self,field: int,exe: str,lanes: int=4) -> None:
        # Exact ntt27 latency, including reset in the op0 inverse-normalization
        # transition and immediately before completion; reload after every reset.
        prime=EXPERIMENT_PRIMES[field];p=prime.p;r=(1<<32)%p;n=32
        root=pow(prime.generator,(p-1)//n,p);data=[(i*7919+17)%p for i in range(n)]
        lines=['5'];transform=5*((n+2*lanes-1)//(2*lanes)+8)
        point=(n+lanes-1)//lanes+7
        def emit(cmd,a):lines.append(cmd+'\n'+' '.join(map(str,a)))
        for mode in (0,1):
            lines.append(f'ORDER {mode}')
            for op,inv in ((0,0),(0,1),(1,0),(2,0),(3,0)):
                limit=(transform if op==0 else 0)+(point if op!=0 or inv else 0)
                times={1,2,3,7,limit-2,limit-1}
                if op==0 and inv:times.update((transform-1,transform,transform+1,transform+2))
                for when in sorted(t for t in times if 0<t<limit):
                    emit('LOAD',[v*r%p for v in data]);emit('ROOTS',[pow(root,i,p)*r%p for i in range(n)])
                    lines.append(f'ABORT_AT {op} {inv} {r} {when}')
            for op in (1,2,3):
                emit('LOAD',[v*r%p for v in data]);emit('ROOTS',[pow(root,i,p)*r%p for i in range(n)])
                lines.append(f'RUN {op} 0 {r if op!=3 else 1}')
                expected=[v*v*r%p for v in data] if op==1 else [v*pow(root,i,p)*r%p for i,v in enumerate(data)] if op==2 else data
                emit('CHECK',expected)
        name=f'reset-ntt27-p{field+1}-l{lanes}';path=self.output/f'{name}.txt';path.write_text('\n'.join(lines)+'\n')
        self.run(name,[exe,str(path),str(self.output/f'{name}-dump.txt')])

    def canonical_checks(self,field,aw,exe):
        for mode in ('data','root','vector'):
            command=['env',f'NTT_NONCANON={mode}',exe,str(self.output/f'cached-squares-p{field+1}-aw{aw}.txt'),str(self.output/f'noncanon-{field}-{mode}.txt')]
            proc=subprocess.run(command,cwd=self.root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
            passed=proc.returncode!=0 and 'noncanonical NTT27' in proc.stdout
            self.report['steps'].append({'name':f'noncanonical-p{field+1}-{mode}','passed':passed})
            if not passed:raise RuntimeError(proc.stdout)
            print(f'noncanonical-p{field+1}-{mode}: PASS',flush=True)

    def reject_mutants(self):
        cases=[
            ('reduction',True,'m_s2<=lo-(lo<<26)-(lo<<S)-extra_q;','m_s2<=lo-(lo<<26)-(lo<<S);'),
            ('correction',True,'else result<=hi_s3+P-mp_hi;','else result<=hi_s3-mp_hi;'),
            ('root-shift',False,'root_shift<=setup_root_shift;','root_shift<=setup_root_shift+1;'),
            ('post-mont',False,'assign product[lane]=bf0[lane];','assign product[lane]=bf1[lane];'),
        ]
        for name,helper,old,new in cases:
            directory=self.output/f'mutation-{name}';directory.mkdir(exist_ok=True)
            helper_path=self.root/'rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv'
            engine_path=self.root/'rtl/kernel/genefer_ntt_banked27_engine.sv'
            original=helper_path if helper else engine_path
            source=original.read_text()
            if old not in source:raise RuntimeError('missing27 mutation anchor')
            path=directory/original.name;path.write_text(source.replace(old,new))
            exe=self.build(f'build-mutation-{name}','genefer_ntt_banked27_engine',
                [path if helper else helper_path,self.root/'rtl/kernel/genefer_sdp_ram32.sv',engine_path if helper else path],
                self.root/'rtl/tb/ntt_banked27_engine.cpp',
                ['-GAW=4','-GLANES=16','-CFLAGS','-DNTT_AW=4 -DNTT_LANES=16 -DNTT_P=104857601u'])
            proc=subprocess.run([exe,str(self.output/'cached-squares-p1-aw4.txt'),str(directory/'dump.txt')],
                cwd=self.root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
            passed=proc.returncode!=0 and any(s in proc.stdout for s in ('mismatch','collision','noncanonical','timeout'))
            self.report['steps'].append({'name':f'reject-mutation-{name}','passed':passed,'returncode':proc.returncode})
            (self.output/f'reject-mutation-{name}.log').write_text(proc.stdout)
            if not passed:raise RuntimeError(proc.stdout)
            print(f'reject-mutation-{name}: PASS',flush=True)


def main() -> None:
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--quick',action='store_true');args=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('Run simulation on aethia only')
    resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30));args.output.mkdir(parents=True,exist_ok=True);reports=[]
    for lanes in ((16,) if args.quick else (16,64)):
        lab=NTT27Lab(args.output/f'lanes{lanes}','verilator');lab.report['memory_limit_bytes']=6<<30
        lab.report['radix_bits']=32;lab.report['basis']=prove_basis(EXPERIMENT_PRIMES)
        lab.report['host_fuzz_policy']='Full physical host fuzz for every cached-square build; arithmetic sweeps omit only its duplicate prelude.'
        try:
            for lg in ((1,4,6,7,8) if args.quick else range(1,17)):schedule_check(lg,lanes)
            lab.report['schedule_proof']={'passed':True,'lanes':lanes,'max_lg':8 if args.quick else 16}
            for aw in ((4,) if args.quick else (1,4,16)):
                cases=cases_for(aw);planes=[]
                if aw==16:cases.append(('max-base1e9',[999999999]*(1<<aw),1000000000))
                for field in range(1 if args.quick else 3):
                    exe=lab.build_ntt(field,aw,lanes);planes.append(lab.cached_squares(field,aw,exe,cases))
                    if aw==4:lab.canonical_checks(field,aw,exe)
                    if aw==16:
                        for lg in range(1,17):lab.transform_test(field,lg,exe,f'-ntt27-aw{aw}')
                        lab.resets(field,exe,lanes)
                    else:lab.transform_test(field,aw,exe,f'-ntt27-aw{aw}')
                if not args.quick:
                    for i,(name,digits,base) in enumerate(cases):
                        coeff=[centered_crt((planes[f][i][j] for f in range(3)),EXPERIMENT_PRIMES) for j in range(1<<aw)]
                        m=pow(base,1<<aw)+1
                        if encode(coeff,base)%m!=pow(encode(digits,base),2,m):raise RuntimeError('ntt27 bigint square mismatch')
                        lab.report.setdefault('integer_squares',[]).append({'aw':aw,'name':name,'passed':True})
            if not args.quick and lanes==16:lab.reject_mutants()
            lab.report['status']='passed'
        except Exception:
            lab.report['status']='failed';raise
        finally:
            (lab.output/'report.json').write_text(json.dumps(lab.report,indent=2)+'\n')
            reports.append({'lanes':lanes,'status':lab.report['status'],'report':f'lanes{lanes}/report.json'})
            (args.output/'report.json').write_text(json.dumps({'status':'passed' if all(r['status']=='passed' for r in reports) else 'failed','variants':reports},indent=2)+'\n')


if __name__=='__main__':main()
