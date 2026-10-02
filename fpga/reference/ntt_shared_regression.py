"""Shared butterfly/pointwise multiplier validation; simulation on aethia only."""
from __future__ import annotations
import argparse
import json
import resource
import socket
import subprocess
from pathlib import Path
from .ntt_vector_regression import VectorLab
from .ntt_cached_regression import cases_for,encode
from .rns_reference import GENEFER_SIGNED_PRIMES,centered_crt


class SharedLab(VectorLab):
    def build_ntt(self,field: int,aw: int=16,lanes: int=4) -> str:
        prime=GENEFER_SIGNED_PRIMES[field]
        return self.build(f'build-shared-p{field+1}-aw{aw}-l{lanes}','genefer_ntt_banked_shared_engine',
            [self.root/'rtl/kernel'/n for n in ('genefer_montgomery_mul32_pipe.sv','genefer_ntt_difdit_engine.sv','genefer_sdp_ram32.sv','genefer_ntt_banked_shared_engine.sv')],
            self.root/'rtl/tb/ntt_banked_shared_engine.cpp',
            [f'-GAW={aw}',f'-GLANES={lanes}',f'-GP={prime.p}',f'-GQ={prime.q}','-CFLAGS',f'-DNTT_LANES={lanes} -DNTT_AW={aw}'])

    def resets(self,field: int,exe: str,lanes: int=4) -> None:
        # Exact shared latency, including reset in the op0 inverse-normalization
        # transition and immediately before completion; reload after every reset.
        prime=GENEFER_SIGNED_PRIMES[field];p=prime.p;r=(1<<32)%p;n=32
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
        name=f'reset-shared-p{field+1}-l{lanes}';path=self.output/f'{name}.txt';path.write_text('\n'.join(lines)+'\n')
        self.run(name,[exe,str(path),str(self.output/f'{name}-dump.txt')])

    def reject_mutants(self) -> None:
        cases=[
            ('point-dif','.dif(bf_in_valid[lane] && active_dif)','.dif(active_dif)'),
            ('point-u',".u(bf_in_valid[lane] ? u : 32'd0)",'.u(u)'),
            ('point-bank','point_half_pipe[6]','point_half_pipe[4]'),
            ('point-row','data_wa[bank]=row_tag[6][bank];data_w[bank]=product',
             'data_wa[bank]=row_tag[4][bank];data_w[bank]=product'),
            ('point-type','shared_valid && point_type_pipe[5]','shared_valid && point_type_pipe[4]'),
            ('normalization-select','.v(bf_in_valid[lane] ? v : mul_lhs)',
             '.v(active_op==0 ? v : mul_lhs)'),
        ]
        for name,old,new in cases:
            directory=self.output/f'mutation-{name}';directory.mkdir(exist_ok=True)
            source=(self.root/'rtl/kernel/genefer_ntt_banked_shared_engine.sv').read_text()
            if old not in source:raise RuntimeError('missing shared mutation anchor')
            path=directory/'genefer_ntt_banked_shared_engine.sv';path.write_text(source.replace(old,new))
            exe=self.build(f'build-mutation-{name}','genefer_ntt_banked_shared_engine',
                [self.root/'rtl/kernel/genefer_montgomery_mul32_pipe.sv',self.root/'rtl/kernel/genefer_ntt_difdit_engine.sv',self.root/'rtl/kernel/genefer_sdp_ram32.sv',path],
                self.root/'rtl/tb/ntt_banked_shared_engine.cpp',['-GAW=4','-CFLAGS','-DNTT_AW=4'])
            proc=subprocess.run([exe,str(self.output/('difdit-p1-n16-shared-aw4.txt' if name=='normalization-select' else 'cached-squares-p1-aw4.txt')),str(directory/'dump.txt')],
                cwd=self.root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
            (self.output/f'reject-mutation-{name}.log').write_text(proc.stdout)
            passed=proc.returncode!=0 and any(s in proc.stdout for s in ('mismatch','collision','count disagrees','timeout'))
            self.report['steps'].append({'name':f'reject-mutation-{name}','passed':passed,'returncode':proc.returncode})
            print(f"reject-mutation-{name}: {'PASS' if passed else 'FAIL'}",flush=True)
            if not passed:raise RuntimeError(proc.stdout[-2500:])


def main() -> None:
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--quick',action='store_true');args=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('Run simulation on aethia only')
    resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30));args.output.mkdir(parents=True,exist_ok=True);reports=[]
    for lanes in ((4,) if args.quick else (4,16)):
        lab=SharedLab(args.output/f'lanes{lanes}','verilator');lab.report['memory_limit_bytes']=6<<30
        try:
            for aw in ((4,) if args.quick else (1,4,16)):
                cases=cases_for(aw);planes=[]
                for field in range(1 if args.quick else 3):
                    exe=lab.build_ntt(field,aw,lanes);planes.append(lab.cached_squares(field,aw,exe,cases))
                    if aw==16:
                        for lg in range(1,17):lab.transform_test(field,lg,exe,f'-shared-aw{aw}')
                        lab.resets(field,exe,lanes)
                    else:lab.transform_test(field,aw,exe,f'-shared-aw{aw}')
                if not args.quick:
                    for i,(name,digits,base) in enumerate(cases):
                        coeff=[centered_crt((planes[f][i][j] for f in range(3)),GENEFER_SIGNED_PRIMES) for j in range(1<<aw)]
                        m=pow(base,1<<aw)+1
                        if encode(coeff,base)%m!=pow(encode(digits,base),2,m):raise RuntimeError('shared bigint square mismatch')
                        lab.report.setdefault('integer_squares',[]).append({'aw':aw,'name':name,'passed':True})
            if not args.quick and lanes==4:lab.reject_mutants()
            lab.report['status']='passed'
        except Exception:
            lab.report['status']='failed';raise
        finally:
            (lab.output/'report.json').write_text(json.dumps(lab.report,indent=2)+'\n')
            reports.append({'lanes':lanes,'status':lab.report['status'],'report':f'lanes{lanes}/report.json'})
            (args.output/'report.json').write_text(json.dumps({'status':'passed' if all(r['status']=='passed' for r in reports) else 'failed','variants':reports},indent=2)+'\n')


if __name__=='__main__':main()
