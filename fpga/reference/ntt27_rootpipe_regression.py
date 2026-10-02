"""Root-XOR cut validation; unchanged arithmetic oracle, nine-clock writeback, aethia only."""
from __future__ import annotations
import argparse
import json
import resource
import os
import signal
import shutil
import time
import hashlib
import sys
import re
import socket
import subprocess
from pathlib import Path
from .engine_regression import Lab,dif
from .ntt27_rootpipe_structure import validate_files
from .ntt_difdit_regression import bitreverse
from .ntt27_experiment import select_basis,prove_basis
from .ntt27_folded_routing import prove as prove_folded_routing
import random
from .ntt_banked_regression import schedule_check
from .ntt_cached_regression import cases_for,encode
from .rns_reference import RADIX,centered_crt,naive_ntt
from .square_core_regression import cache_context

assert RADIX == 1<<32, '27-bit operands do not change Montgomery radix'
EXPERIMENT_PRIMES=select_basis()


def bench_proof(root):
    ancestor=(root/'rtl/tb/ntt_banked27_tiled_engine.cpp').read_text()
    if hashlib.sha256(ancestor.encode()).hexdigest()!='c9f78aa9ad00a0dbbc23a576dca62f4d9533a5f5398be10b9aceff3221e4d4ce':
        raise RuntimeError('frozen tiled bench changed')
    expected=ancestor.replace('genefer_ntt_banked27_tiled_engine','genefer_ntt_banked27_rootpipe_engine')
    expected=expected.replace('(op==0?8*lg:0)+(mul?8:0)','(op==0?9*lg:0)+(mul?9:0)')
    if (root/'rtl/tb/ntt_banked27_rootpipe_engine.cpp').read_text()!=expected:
        raise RuntimeError('bench changed beyond rename and exact drain8 to9')
    return {'ancestor_sha256':hashlib.sha256(ancestor.encode()).hexdigest(),
            'candidate_sha256':hashlib.sha256(expected.encode()).hexdigest(),'passed':True}


