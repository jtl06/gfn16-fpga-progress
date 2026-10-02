"""Registered stage-control candidate validation; simulation on aethia only."""
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


class PredecodeLab(VectorLab):
    def build_ntt(self,field: int,aw: int=16,lanes: int=4) -> str:
        prime=GENEFER_SIGNED_PRIMES[field]
        return self.build(f'build-predecode-p{field+1}-aw{aw}-l{lanes}','genefer_ntt_banked_predecode_engine',
            [self.root/'rtl/kernel'/n for n in ('genefer_montgomery_mul32_pipe.sv','genefer_ntt_difdit_engine.sv','genefer_sdp_ram32.sv','genefer_ntt_banked_predecode_engine.sv')],
            self.root/'rtl/tb/ntt_banked_predecode_engine.cpp',
            [f'-GAW={aw}',f'-GLANES={lanes}',f'-GP={prime.p}',f'-GQ={prime.q}','-CFLAGS',f'-DNTT_LANES={lanes} -DNTT_AW={aw}'])

    def reject_mutants(self) -> None:
        cases=[
            ('pairing',"pairing<=PW'(int'(stage_bit)%KW);",'pairing<=0;'),
            ('root-count',"stage_root_count<=int'(stage_bit)<LW ? KW'(1)<<stage_bit : KW'(LANES);","stage_root_count<=KW'(LANES);"),
            ('fixed-index',"SIW'(fixed_index(s,j))","SIW'(fixed_index(s,j)+1)"),
            ('setup-bypass','state<=op==0 ? STAGE_SETUP : MUL_READ;','state<=op==0 ? BF_READ : MUL_READ;'),
        ]
        for name,old,new in cases:
            directory=self.output/f'mutation-{name}';directory.mkdir(exist_ok=True)
            source=(self.root/'rtl/kernel/genefer_ntt_banked_predecode_engine.sv').read_text()
            if old not in source:raise RuntimeError('missing predecode mutation anchor')
            path=directory/'genefer_ntt_banked_predecode_engine.sv';path.write_text(source.replace(old,new))
            exe=self.build(f'build-mutation-{name}','genefer_ntt_banked_predecode_engine',
                [self.root/'rtl/kernel/genefer_montgomery_mul32_pipe.sv',self.root/'rtl/kernel/genefer_ntt_difdit_engine.sv',self.root/'rtl/kernel/genefer_sdp_ram32.sv',path],
                self.root/'rtl/tb/ntt_banked_predecode_engine.cpp',['-GAW=4','-CFLAGS','-DNTT_AW=4'])
            proc=subprocess.run([exe,str(self.output/'cached-squares-p1-aw4.txt'),str(directory/'dump.txt')],
                cwd=self.root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
            (self.output/f'reject-mutation-{name}.log').write_text(proc.stdout)
            passed=proc.returncode!=0 and any(s in proc.stdout for s in ('mismatch','collision','count disagrees'))
            self.report['steps'].append({'name':f'reject-mutation-{name}','passed':passed,'returncode':proc.returncode})
            print(f"reject-mutation-{name}: {'PASS' if passed else 'FAIL'}",flush=True)
            if not passed:raise RuntimeError(proc.stdout[-2500:])


def main() -> None:
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--quick',action='store_true');args=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('Run simulation on aethia only')
    resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30));args.output.mkdir(parents=True,exist_ok=True);reports=[]
    for lanes in ((4,) if args.quick else (4,16)):
        lab=PredecodeLab(args.output/f'lanes{lanes}','verilator');lab.report['memory_limit_bytes']=6<<30
        try:
            for aw in ((4,) if args.quick else (1,4,16)):
                cases=cases_for(aw);planes=[]
                for field in range(1 if args.quick else 3):
                    exe=lab.build_ntt(field,aw,lanes);planes.append(lab.cached_squares(field,aw,exe,cases))
                    if aw==16:
                        for lg in range(1,17):lab.transform_test(field,lg,exe,f'-predecode-aw{aw}')
                        lab.resets(field,exe,lanes)
                    else:lab.transform_test(field,aw,exe,f'-predecode-aw{aw}')
                if not args.quick:
                    for i,(name,digits,base) in enumerate(cases):
                        coeff=[centered_crt((planes[f][i][j] for f in range(3)),GENEFER_SIGNED_PRIMES) for j in range(1<<aw)]
                        m=pow(base,1<<aw)+1
                        if encode(coeff,base)%m!=pow(encode(digits,base),2,m):raise RuntimeError('predecode bigint square mismatch')
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
