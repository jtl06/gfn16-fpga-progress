"""Banked multi-lane DIF/DIT prototype checks. Run only on aethia."""
from __future__ import annotations
import argparse
import json
import socket
import subprocess
from pathlib import Path
from .ntt_difdit_regression import DIFDITLab
from .rns_reference import GENEFER_SIGNED_PRIMES, centered_crt


class ParallelLab(DIFDITLab):
    def build_ntt(self, field: int, aw: int=16, lanes: int=4) -> str:
        prime=GENEFER_SIGNED_PRIMES[field]
        return self.build(f'build-parallel-p{field+1}-aw{aw}-l{lanes}','genefer_ntt_parallel_engine',
            [self.root/'rtl/kernel'/n for n in ('genefer_montgomery_mul32_pipe.sv','genefer_ntt_difdit_engine.sv','genefer_ntt_parallel_engine.sv')],
            self.root/'rtl/tb/ntt_parallel_engine.cpp',
            [f'-GAW={aw}',f'-GLANES={lanes}',f'-GP={prime.p}',f'-GQ={prime.q}','-CFLAGS',f'-DNTT_LANES={lanes}'])

    def resets(self, field: int, exe: str, lanes: int=4) -> None:
        prime=GENEFER_SIGNED_PRIMES[field];p=prime.p;r=(1<<32)%p;n=32
        root=pow(prime.generator,(p-1)//n,p);data=[(i*7919+17)%p for i in range(n)]
        lines=['5'];forward_cycles=5*((n+2*lanes-1)//(2*lanes)+7)
        vector_cycles=(n+lanes-1)//lanes+5
        def emit(cmd,a):lines.append(cmd+'\n'+' '.join(map(str,a)))
        for mode in (0,1):
            lines.append(f'ORDER {mode}')
            for op in range(4):
                limit=forward_cycles if op==0 else vector_cycles
                for when in sorted({1,3,min(8,limit-1),limit-1}):
                    emit('LOAD',[v*r%p for v in data]);emit('ROOTS',[pow(root,i,p)*r%p for i in range(n)])
                    lines.append(f'ABORT_AT {op} 0 {r} {when}')
            for op in (1,2,3):
                emit('LOAD',[v*r%p for v in data]);emit('ROOTS',[pow(root,i,p)*r%p for i in range(n)])
                lines.append(f'RUN {op} 0 {r if op!=3 else 1}')
                expected=[v*v*r%p for v in data] if op==1 else [v*pow(root,i,p)*r%p for i,v in enumerate(data)] if op==2 else data
                emit('CHECK',expected)
        name=f'reset-parallel-p{field+1}-l{lanes}';path=self.output/f'{name}.txt';path.write_text('\n'.join(lines)+'\n')
        self.run(name,[exe,str(path),str(self.output/f'{name}-dump.txt')])

    def reject_mutants(self) -> None:
        cases=[
            ('twiddle',"AW'((a&((32'd1<<stage_bit)-1))<<(lg-1-stage_bit))","AW'((a&((32'd1<<stage_bit)-1))<<(lg-stage_bit))"),
            ('write-tag','tag_u[6][lane]','tag_u[5][lane]'),
            ('lane-mask',"32'(lane)<bf_lanes","32'(lane)<=bf_lanes"),
            ('bank-map','b[j%KW]=b[j%KW]^a[j];','b[j%KW]=a[j];'),
        ]
        for name,old,new in cases:
            directory=self.output/f'mutation-{name}';directory.mkdir(exist_ok=True)
            text=(self.root/'rtl/kernel/genefer_ntt_parallel_engine.sv').read_text()
            if old not in text:raise RuntimeError('missing mutation anchor')
            path=directory/'genefer_ntt_parallel_engine.sv';path.write_text(text.replace(old,new))
            exe=self.build(f'build-mutation-{name}','genefer_ntt_parallel_engine',
                [self.root/'rtl/kernel/genefer_montgomery_mul32_pipe.sv',self.root/'rtl/kernel/genefer_ntt_difdit_engine.sv',path],
                self.root/'rtl/tb/ntt_parallel_engine.cpp')
            vector='difdit-p1-n2.txt' if name=='lane-mask' else 'difdit-p1-n32.txt'
            proc=subprocess.run([exe,str(self.output/vector),str(directory/'dump.txt')],
                                cwd=self.root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
            (self.output/f'reject-mutation-{name}.log').write_text(proc.stdout)
            passed=proc.returncode!=0 and any(s in proc.stdout for s in ('NTT mismatch','bank conflict','RAM collision','accounting mismatch'))
            self.report['steps'].append({'name':f'reject-mutation-{name}','passed':passed,'returncode':proc.returncode})
            print(f"reject-mutation-{name}: {'PASS' if passed else 'FAIL'}",flush=True)
            if not passed:raise RuntimeError(proc.stdout[-2000:])


def main() -> None:
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--quick',action='store_true');args=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('Run simulation on aethia only')
    lab=ParallelLab(args.output,'verilator')
    try:
        executables=[];corner_planes={1:[],4:[]}
        for field in range(1 if args.quick else 3):
            exe=lab.build_ntt(field);executables.append(exe)
            for lg in ((1,2,3,4,5) if args.quick else range(1,17)):lab.transform_test(field,lg,exe)
            lab.resets(field,exe)
            if not args.quick:
                for aw in (1,4):
                    small=lab.build_ntt(field,aw);lab.transform_test(field,aw,small,f'-aw{aw}')
                    digits=[(i*7919+3)%1024 for i in range(1<<aw)]
                    corner_planes[aw].append(lab.square_field(field,digits,small,f'parallel-square-aw{aw}'))
        if not args.quick:
            for aw,planes in corner_planes.items():
                n=1<<aw;digits=[(i*7919+3)%1024 for i in range(n)];expected=[0]*n
                for i,a in enumerate(digits):
                    for j,b in enumerate(digits):expected[(i+j)%n]+=a*b if i+j<n else -a*b
                got=[centered_crt((plane[i] for plane in planes),GENEFER_SIGNED_PRIMES) for i in range(n)]
                if got!=expected:raise RuntimeError('parameter-corner convolution mismatch')
                lab.report.setdefault('corner_convolutions',[]).append({'aw':aw,'passed':True})
            lab.square_checks(executables)
            for lanes in (1,2,8):
                exe=lab.build_ntt(0,16,lanes)
                for lg in (1,2,3,4,5,16):lab.transform_test(0,lg,exe,f'-lanes{lanes}')
                lab.resets(0,exe,lanes)
            lab.reject_mutants()
        lab.report['status']='passed'
    except Exception:
        lab.report['status']='failed';raise
    finally:(lab.output/'report.json').write_text(json.dumps(lab.report,indent=2)+'\n')


if __name__=='__main__':main()
