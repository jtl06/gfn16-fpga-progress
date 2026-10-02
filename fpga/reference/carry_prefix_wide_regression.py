"""Banked four-lane bounded-transfer carry RTL checks; aethia only, two build threads."""
from pathlib import Path
import argparse
import hashlib
import itertools
import json
import random
import socket
import subprocess
import time
from .carry_fast_regression import expected
from .carry_prefix_model import normalize

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--mutations',action='store_true');ap.add_argument('--square-vectors',type=Path)
    ap.add_argument('--lanes',type=int,nargs='+',default=[4])
    args=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    root=Path(__file__).resolve().parents[1];out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    rng=random.Random(0xface1234);cases=[]
    def emit(label,a,b,mode='OK'):
        answer=expected(a,b) if mode=='OK' else []
        if mode=='OK' and normalize(a,b)[0]!=answer:raise AssertionError('prefix reference disagrees with bigint')
        cases.append((mode,label,len(a).bit_length()-1,b,a,answer))
    for b in [9,10,13]:
        for i,a in enumerate(itertools.product(range(-8,9),repeat=2)):emit(f'exhaust-b{b}-{i}',list(a),b)
    for lg in [1,2,3,4,8,16]:
        n=1<<lg
        for b in [2*n+5,2*n+6,604832956,1000000000]:
            bound=2*n*(b-1)**2
            patterns=[[bound]*n,[-bound]*n,[bound if i%2 else -bound for i in range(n)],
                      [0]*n,[-1]+[0]*(n-1),[b-1]*n,
                      [0]*(n-1)+[-1],[rng.randrange(-bound,bound+1) for _ in range(n)]]
            for k,a in enumerate(patterns):emit(f'lg{lg}-b{b}-pattern{k}',a,b)
            # Both sides of the bound must be rejected at an interior/final index.
            for sign in [-1,1]:
                a=[0]*n;a[-1]=sign*(bound+1);emit(f'bad-bound-lg{lg}-b{b}-sign{sign}',a,b,'BAD')
        for b in [2,2*n+4,1000000001]:emit(f'bad-base-lg{lg}-b{b}',[0]*n,b,'BAD')
    # Recurrent polynomial-square and double, oracle computed as whole bigint.
    for b in [37,604832956,1000000000]:
        n=16;a=[rng.randrange(b) for _ in range(n)]
        for step in range(12):
            coeff=[0]*n;double=1+(step%2)
            for i,x in enumerate(a):
                for j,y in enumerate(a):coeff[(i+j)%n]+=double*x*y*(1 if i+j<n else -1)
            emit(f'recurrent-b{b}-step{step}',coeff,b);a=expected(coeff,b)
    if args.square_vectors:
        for path in sorted(args.square_vectors.glob('square-gfn16-bit*-post.txt')):
            t=path.read_text().split();lg,b,bit=map(int,t[:3]);n=1<<lg
            a=[int(t[3+4*i+3])*(1+bit) for i in range(n)]
            emit(path.stem,a,b)
            if cases[-1][-1]!=list(map(int,t[3+4*n:])):raise AssertionError('square oracle mismatch')
    # Abort during setup, input split, wrap/drain and digit emission; reload follows.
    for when in ['1','50','98','110','120','emit']:
        emit(when,[123456]*256,604832956,'ABORT')
        emit(f'after-abort-{when}',[-123456]*256,604832956)
    vectors=out/'vectors.txt'
    with vectors.open('w') as f:
        for mode,label,lg,b,a,answer in cases:
            f.write(f'{mode} {label} {lg} {b}\n'+' '.join(map(str,a))+'\n')
            if answer:f.write(' '.join(map(str,answer))+'\n')
    dv=out/'divide-vectors.txt';records=[]
    def divrow(reset,valid,b,x,tag):
        q,r=divmod(x,b);records.append(f'{reset} {valid} {b} {(1<<96)//b} {x} {q} {r} {tag}\n')
    for b in [2,3,9,13,131077,604832956,999999999,1000000000]+[rng.randrange(2,1000000001) for _ in range(12)]:
        divrow(0,0,b,0,0)
        boundary=[0,1,-1,b-1,b,b+1,-b-1,-b,-b+1,(1<<94)-1,-((1<<94)-1)]
        for j in range(1200):
            x=boundary[j] if j<len(boundary) else rng.randrange(-(1<<94)+1,1<<94)
            divrow(int(j%293!=292),int(j%11!=10),b,x,j)
        for j in range(8):divrow(1,0,b,0,0)
    dv.write_text(''.join(records))
    src=[root/'rtl/kernel/genefer_div96_recip_prefix.sv',root/'rtl/kernel/genefer_carry_prefix_wide.sv',root/'rtl/kernel/genefer_carry_transfer_tree.sv']
    report={'host':socket.gethostname(),'status':'running','cases':len(cases),'lanes':args.lanes,'steps':[],
            'sources':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in src+[Path(__file__),root/'rtl/tb/carry_prefix_wide.cpp',root/'rtl/tb/carry_prefix_div.cpp']}}
    def run(name,cmd,reject=None):
        then=time.monotonic();p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=600)
        (out/f'{name}.log').write_text(p.stdout)
        report['steps'].append({'name':name,'returncode':p.returncode,'seconds':time.monotonic()-then,'command':cmd})
        print(name,p.returncode,p.stdout[-700:],flush=True)
        if reject is None:
            if p.returncode:raise RuntimeError(name+' failed')
        elif p.returncode==0 or not any(token in p.stdout for token in ([reject] if isinstance(reject,str) else reject)):raise RuntimeError(name+' mutant not rejected')
    def build(name,top,sources,cpp,params=[]):
        directory=out/name
        run(name,['verilator','--cc','--exe','--build','-j','2','--top-module',top,'--Mdir',str(directory),*params,*map(str,sources),str(cpp)])
        return str(directory/f'V{top}')
    try:
        exe=build('build-divider','genefer_div96_recip_prefix',src[:1],root/'rtl/tb/carry_prefix_div.cpp',['-GPAYLOAD_W=32'])
        run('test-divider',[exe,str(dv)])
        # Elaboration corner, distinct from runtime N2 with AW16 RAMs.
        tiny=out/'vectors-aw1.txt'
        with tiny.open('w') as f:
            for mode,label,lg,b,a,answer in cases:
                if lg!=1:continue
                f.write(f'{mode} {label} {lg} {b}\n'+' '.join(map(str,a))+'\n')
                if answer:f.write(' '.join(map(str,answer))+'\n')
        for lanes in args.lanes:
            exe=build(f'build-carry-w{lanes}','genefer_carry_prefix_wide',src,root/'rtl/tb/carry_prefix_wide.cpp',[f'-GLANES={lanes}'])
            run(f'test-carry-w{lanes}',[exe,str(vectors)])
            exe=build(f'build-carry-aw1-w{lanes}','genefer_carry_prefix_wide',src,root/'rtl/tb/carry_prefix_wide.cpp',['-GAW=1',f'-GLANES={lanes}'])
            run(f'test-carry-aw1-w{lanes}',[exe,str(tiny)])
        if args.mutations:
            mutations=[('wrap',"-33'(split_q[last_active-1]);","+33'(split_q[last_active-1]);",'carry mismatch'),
                       ('order','compose(suffix,a_prefix[LANES-1])','compose(a_prefix[LANES-1],suffix)',('unexpected error','carry mismatch')),
                       ('special','special<=!found_carry','special<=0','unexpected error'),
                       ('lane-prefix','lane_in[g]=b_prefix[g-1]','lane_in[g]=b_prefix[g]','carry mismatch'),
                       ('bank-write','mem_addr[g]=emit_row',"mem_addr[g]=RW'(emit_row+1)",'carry mismatch'),
                       ('output-tag','mem_addr[g]=emit_row',"mem_addr[g]=RW'(written)",'carry mismatch')]
            for name,old,new,reject in mutations:
                text=src[1].read_text()
                if text.count(old)!=1:raise RuntimeError('mutation anchor '+name)
                path=out/f'mutant-{name}.sv';path.write_text(text.replace(old,new))
                exe=build('build-mutant-'+name,'genefer_carry_prefix_wide',[src[0],src[2],path],root/'rtl/tb/carry_prefix_wide.cpp')
                run('reject-'+name,[exe,str(vectors)],reject)
            text=src[2].read_text()
            old='compose(level[s-1].value[i-(1<<(s-1))],level[s-1].value[i])'
            if text.count(old)!=1:raise RuntimeError('tree mutation anchor')
            path=out/'mutant-tree.sv';path.write_text(text.replace(old,'compose(level[s-1].value[i],level[s-1].value[i-(1<<(s-1))])'))
            exe=build('build-mutant-tree','genefer_carry_prefix_wide',[src[0],src[1],path],root/'rtl/tb/carry_prefix_wide.cpp')
            run('reject-tree',[exe,str(vectors)],('carry mismatch','unexpected error'))
            for name,old,new in [
                    ('divide-floor',"-(unsigned_r!=0 ? 96'sd1 : 96'sd0)",''),
                    ('divide-correction','provisional_r>=base','provisional_r>base'),
                    ('divide-payload','assign payload_out=payloads[6]','assign payload_out=payloads[5]')]:
                text=src[0].read_text()
                if old not in text:raise RuntimeError('divider mutation anchor '+name)
                path=out/f'mutant-{name}.sv';path.write_text(text.replace(old,new))
                exe=build('build-mutant-'+name,'genefer_div96_recip_prefix',[path],root/'rtl/tb/carry_prefix_div.cpp',['-GPAYLOAD_W=32'])
                run('reject-'+name,[exe,str(dv)],'divider arithmetic/payload mismatch')
        report['status']='passed'
    except BaseException as exc:
        report['status']='failed';report['error']=repr(exc);raise
    finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
