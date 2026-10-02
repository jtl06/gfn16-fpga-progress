"""Explicit compact-profile generated NTT regression; execute on aethia only."""
from __future__ import annotations
import argparse, hashlib, json, random, resource, socket, subprocess
from pathlib import Path
from .engine_regression import Lab, dif
from .ntt_difdit_regression import bitreverse
from .ntt27_experiment import select_basis
from .rns_reference import RADIX, naive_ntt, centered_crt
from .ntt_cached_regression import cases_for, encode

PRIMES=select_basis()
TOP='genefer_ntt_banked27_generated_engine'
SOURCES=('genefer_montgomery_mul27_sparse_pipe.sv','genefer_sdp_ram32.sv','genefer_sp_ram.sv',
         'genefer_root_recurrence27.sv','genefer_ntt_banked27_engine.sv',TOP+'.sv')

def profile(field,aw,lg,lanes):
    """Independent pow-based logical seed profile (not RTL bank/router code)."""
    p=PRIMES[field].p;n=1<<lg;r=RADIX%p;k=(2*lanes).bit_length()-1
    psi=pow(PRIMES[field].generator,(p-1)//(2*n),p);omega=psi*psi%p
    words=[]
    for key in range(2*aw+2):
        seeds=[0]*(4*lanes);step=r
        if key in (0,2*aw+1):
            alpha=psi if key==0 else pow(psi,-1,p)
            factor=r if key==0 else pow(n,-1,p)
            for q in range(4):
                for j in range(lanes):seeds[q*lanes+j]=pow(alpha,q*lanes+j,p)*factor%p
            step=pow(alpha,4*lanes,p)*r%p
        else:
            inverse=key>aw;s=key-1-(aw if inverse else 0)
            if s<lg:
                alpha=pow(omega,-1,p) if inverse else omega;h=lg-1-s
                period=1 if s<k else 1<<(s-k+1)
                for q in range(4):
                    g=q%period
                    base=0 if s<k else ((g&1)*(1<<(s%k))+((g>>1)%(1<<(s-k)))*(1<<k))<<h
                    for j in range(min(lanes,1<<s)):
                        v=j if s<k else (j&((1<<(s%k))-1))|((j>>(s%k))<<(s%k+1))
                        seeds[q*lanes+j]=pow(alpha,base+(v<<h),p)*r%p
                step=r if period<=4 else pow(alpha,1<<(k+h+1),p)*r%p
        words+=seeds+[step]
    return words

class GeneratedLab(Lab):
    def build_ntt(self,field,aw,lanes,override=None):
        prime=PRIMES[field]
        paths=[self.root/'rtl/kernel'/s for s in SOURCES]
        if override:paths=[override if p.name==override.name else p for p in paths]
        return self.build(f'build-p{field+1}-aw{aw}-l{lanes}'+('-'+override.parent.name if override else ''),TOP,paths,
            self.root/'rtl/tb'/f'{TOP.removeprefix("genefer_")}.cpp',
            [f'-GAW={aw}',f'-GLANES={lanes}',f'-GP={prime.p}',f'-GQ={prime.q}',
             '-CFLAGS',f'-DNTT_LANES={lanes} -DNTT_AW={aw} -DNTT_P={prime.p}u'])

    def execute(self,name,exe,lines,fuzz=False):
        path=self.output/f'{name}.txt';path.write_text('\n'.join(lines)+'\n')
        dump=self.output/f'{name}-dump.txt'
        self.run(name,(['env','NTT_SKIP_HOST_FUZZ=1'] if not fuzz else [])+[exe,str(path),str(dump)])
        return list(map(int,dump.read_text().split()))

    def transforms(self,field,aw,lg,lanes,exe,fuzz=False):
        p=PRIMES[field].p;n=1<<lg;r=RADIX%p;rng=random.Random(49131+field*31+lg)
        lines=[str(lg),f'REJECT {lg} 0 1']
        def emit(cmd,a):lines.append(cmd+'\n'+' '.join(map(str,a)))
        emit('PROFILE',profile(field,aw,lg,lanes))
        lines += [f'REJECT {lg} 0 0',f'REJECT {lg} 2 1']
        if aw>1:lines.append(f'REJECT {lg-1 if lg>1 else 2} 0 1')
        patterns=[[0]*n,[1]+[0]*(n-1),[p-1]*n,[rng.randrange(p) for _ in range(n)]] if lg<=5 else [[rng.randrange(p) for _ in range(n)]]
        for values in patterns:
            forward=dif(values,p,PRIMES[field].generator)
            if lg<=5:assert forward==naive_ntt(values,PRIMES[field])
            mont=lambda a:[v*r%p for v in a]
            emit('LOAD',mont(values));lines+=['PHASE 1','ORDER 1','RUN 0 0 0'];emit('CHECK',mont(bitreverse(forward)))
            lines+=['PHASE 2','ORDER 0',f'RUN 0 1 {pow(n,-1,p)*r%p}'];emit('CHECK',mont(values))
            emit('LOAD',mont(bitreverse(values)));lines+=['PHASE 1','ORDER 0','RUN 0 0 0'];emit('CHECK',mont(forward))
            lines+=['PHASE 2','ORDER 1',f'RUN 0 1 {pow(n,-1,p)*r%p}'];emit('CHECK',mont(bitreverse(values)))
        return self.execute(f'transform-p{field+1}-aw{aw}-n{n}',exe,lines,fuzz)

    def squares(self,field,aw,lg,lanes,exe,cases):
        p=PRIMES[field].p;n=1<<lg;r=RADIX%p;invn=pow(n,-1,p)
        psi=pow(PRIMES[field].generator,(p-1)//(2*n),p)
        twist=[pow(psi,i,p) for i in range(n)];post=[pow(psi,-i,p)*invn%p for i in range(n)]
        lines=[str(lg)]
        def emit(cmd,a):lines.append(cmd+'\n'+' '.join(map(str,a)))
        emit('PROFILE',profile(field,aw,lg,lanes));planes=[]
        for name,digits,base in cases:
            a=[v%p for v in digits];emit('LOAD',[v*r%p for v in a])
            lines+=['PHASE 0','RUN 2 0 0'];a=[v*w%p for v,w in zip(a,twist)];emit('CHECK',[v*r%p for v in a])
            lines+=['PHASE 1','ORDER 1','RUN 0 0 0'];a=bitreverse(dif(a,p,PRIMES[field].generator));emit('CHECK',[v*r%p for v in a])
            lines+=['RUN 1 0 0'];a=[v*v%p for v in a];emit('CHECK',[v*r%p for v in a])
            lines+=['PHASE 2','ORDER 0','RUN 0 0 0'];a=[v*n%p for v in dif(bitreverse(a),p,PRIMES[field].generator,True)];emit('CHECK',[v*r%p for v in a])
            lines+=['PHASE 3','RUN 2 0 0'];a=[v*w%p for v,w in zip(a,post)];emit('CHECK',a);lines.append('DUMP');planes.append(a)
        got=self.execute(f'squares-p{field+1}-aw{aw}-n{n}',exe,lines)
        assert got==sum(planes,[])
        return planes

    def resets(self,field,aw,lanes,exe):
        lg=min(5,aw);n=1<<lg;p=PRIMES[field].p;r=RADIX%p
        words=profile(field,aw,lg,lanes);lines=[str(lg)];a=[(i*7919+17)%p for i in range(n)]
        def emit(cmd,v):lines.append(cmd+'\n'+' '.join(map(str,v)))
        k=(2*lanes).bit_length()-1;groups=(n+2*lanes-1)//(2*lanes)
        setup=sum(min(4,groups,1 if s<k else 1<<(s-k+1))*min(lanes,1<<s)+4 for s in range(lg))
        transform=lg*(groups+8)+setup;point=(n+lanes-1)//lanes+7
        for phase,op,inv in ((1,0,0),(2,0,1),(0,2,0),(3,2,0),(0,1,0),(0,3,0)):
            # Early reset, seed RAM response/clear/setup, butterfly and multiplier pipelines.
            limit=transform+(point if inv else 0) if op==0 else point+(min(4,(n+lanes-1)//lanes)*min(lanes,n)+4 if op==2 else 0)
            times=set(range(1,15))|{limit-2,limit-1}
            if op==0 and inv:times.update((transform-1,transform,transform+1,transform+2))
            for when in sorted(t for t in times if 0<t<limit):
                emit('PROFILE',words);emit('LOAD',a);lines+= [f'PHASE {phase}',f'ABORT_AT {op} {inv} {r} {when}',f'REJECT {lg} 0 1']
        emit('LOAD',a);lines+=['RUN 3 0 '+str(r)];emit('CHECK',a)
        emit('PROFILE',words);emit('LOAD',a);lines+=['PHASE 1','ORDER 1','RUN 0 0 0'];emit('CHECK',bitreverse(dif(a,p,PRIMES[field].generator)))
        self.execute(f'reset-p{field+1}-aw{aw}',exe,lines)

    def size_reload(self,field,aw,lanes,exe):
        if aw==1:return
        p=PRIMES[field].p;r=RADIX%p;lines=['1']
        def emit(cmd,a):lines.append(cmd+'\n'+' '.join(map(str,a)))
        for lg in (1,min(5,aw),min(3,aw),1):
            n=1<<lg;lines += [f'SIZE {lg}',f'REJECT {lg} 0 1']
            emit('PROFILE',profile(field,aw,lg,lanes));a=[(37*i+941)%p for i in range(n)]
            emit('LOAD',[v*r%p for v in a]);lines+=['PHASE 1','ORDER 1','RUN 0 0 0']
            emit('CHECK',[v*r%p for v in bitreverse(dif(a,p,PRIMES[field].generator))])
            lines+=['PHASE 2','ORDER 0',f'RUN 0 1 {pow(n,-1,p)*r%p}'];emit('CHECK',[v*r%p for v in a])
        self.execute(f'size-reload-p{field+1}-aw{aw}',exe,lines)

    def mutants(self,lanes):
        source=self.root/'rtl/kernel'/f'{TOP}.sv'
        cases=[('profile-size','profile_loaded_size!=size_log2','1\'b0'),
               ('root-bank','base_bank_d','base_bank'),
               ('seed-step','seed_step<=profile_q;','seed_step<=32\'d1;'),
               ('point-route','point_bank_d','point_bank_d ^ 1'),
               ('inverse-profile',"1+32'(AW)+32'(stage_bit)","1+32'(stage_bit)"),
               ('period-wrap',"int'(stage_bit)-KW+1","int'(stage_bit)-KW+2"),
               ('seed-response-tag','seed_tag<=seed_issue;','seed_tag<=seed_issue+1;'),
               ('group-skip','group_index<=group_index+1;','group_index<=group_index+2;'),
               ('profile-commit',"int'(profile_next_addr)==PROFILE_WORDS","1'b1"),
               ('phase-guard',"(op==0 && root_phase!=1 && root_phase!=2)","1'b0")]
        for name,old,new in cases:
            text=source.read_text()
            if name=='root-bank':old='remove_bit(int\'(base_bank_d),int\'(pairing_d))';new='remove_bit(int\'(base_bank),int\'(pairing_d))'
            if name=='point-route':old="KW'(point_bank_d)";new="(KW'(point_bank_d)^KW'(1))"
            if old not in text:raise RuntimeError('missing mutant anchor '+old)
            folder=self.output/f'mutant-{name}';folder.mkdir();path=folder/source.name;path.write_text(text.replace(old,new))
            exe=self.build_ntt(0,10,lanes,path)
            command=self.output/'transform-p1-aw10-n1024.txt'
            if name=='point-route':command=self.output/'squares-p1-aw10-n1024.txt'
            result=subprocess.run(['env','NTT_SKIP_HOST_FUZZ=1',exe,str(command),str(folder/'dump')],capture_output=True,text=True,timeout=180)
            (folder/'result.log').write_text(result.stdout+result.stderr)
            passed=result.returncode!=0 and any(v in result.stdout+result.stderr for v in ('mismatch','accepted','timeout','FAIL','seed loader error','recurrence stall'))
            self.report['steps'].append({'name':'mutant-'+name,'passed':passed})
            if not passed:raise RuntimeError('survived mutant '+name)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=Path);ap.add_argument('--quick',action='store_true');ap.add_argument('--mutants',action='store_true');args=ap.parse_args()
    if args.mutants and not args.quick:ap.error('--mutants requires --quick (AW10/LANES16 mutation fixture)')
    if socket.gethostname()!='aethia':raise RuntimeError('simulation only on aethia')
    resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30));args.output.mkdir(parents=True,exist_ok=True)
    for lanes in ((16,) if args.quick else (16,64)):
        lab=GeneratedLab(args.output/f'lanes{lanes}','verilator')
        try:
            for aw in ((10,) if args.quick else (1,16)):
                cases=cases_for(aw);planes=[]
                if aw==16:cases.append(('max-base1e9',[999999999]*(1<<aw),1000000000))
                for field in range(1 if args.quick else 3):
                    exe=lab.build_ntt(field,aw,lanes)
                    for lg in ((1,4,6,8,10) if args.quick else range(1,aw+1)):lab.transforms(field,aw,lg,lanes,exe,lg==aw)
                    planes.append(lab.squares(field,aw,aw,lanes,exe,cases));lab.resets(field,aw,lanes,exe)
                    lab.size_reload(field,aw,lanes,exe)
                if not args.quick:
                    for i,(name,digits,base) in enumerate(cases):
                        coeff=[centered_crt((planes[f][i][j] for f in range(3)),PRIMES) for j in range(1<<aw)]
                        modulus=pow(base,1<<aw)+1
                        assert encode(coeff,base)%modulus==pow(encode(digits,base),2,modulus)
                    lab.report['whole_integer_crt_aw'+str(aw)]=True
            if args.mutants:lab.mutants(lanes)
            lab.report['status']='passed'
        finally:(lab.output/'report.json').write_text(json.dumps(lab.report,indent=2)+'\n')

if __name__=='__main__':main()
