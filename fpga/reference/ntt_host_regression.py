"""Shared butterfly/pointwise multiplier validation; simulation on aethia only."""
from __future__ import annotations
import argparse
import json
import resource
import socket
import subprocess
from pathlib import Path
from .ntt_vector_regression import VectorLab
from .ntt_banked_regression import schedule_check
from .ntt_cached_regression import cases_for,encode
from .rns_reference import GENEFER_SIGNED_PRIMES,centered_crt


class HostLab(VectorLab):
    def run(self,name,command,reject=None):
        # Every cached-square invocation retains the full physical host
        # scoreboard. Transform/reset invocations retain their own host traffic
        # and complete arithmetic oracle, without repeating that same prelude.
        if name.startswith(('difdit-','reset-host-')):
            command=['env','NTT_SKIP_HOST_FUZZ=1',*command]
        return super().run(name,command,reject)

    def build_ntt(self,field: int,aw: int=16,lanes: int=64) -> str:
        prime=GENEFER_SIGNED_PRIMES[field]
        return self.build(f'build-host-p{field+1}-aw{aw}-l{lanes}','genefer_ntt_banked_host_engine',
            [self.root/'rtl/kernel'/n for n in ('genefer_montgomery_mul32_pipe.sv','genefer_ntt_difdit_engine.sv','genefer_sdp_ram32.sv','genefer_ntt_banked_wide_engine.sv','genefer_ntt_banked_host_engine.sv')],
            self.root/'rtl/tb/ntt_banked_host_engine.cpp',
            [f'-GAW={aw}',f'-GLANES={lanes}',f'-GP={prime.p}',f'-GQ={prime.q}','-CFLAGS',f'-DNTT_LANES={lanes} -DNTT_AW={aw}'])

    def resets(self,field: int,exe: str,lanes: int=4) -> None:
        # Exact host latency, including reset in the op0 inverse-normalization
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
        name=f'reset-host-p{field+1}-l{lanes}';path=self.output/f'{name}.txt';path.write_text('\n'.join(lines)+'\n')
        self.run(name,[exe,str(path),str(self.output/f'{name}-dump.txt')])

    def reject_mutants(self) -> None:
        cases=[
            ('alignment',"(32'(vector_addr)&32'(HOST_LANES-1))==0","(32'(vector_addr)&32'(LANES-1))==0"),
            ('range-before-rounding',"32'(vector_addr)<host_n","32'(child_addr)<host_n"),
            ('quarter-write',"host_group==GW'(h/HOST_LANES)","1'b1"),
            ('quarter-read',"int'(read_group)*HOST_LANES+h","h"),
            ('root-suppression','.root_we(root_we && !request)','.root_we(root_we)'),
            ('scalar-suppression','.load_we(load_we && !request)','.load_we(load_we)'),
            ('busy-error','local_error<=!busy && !start && request && !descriptor_ok;','local_error<=!start && request && !descriptor_ok;'),
            ('start-error','local_error<=!busy && !start && request && !descriptor_ok;','local_error<=!busy && request && !descriptor_ok;'),
        ]
        for name,old,new in cases:
            directory=self.output/f'mutation-{name}';directory.mkdir(exist_ok=True)
            source=(self.root/'rtl/kernel/genefer_ntt_banked_host_engine.sv').read_text()
            if old not in source:raise RuntimeError('missing host mutation anchor')
            path=directory/'genefer_ntt_banked_host_engine.sv';path.write_text(source.replace(old,new))
            exe=self.build(f'build-mutation-{name}','genefer_ntt_banked_host_engine',
                [self.root/'rtl/kernel/genefer_montgomery_mul32_pipe.sv',self.root/'rtl/kernel/genefer_ntt_difdit_engine.sv',self.root/'rtl/kernel/genefer_sdp_ram32.sv',self.root/'rtl/kernel/genefer_ntt_banked_wide_engine.sv',path],
                self.root/'rtl/tb/ntt_banked_host_engine.cpp',['-GAW=8','-GLANES=64','-CFLAGS','-DNTT_AW=8 -DNTT_LANES=64 -DNTT_HOST_LANES=16'])
            proc=subprocess.run([exe,str(self.output/'cached-squares-p1-aw4.txt'),str(directory/'dump.txt')],
                cwd=self.root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
            (self.output/f'reject-mutation-{name}.log').write_text(proc.stdout)
            passed=proc.returncode!=0 and any(s in proc.stdout for s in ('mismatch','collision','count disagrees','timeout','adapter','alignment','suppression'))
            self.report['steps'].append({'name':f'reject-mutation-{name}','passed':passed,'returncode':proc.returncode})
            print(f"reject-mutation-{name}: {'PASS' if passed else 'FAIL'}",flush=True)
            if not passed:raise RuntimeError(proc.stdout[-2500:])


def main() -> None:
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--quick',action='store_true');args=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('Run simulation on aethia only')
    resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30));args.output.mkdir(parents=True,exist_ok=True);reports=[]
    for lanes in (64,):
        lab=HostLab(args.output/f'lanes{lanes}','verilator');lab.report['memory_limit_bytes']=6<<30
        lab.report['host_fuzz_policy']='Full physical host scoreboard for every cached-square invocation and every mutant; no duplicate prelude for transform/reset invocations.'
        try:
            for lg in ((1,4,6,7,8) if args.quick else range(1,17)):schedule_check(lg,lanes)
            lab.report['schedule_proof']={'passed':True,'lanes':lanes,'max_lg':8 if args.quick else 16}
            for aw in ((8,) if args.quick else (1,4,16)):
                cases=cases_for(aw);planes=[]
                for field in range(1 if args.quick else 3):
                    exe=lab.build_ntt(field,aw,lanes);planes.append(lab.cached_squares(field,aw,exe,cases))
                    if aw==16:
                        for lg in range(1,17):lab.transform_test(field,lg,exe,f'-host-aw{aw}')
                        lab.resets(field,exe,lanes)
                    else:lab.transform_test(field,aw,exe,f'-host-aw{aw}')
                if not args.quick:
                    for i,(name,digits,base) in enumerate(cases):
                        coeff=[centered_crt((planes[f][i][j] for f in range(3)),GENEFER_SIGNED_PRIMES) for j in range(1<<aw)]
                        m=pow(base,1<<aw)+1
                        if encode(coeff,base)%m!=pow(encode(digits,base),2,m):raise RuntimeError('host bigint square mismatch')
                        lab.report.setdefault('integer_squares',[]).append({'aw':aw,'name':name,'passed':True})
            if not args.quick and lanes==64:lab.reject_mutants()
            lab.report['status']='passed'
        except Exception:
            lab.report['status']='failed';raise
        finally:
            (lab.output/'report.json').write_text(json.dumps(lab.report,indent=2)+'\n')
            reports.append({'lanes':lanes,'status':lab.report['status'],'report':f'lanes{lanes}/report.json'})
            (args.output/'report.json').write_text(json.dumps({'status':'passed' if all(r['status']=='passed' for r in reports) else 'failed','variants':reports},indent=2)+'\n')


if __name__=='__main__':main()
