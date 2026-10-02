"""Isolated RAM-template diagnostic validation; aethia only, no vendor tools."""
from __future__ import annotations
import argparse
import hashlib
import json
import resource
import socket
from pathlib import Path
from .ntt_cached_regression import CachedLab,cases_for,encode
from .rns_reference import GENEFER_SIGNED_PRIMES,centered_crt


class ModuleRAMLab(CachedLab):
    def build_ntt(self,field: int,aw: int=16,lanes: int=4) -> str:
        prime=GENEFER_SIGNED_PRIMES[field]
        return self.build(f'build-modulemem-p{field+1}-aw{aw}-l{lanes}','genefer_ntt_banked_modulemem_engine',
            [self.root/'rtl/kernel'/n for n in ('genefer_montgomery_mul32_pipe.sv','genefer_ntt_difdit_engine.sv','genefer_sdp_ram32.sv','genefer_ntt_banked_modulemem_engine.sv')],
            self.root/'rtl/tb/ntt_banked_modulemem_engine.cpp',
            [f'-GAW={aw}',f'-GLANES={lanes}',f'-GP={prime.p}',f'-GQ={prime.q}','-CFLAGS',f'-DNTT_LANES={lanes}'])


def main() -> None:
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--quick',action='store_true');args=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('Run simulation on aethia only')
    resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30))
    lab=ModuleRAMLab(args.output,'verilator');lab.report['memory_limit_bytes']=6<<30
    try:
        for aw in ((8,) if args.quick else (1,8,16)):
            cases=cases_for(aw);planes=[]
            for field in range(1 if args.quick else 3):
                exe=lab.build_ntt(field,aw);planes.append(lab.cached_squares(field,aw,exe,cases))
                lab.transform_test(field,aw,exe,f'-modulemem-aw{aw}')
                if aw>=5:lab.resets(field,exe)
            if not args.quick:
                for i,(name,digits,base) in enumerate(cases):
                    coeff=[centered_crt((planes[f][i][j] for f in range(3)),GENEFER_SIGNED_PRIMES) for j in range(1<<aw)]
                    modulus=pow(base,1<<aw)+1
                    if encode(coeff,base)%modulus!=pow(encode(digits,base),2,modulus):raise RuntimeError('RAM-template square mismatch')
                    lab.report.setdefault('integer_squares',[]).append({'aw':aw,'name':name,'passed':True})
        lab.report['status']='passed'
    except Exception:
        lab.report['status']='failed';raise
    finally:(lab.output/'report.json').write_text(json.dumps(lab.report,indent=2)+'\n')


if __name__=='__main__':main()