class NTT27RootpipeLab(Lab):
    def run(self,name,command,reject=None):
        if name.startswith(('difdit-','reset-ntt27-')):
            command=['env','NTT_SKIP_HOST_FUZZ=1',*command]
        begin=time.monotonic();proc=subprocess.Popen(command,cwd=self.root,text=True,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
        timeout=False
        try:output,_=proc.communicate(timeout=600)
        except subprocess.TimeoutExpired:
            timeout=True;os.killpg(proc.pid,signal.SIGKILL);output,_=proc.communicate()
        (self.output/f'{name}.log').write_text(output)
        passed=not timeout and (proc.returncode==0 if reject is None else proc.returncode==1 and reject in output)
        self.report['steps'].append(dict(name=name,command=command,returncode=proc.returncode,
            passed=passed,seconds=time.monotonic()-begin,timed_out=timeout))
        print(name,'PASS' if passed else 'FAIL',flush=True)
        if not passed:raise RuntimeError(name+': '+output[-2500:])
        return output

    def build(self,name,top,sources,cpp,params=None):
        if shutil.disk_usage(self.output).free<10<<30:raise RuntimeError('no new build below10GiB')
        directory=self.output/name
        command=[self.verilator,'--cc','--exe','--build','-j','2','--top-module',top,
                 '--Mdir',str(directory),*(params or []),*map(str,sources),str(cpp)]
        if self.compile_lock:command=['flock','--timeout','600',str(self.compile_lock),*command]
        self.run(name,command)
        executable=directory/f'V{top}'
        self.report.setdefault('builds',[]).append(dict(name=name,top=top,
            sources={str(p.relative_to(self.root)) if p.is_relative_to(self.root) else str(p):
                     hashlib.sha256(p.read_bytes()).hexdigest() for p in [*sources,cpp]},
            parameters=params or [],executable=str(executable),
            executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest()))
        return str(executable)

    def build_ntt(self,field: int,aw: int=16,lanes: int=64) -> str:
        prime=EXPERIMENT_PRIMES[field]
        return self.build(f'build-ntt27-rootpipe-p{field+1}-aw{aw}-l{lanes}','genefer_ntt_banked27_rootpipe_engine',
            [self.root/'rtl/kernel'/n for n in ('genefer_montgomery_mul27_sparse_pipe.sv','genefer_sdp_ram32.sv','genefer_ntt_banked27_engine.sv','genefer_ntt_banked27_rootpipe_engine.sv')],
            self.root/'rtl/tb/ntt_banked27_rootpipe_engine.cpp',
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
        output=self.output/f'{name}-residues.txt';log=self.run(name,[exe,str(path),str(output)])
        phase_cycles=[int(x) for x in re.findall(r'^RUN .* cycles=(\d+)$',log,re.M)]
        if len(phase_cycles)!=5*len(cases):raise RuntimeError('missing five-phase cycle measurements')
        for index,(case,_,_) in enumerate(cases):
            measured=phase_cycles[5*index:5*index+5]
            self.report.setdefault('arithmetic_cycles_samples',[]).append(dict(
                field=field+1,aw=aw,n=n,lanes=self.lanes,case=case,
                phase_cycles=measured,cycles=sum(measured)))
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
        # Exact routing-retimed NTT27 latency, including reset in the op0 inverse-normalization
        # transition and immediately before completion; reload after every reset.
        prime=EXPERIMENT_PRIMES[field];p=prime.p;r=(1<<32)%p;n=32
        root=pow(prime.generator,(p-1)//n,p);data=[(i*7919+17)%p for i in range(n)]
        lines=['5'];transform=5*((n+2*lanes-1)//(2*lanes)+10)
        point=(n+lanes-1)//lanes+9
        def emit(cmd,a):lines.append(cmd+'\n'+' '.join(map(str,a)))
        for mode in (0,1):
            lines.append(f'ORDER {mode}')
            for op,inv in ((0,0),(0,1),(1,0),(2,0),(3,0)):
                limit=(transform if op==0 else 0)+(point if op!=0 or inv else 0)
                times=set(range(1,12))|{limit-2,limit-1}
                if op==0 and inv:times.update((transform-1,transform,transform+1,transform+2))
                for when in sorted(t for t in times if 0<t<limit):
                    emit('LOAD',[v*r%p for v in data]);emit('ROOTS',[pow(root,i,p)*r%p for i in range(n)])
                    lines.append(f'ABORT_AT {op} {inv} {r} {when}')
            for op in (1,2,3):
                emit('LOAD',[v*r%p for v in data]);emit('ROOTS',[pow(root,i,p)*r%p for i in range(n)])
                lines.append(f'RUN {op} 0 {r if op!=3 else 1}')
                expected=[v*v*r%p for v in data] if op==1 else [v*pow(root,i,p)*r%p for i,v in enumerate(data)] if op==2 else data
                emit('CHECK',expected)
        name=f'reset-ntt27-rootpipe-p{field+1}-l{lanes}';path=self.output/f'{name}.txt';path.write_text('\n'.join(lines)+'\n')
        self.run(name,[exe,str(path),str(self.output/f'{name}-dump.txt')])

    def canonical_checks(self,field,aw,exe):
        for mode in ('data','root','vector'):
            command=['env',f'NTT_NONCANON={mode}',exe,str(self.output/f'cached-squares-p{field+1}-aw{aw}.txt'),str(self.output/f'noncanon-{field}-{mode}.txt')]
            proc=subprocess.run(command,cwd=self.root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
            passed=proc.returncode!=0 and 'noncanonical NTT27' in proc.stdout
            name=f'noncanonical-p{field+1}-{mode}'
            (self.output/f'{name}.log').write_text(proc.stdout)
            self.report['steps'].append({'name':name,'passed':passed,'returncode':proc.returncode,'command':command})
            if not passed:raise RuntimeError(proc.stdout)
            print(f'noncanonical-p{field+1}-{mode}: PASS',flush=True)

    def reject_mutants(self):
        # AW10/L64 crosses both physical row and bank-half boundaries.
        records=[b for b in self.report['builds'] if b['name']==f'build-ntt27-rootpipe-p1-aw10-l{self.lanes}']
        if not records:
            fixture=self.build_ntt(0,10,self.lanes)
            self.cached_squares(0,10,fixture,cases_for(10))
            self.resets(0,fixture,self.lanes)
            records=[b for b in self.report['builds'] if b['name']==f'build-ntt27-rootpipe-p1-aw10-l{self.lanes}']
        if len(records)!=1:raise RuntimeError('missing unique completed mutation control')
        fixture=Path(records[0]['executable'])
        if hashlib.sha256(fixture.read_bytes()).hexdigest()!=records[0]['executable_sha256']:
            raise RuntimeError('mutation control executable changed')
        for name in ('cached-squares-p1-aw10.txt',f'reset-ntt27-rootpipe-p1-l{self.lanes}.txt'):
            if not (self.output/name).is_file():raise RuntimeError('missing completed control vectors')
        cases=[
            ('upper-control','control_tiles[b/TILE_BANKS].folded_root_bank_mid[d-1]',
                             'control_tiles[b/TILE_BANKS].folded_root_bank_d[d-1]'),
            ('rotation','rotation_mid<=rotation_d;', "rotation_mid<='0;"),
            ('cut-word','root_cut_q[b]<=root_xor_stages[ROOT_CUT].words[b];',
                        'root_cut_q[b]<=root_xor_stages[ROOT_CUT].words[b^1];'),
            ('data-delay','data_route_q[b]<=data_mid_q[b];','data_route_q[b]<=data_q[b];'),
            ('valid-delay','bf_route_valid<=bf_mid_valid;','bf_route_valid<=bf_in_valid;'),
            ('row-tag','row_tag[8][bank]','row_tag[7][bank]'),
            ('orientation-tag','orientation_pipe[8]','orientation_pipe[7]'),
            ('point-half-tag','point_half_pipe[8]','point_half_pipe[7]'),
            ('point-data','root_point_q[b]<=root_point_mid_q[b];','root_point_q[b]<=root_q[b];'),
            ('point-valid','mul_route_valid<=mul_mid_valid;','mul_route_valid<=mul_in_valid;'),
            ('clip-delay','stage_bit_e<=stage_bit_mid;',"stage_bit_e<=5'd0;"),
            ('pairing-delay','pairing_e<=pairing_mid;',"pairing_e<='0;"),
        ]
        engine=self.root/'rtl/kernel/genefer_ntt_banked27_rootpipe_engine.sv'
        dependencies=[self.root/'rtl/kernel'/n for n in (
            'genefer_montgomery_mul27_sparse_pipe.sv','genefer_sdp_ram32.sv','genefer_ntt_banked27_engine.sv')]
        for name,old,new in cases:
            text=engine.read_text()
            if old not in text:raise RuntimeError('missing mutation anchor '+name)
            directory=self.output/f'mutation-{name}';directory.mkdir()
            changed=directory/engine.name;changed.write_text(text.replace(old,new))
            exe=self.build(f'build-mutation-{name}','genefer_ntt_banked27_rootpipe_engine',
                [*dependencies,changed],self.root/'rtl/tb/ntt_banked27_rootpipe_engine.cpp',
                ['-GAW=10',f'-GLANES={self.lanes}','-CFLAGS',f'-O0 -DNTT_AW=10 -DNTT_LANES={self.lanes} -DNTT_P=104857601u'])
            passed=False;attempts=[]
            for suffix,vectors in [('square','cached-squares-p1-aw10.txt'),
                                   ('reset',f'reset-ntt27-rootpipe-p1-l{self.lanes}.txt')]:
                proc=subprocess.run(['env','NTT_SKIP_HOST_FUZZ=1',exe,str(self.output/vectors),str(directory/(suffix+'-dump.txt'))],
                    cwd=self.root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
                log=self.output/f'reject-mutation-{name}-{suffix}.log';log.write_text(proc.stdout)
                rejected=proc.returncode!=0 and any(s in proc.stdout for s in ('mismatch','collision','noncanonical','timeout','completion','reset'))
                attempts.append(dict(kind=suffix,rejected=rejected,returncode=proc.returncode,
                    evidence_log=str(log),evidence_sha256=hashlib.sha256(log.read_bytes()).hexdigest()))
                if rejected:
                    passed=True;break
            self.report['steps'].append(dict(name=f'reject-mutation-{name}',passed=passed,
                attempts=attempts,source_sha256=hashlib.sha256(changed.read_bytes()).hexdigest()))
            if not passed:raise RuntimeError('mutation not rejected '+name)
            print('reject-mutation-'+name,'PASS',flush=True)


def main() -> None:
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--quick',action='store_true')
    ap.add_argument('--lanes',type=int,nargs='+',choices=[1,16,64],default=[64])
    ap.add_argument('--compile-lock',type=Path)
    ap.add_argument('--mutations',action='store_true')
    args=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('Run simulation on aethia only')
    resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30));args.output.mkdir(parents=True,exist_ok=False);reports=[]
    # Reuse the previously audited conservative fingerprint, not cached results.
    # The returned empty cache object is never used for a build or oracle.
    _,toolchain,environment=cache_context(args.output/'unused-cache-record-only')
    tools_path=args.output/'toolchain.json'
    tools_path.write_text(json.dumps(dict(toolchain=toolchain,environment=environment),indent=2)+'\n')
    for lanes in args.lanes:
        lab=NTT27RootpipeLab(args.output/f'lanes{lanes}','verilator');lab.report['memory_limit_bytes']=6<<30
        lab.lanes=lanes
        lab.compile_lock=args.compile_lock.resolve() if args.compile_lock else None
        lab.report['control_replica_proof']=validate_files(lab.root)
        lab.report['bench_delta_proof']=bench_proof(lab.root)
        lab.report['toolchain_manifest']={'path':str(tools_path.resolve()),'sha256':hashlib.sha256(tools_path.read_bytes()).hexdigest()}
        lab.report['command_timeout_seconds']=600
        lab.run('structural-unit-tests',[sys.executable,'-m','unittest','tests.test_ntt27_rootpipe_structure'])
        lab.report['radix_bits']=32;lab.report['basis']=prove_basis(EXPERIMENT_PRIMES)
        lab.report['host_fuzz_policy']='Full physical host fuzz for every cached-square build; arithmetic sweeps omit only its duplicate prelude.'
        try:
            lab.report['folded_routing_proof']=prove_folded_routing()
            for lg in range(1,11 if args.quick else 17):schedule_check(lg,lanes)
            lab.report['schedule_proof']={'passed':True,'lanes':lanes,'max_lg':10 if args.quick else 16}
            for aw in ((1,4,10) if args.quick else (1,4,16)):
                cases=cases_for(aw);planes=[]
                if aw==16:cases.append(('max-base1e9',[999999999]*(1<<aw),1000000000))
                for field in range(3):
                    exe=lab.build_ntt(field,aw,lanes);planes.append(lab.cached_squares(field,aw,exe,cases))
                    if aw==4:lab.canonical_checks(field,aw,exe)
                    if aw>=5:
                        for lg in range(1,aw+1):lab.transform_test(field,lg,exe,f'-ntt27-aw{aw}')
                        lab.resets(field,exe,lanes)
                    else:lab.transform_test(field,aw,exe,f'-ntt27-aw{aw}')
                if True:
                    for i,(name,digits,base) in enumerate(cases):
                        coeff=[centered_crt((planes[f][i][j] for f in range(3)),EXPERIMENT_PRIMES) for j in range(1<<aw)]
                        m=pow(base,1<<aw)+1
                        if encode(coeff,base)%m!=pow(encode(digits,base),2,m):raise RuntimeError('ntt27 bigint square mismatch')
                        lab.report.setdefault('integer_squares',[]).append({'aw':aw,'name':name,'passed':True})
            if args.mutations and lanes==64:lab.reject_mutants()
            validate_files(lab.root)
            bench_proof(lab.root)
            if not all(s['passed'] for s in lab.report['steps']):raise RuntimeError('failed logical gate step')
            for name,expected in lab.report['source_sha256'].items():
                if hashlib.sha256((lab.root/name).read_bytes()).hexdigest()!=expected:
                    raise RuntimeError('source changed during gate: '+name)
            lab.report['status']='passed'
        except Exception:
            lab.report['status']='failed';raise
        finally:
            lab.report['evidence_sha256']={str(p.relative_to(lab.output)):hashlib.sha256(p.read_bytes()).hexdigest() for p in lab.output.iterdir() if p.suffix in ('.log','.txt')}
            (lab.output/'report.json').write_text(json.dumps(lab.report,indent=2)+'\n')
            reports.append({'lanes':lanes,'status':lab.report['status'],'report':f'lanes{lanes}/report.json'})
            complete=len(reports)==len(args.lanes) and all(r['status']=='passed' for r in reports)
            status='passed' if complete else 'failed' if any(r['status']=='failed' for r in reports) else 'running'
            (args.output/'report.json').write_text(json.dumps({'status':status,'requested_lanes':args.lanes,
                'quick':args.quick,'variants':reports},indent=2)+'\n')


if __name__=='__main__':main()
