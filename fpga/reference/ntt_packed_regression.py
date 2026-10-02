"""Isolated RAM-template diagnostic validation; aethia only, no vendor tools."""
from __future__ import annotations
import argparse
import hashlib
import json
import resource
import socket
import subprocess
from pathlib import Path
from .ntt_cached_regression import CachedLab,cases_for,encode
from .rns_reference import GENEFER_SIGNED_PRIMES,centered_crt


class PackedRAMLab(CachedLab):
    def build_ntt(self,field: int,aw: int=16,lanes: int=4) -> str:
        prime=GENEFER_SIGNED_PRIMES[field]
        return self.build(f'build-packed-p{field+1}-aw{aw}-l{lanes}','genefer_ntt_banked_packed_engine',
            [self.root/'rtl/kernel'/n for n in ('genefer_montgomery_mul32_pipe.sv','genefer_ntt_difdit_engine.sv','genefer_sdp_ram32.sv','genefer_ntt_banked_packed_engine.sv')],
            self.root/'rtl/tb/ntt_banked_packed_engine.cpp',
            [f'-GAW={aw}',f'-GLANES={lanes}',f'-GP={prime.p}',f'-GQ={prime.q}','-CFLAGS',f'-DNTT_LANES={lanes}'])

    def reject_mutants(self) -> None:
        cases=[
            ('middle-alias',"middle_write_addr=MRW'(root_write_addr-RRW'(DEPTH));",
             "middle_write_addr=MRW'(root_write_addr-RRW'(root_phase==2 ? DEPTH+HALF_DEPTH : DEPTH));"),
            ('post-select',"root_write_en && root_phase==3","root_write_en && root_phase==0"),
            ('live-read-phase',"read_twist=active_root_base==0;","read_twist=root_phase==0;"),
            ('upper-half-write',"!half_write_illegal && host_bank","host_bank"),
        ]
        for name,old,new in cases:
            directory=self.output/f'mutation-{name}';directory.mkdir(exist_ok=True)
            text=(self.root/'rtl/kernel/genefer_ntt_banked_packed_engine.sv').read_text()
            if old not in text:raise RuntimeError('missing packed mutation anchor')
            path=directory/'genefer_ntt_banked_packed_engine.sv';path.write_text(text.replace(old,new))
            exe=self.build(f'build-mutation-{name}','genefer_ntt_banked_packed_engine',
                [self.root/'rtl/kernel/genefer_montgomery_mul32_pipe.sv',self.root/'rtl/kernel/genefer_ntt_difdit_engine.sv',
                 self.root/'rtl/kernel/genefer_sdp_ram32.sv',path],
                self.root/'rtl/tb/ntt_banked_packed_engine.cpp',['-GAW=4'])
            proc=subprocess.run([exe,str(self.output/'cached-squares-p1-aw4.txt'),str(directory/'dump.txt')],
                cwd=self.root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
            (self.output/f'reject-mutation-{name}.log').write_text(proc.stdout)
            passed=proc.returncode!=0 and any(s in proc.stdout for s in ('NTT mismatch','RAM read outside','RAM write outside'))
            self.report['steps'].append({'name':f'reject-mutation-{name}','passed':passed,'returncode':proc.returncode})
            print(f"reject-mutation-{name}: {'PASS' if passed else 'FAIL'}",flush=True)
            if not passed:raise RuntimeError(proc.stdout[-2000:])


def main() -> None:
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--quick',action='store_true');args=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('Run simulation on aethia only')
    resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30))
    lab=PackedRAMLab(args.output,'verilator');lab.report['memory_limit_bytes']=6<<30
    try:
        for aw in ((4,) if args.quick else (1,4,16)):
            cases=cases_for(aw);planes=[]
            for field in range(1 if args.quick else 3):
                exe=lab.build_ntt(field,aw);planes.append(lab.cached_squares(field,aw,exe,cases))
                lab.transform_test(field,aw,exe,f'-packed-aw{aw}')
                if aw>=5:lab.resets(field,exe)
                if aw==16:
                    for lg in (1,2,3,4,5):lab.transform_test(field,lg,exe,f'-packed-small{lg}')
            if not args.quick:
                for i,(name,digits,base) in enumerate(cases):
                    coeff=[centered_crt((planes[f][i][j] for f in range(3)),GENEFER_SIGNED_PRIMES) for j in range(1<<aw)]
                    modulus=pow(base,1<<aw)+1
                    if encode(coeff,base)%modulus!=pow(encode(digits,base),2,modulus):raise RuntimeError('RAM-template square mismatch')
                    lab.report.setdefault('integer_squares',[]).append({'aw':aw,'name':name,'passed':True})
        if not args.quick:lab.reject_mutants()
        lab.report['status']='passed'
    except Exception:
        lab.report['status']='failed';raise
    finally:(lab.output/'report.json').write_text(json.dumps(lab.report,indent=2)+'\n')


if __name__=='__main__':main()
