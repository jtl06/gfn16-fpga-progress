"""Bank-centric routing proof and independent RTL checks; aethia only."""
from __future__ import annotations
import argparse
import json
import re
import resource
import socket
import subprocess
from pathlib import Path
from .ntt_cached_regression import CachedLab,cases_for,encode
from .rns_reference import GENEFER_SIGNED_PRIMES,centered_crt


def schedule_check(lg: int, lanes: int) -> None:
    n=1<<lg;k=(2*lanes).bit_length()-1;banks=2*lanes
    def bank(a):
        value=0
        while a:value^=a&(banks-1);a>>=k
        return value
    def inverse(b,row):return (row<<k)|(b^bank(row<<k))
    def rol(x,r):return ((x<<r)|(x>>(k-r)))&(banks-1)
    def ror(x,r):return ((x>>r)|(x<<(k-r)))&(banks-1)
    for s in range(lg):
        p=s%k;shift=lg-1-s;rotation=shift%k
        fixed=[j for j in range(lg) if j!=s and not(j<k and j!=p)]
        seen=set()
        for g in range(max(1,n//banks)):
            base=sum(((g>>i)&1)<<j for i,j in enumerate(fixed));bb=bank(base);ori=(bb>>p)&1
            rbase=(base&((1<<s)-1))<<shift;rb=bank(rbase)
            mask=(1<<s)-1 if s<k else (banks-1)^(1<<p)
            need_roots=set()
            rows={b:(base|((((b>>p)&1)^ori)<<s))>>k for b in range(min(banks,n))}
            for lane in range(min(lanes,n//2)):
                lo=(lane&((1<<p)-1))|((lane>>p)<<(p+1));hi=lo|(1<<p)
                bu=hi if ori else lo;bv=lo if ori else hi
                u=inverse(bu,rows[bu]);v=inverse(bv,rows[bv])
                assert u^(1<<s)==v and not(u&(1<<s))
                assert u not in seen and v not in seen;seen.update((u,v))
                t=(u&((1<<s)-1))<<shift;need_roots.add(t)
                # Structured root permutation must route the expected bank.
                x=bu^bb
                if s<k:x&=(1<<s)-1
                assert rol(x,rotation)^rb==bank(t)
            got_roots=set()
            for b in range(banks):
                var=ror(b^rb,rotation)
                if var&~mask==0:
                    t=rbase|(var<<shift);assert bank(t)==b and t<n//2;got_roots.add(t)
            assert got_roots==need_roots
        assert seen==set(range(n))
    seen=set()
    for g in range(max(1,n//lanes)):
        base=g*lanes;half=(bank(base)>>(k-1))&1;row=base>>k
        for lane in range(min(lanes,n)):
            a=inverse(lane+half*lanes,row);assert a not in seen and a//lanes==g;seen.add(a)
    assert seen==set(range(n))


class BankedLab(CachedLab):
    def build_ntt(self,field: int,aw: int=16,lanes: int=4) -> str:
        prime=GENEFER_SIGNED_PRIMES[field]
        exe=self.build(f'build-banked-p{field+1}-aw{aw}-l{lanes}','genefer_ntt_banked_engine',
            [self.root/'rtl/kernel'/n for n in ('genefer_montgomery_mul32_pipe.sv','genefer_ntt_difdit_engine.sv','genefer_ntt_banked_engine.sv')],
            self.root/'rtl/tb/ntt_banked_engine.cpp',
            [f'-GAW={aw}',f'-GLANES={lanes}',f'-GP={prime.p}',f'-GQ={prime.q}','-CFLAGS',f'-DNTT_LANES={lanes}'])
        if aw==16:
            header=(Path(exe).parent/'Vgenefer_ntt_banked_engine___024root.h').read_text()
            lines=[line for line in header.splitlines() if 'root_mem' in line]
            depth=3*(1<<aw)//(2*lanes)
            if len(lines)!=2*lanes or not all(re.search(rf'\b{depth}\b',line) for line in lines):raise RuntimeError('bad banked memory shape')
            self.report.setdefault('root_array_shape',[]).append({'field':field,'lanes':lanes,'banks':2*lanes,'words_per_bank':depth,'total_words':3*(1<<aw),'verified':True})
        return exe

    def reject_mutants(self) -> None:
        cases=[
            ('orientation','orientation_d ? data_hi[pairing_d] : data_lo[pairing_d]',
             'orientation_d ? data_lo[pairing_d] : data_hi[pairing_d]'),
            ('root-permutation','root_base_bank_d[d-1] ? root_xor_stages[d-1].words[b^(1<<(d-1))] : root_xor_stages[d-1].words[b]',
             'root_xor_stages[d-1].words[b]'),
            ('row-tag','row_tag[6][bank]','row_tag[5][bank]'),
            ('vector-half','point_half_pipe[4]','point_half_pipe[3]'),
        ]
        for name,old,new in cases:
            directory=self.output/f'mutation-{name}';directory.mkdir(exist_ok=True)
            text=(self.root/'rtl/kernel/genefer_ntt_banked_engine.sv').read_text()
            if old not in text:raise RuntimeError('missing banked mutation anchor')
            path=directory/'genefer_ntt_banked_engine.sv';path.write_text(text.replace(old,new))
            exe=self.build(f'build-mutation-{name}','genefer_ntt_banked_engine',
                [self.root/'rtl/kernel/genefer_montgomery_mul32_pipe.sv',self.root/'rtl/kernel/genefer_ntt_difdit_engine.sv',path],
                self.root/'rtl/tb/ntt_banked_engine.cpp',['-GAW=4'])
            proc=subprocess.run([exe,str(self.output/'cached-squares-p1-aw4.txt'),str(directory/'dump.txt')],
                cwd=self.root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
            (self.output/f'reject-mutation-{name}.log').write_text(proc.stdout)
            passed=proc.returncode!=0 and any(s in proc.stdout for s in ('NTT mismatch','RAM collision'))
            self.report['steps'].append({'name':f'reject-mutation-{name}','passed':passed,'returncode':proc.returncode})
            print(f"reject-mutation-{name}: {'PASS' if passed else 'FAIL'}",flush=True)
            if not passed:raise RuntimeError(proc.stdout[-2000:])


def main() -> None:
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--quick',action='store_true');args=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('Run simulation on aethia only')
    resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30))
    lab=BankedLab(args.output,'verilator')
    lab.report['per_process_address_space_limit_bytes']=6<<30
    try:
        for lanes in (4,16):
            for lg in ((1,4,5) if args.quick else range(1,17)):schedule_check(lg,lanes)
        lab.report['schedule_proof']={'passed':True,'lanes':[4,16],'lg_max':5 if args.quick else 16}
        for aw in ((4,) if args.quick else (1,4,16)):
            cases=cases_for(aw);all_planes=[]
            for field in range(1 if args.quick else 3):
                exe=lab.build_ntt(field,aw);all_planes.append(lab.cached_squares(field,aw,exe,cases))
                lab.transform_test(field,aw,exe,f'-banked-aw{aw}')
                if aw==16:
                    for lg in (1,2,3,4,5,8,12,15):lab.transform_test(field,lg,exe,f'-banked-aw{aw}')
                    lab.resets(field,exe)
            if not args.quick:
                for i,(name,digits,base) in enumerate(cases):
                    coeff=[centered_crt((all_planes[f][i][j] for f in range(3)),GENEFER_SIGNED_PRIMES) for j in range(1<<aw)]
                    m=pow(base,1<<aw)+1
                    if encode(coeff,base)%m!=pow(encode(digits,base),2,m):raise RuntimeError('banked bigint mismatch')
                    if aw<=4:
                        school=[0]*(1<<aw)
                        for j,a in enumerate(digits):
                            for k,b in enumerate(digits):school[(j+k)%len(digits)]+=a*b if j+k<len(digits) else -a*b
                        if coeff!=school:raise RuntimeError('banked schoolbook mismatch')
                    lab.report.setdefault('banked_integer_squares',[]).append({'aw':aw,'name':name,'base':base,'passed':True})
        if not args.quick:
            wide=BankedLab(lab.output/'lanes16','verilator')
            exe=wide.build_ntt(0,16,16)
            for lg in (1,2,3,4,5,8,16):wide.transform_test(0,lg,exe,'-lanes16')
            wide.resets(0,exe,16)
            # P1 full-size cached recurrent squares also exercise 32-bank routing.
            wide.cached_squares(0,16,exe,cases_for(16))
            wide.report['status']='passed'
            (wide.output/'report.json').write_text(json.dumps(wide.report,indent=2)+'\n')
            lab.report['lanes16_report']='lanes16/report.json'
            lab.reject_mutants()
        lab.report['status']='passed'
    except Exception:
        lab.report['status']='failed';raise
    finally:(lab.output/'report.json').write_text(json.dumps(lab.report,indent=2)+'\n')


if __name__=='__main__':main()
