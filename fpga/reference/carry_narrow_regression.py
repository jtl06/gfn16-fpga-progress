"""Exact width-specialized divider and carry checks; aethia only."""
from pathlib import Path
import argparse
import hashlib
import json
import random
import socket
import subprocess
import time

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--vectors',type=Path,required=True)
    ap.add_argument('--tiny-vectors',type=Path,required=True)
    ap.add_argument('--mutations',action='store_true')
    args=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    root=Path(__file__).resolve().parents[1];out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    helper=root/'rtl/kernel/genefer_div_recip_narrow.sv'
    shared=[helper,root/'rtl/kernel/genefer_carry_transfer_tree.sv',root/'rtl/kernel/genefer_sp_ram.sv']
    tops={kind:root/f'rtl/kernel/genefer_carry_prefix_{kind}_narrow.sv' for kind in ['wide','vector']}
    cpp={kind:root/f'rtl/tb/carry_prefix_{kind}_narrow.cpp' for kind in tops}
    div_cpp=root/'rtl/tb/carry_div_narrow.cpp'
    size_cpp=root/'rtl/tb/carry_narrow_size.cpp'
    files=shared+list(tops.values())+list(cpp.values())+[div_cpp,size_cpp,Path(__file__),args.vectors,args.tiny_vectors]
    report={'host':socket.gethostname(),'status':'running','steps':[],
            'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    rng=random.Random(0x4777abcd);derived=[]
    for lg in range(1,17):
        n=1<<lg;k=2*n
        for b in [k+5,k+6,604832956,1000000000]:
            bound=k*(b-1)**2
            assert bound<1<<77 and (bound+b-1)//b==k*(b-2)+1<1<<47
            for a in [bound,-bound,bound-1,-bound+1,0]+[rng.randrange(-bound,bound+1) for _ in range(50)]:
                q,r=divmod(a,b);assert abs(q)<1<<47
                derived.append((b,q))
    div_vectors={}
    for width in [77,47]:
        m=(1<<width)-1;records=[]
        def row(reset,valid,b,x,tag):
            assert abs(x)<1<<width
            q,r=divmod(x,b);records.append(f'{reset} {valid} {b} {(1<<96)//b} {x} {q} {r} {tag}\n')
        for b in [2,3,7,9,37,131077,604832956,999999999,1000000000]+[rng.randrange(2,1000000001) for _ in range(16)]:
            row(0,0,b,0,0)
            edges=[0,1,-1,b-1,b,b+1,-b-1,-b,-b+1,m,-m]
            for multiple in [m//b*b,(m//b-1)*b]:
                edges.extend(sign*(multiple+d) for sign in [-1,1] for d in [-1,0,1] if abs(multiple+d)<=m)
            for bit in [31,32,46,47,63,64,76]:
                edges.extend(sign*((1<<bit)+d) for sign in [-1,1] for d in [-1,0,1] if 0<=(1<<bit)+d<=m)
            for j in range(2200):
                x=edges[j] if j<len(edges) else rng.randrange(-m,m+1)
                row(int(j%293!=292),int(j%11!=10),b,x,j)
            for j in range(8):row(1,0,b,0,0)
        if width==47:
            # Exact first-quotient boundary samples, reset between base changes.
            for tag,(b,q) in enumerate(derived):
                row(0,0,b,0,0);row(1,1,b,q,tag)
                for j in range(8):row(1,0,b,0,0)
        path=out/f'divide-{width}.txt';path.write_text(''.join(records));div_vectors[width]=path
    vectors=out/'vectors.txt';tiny=out/'vectors-aw1.txt'
    vectors.write_text(args.vectors.read_text());tiny.write_text(args.tiny_vectors.read_text())
    for lg in [1,4,16]:
        n=1<<lg
        for magnitude in [1<<77,(1<<94)-1]:
            for sign in [-1,1]:
                for position in [0,n-1]:
                    a=[0]*n;a[position]=sign*magnitude
                    text=f'BAD narrow-reject-lg{lg}-m{magnitude}-s{sign}-p{position} {lg} 1000000000\n'+' '.join(map(str,a))+'\n'
                    with vectors.open('a') as f:f.write(text)
                    if lg==1:
                        with tiny.open('a') as f:f.write(text)
    report['derived_first_quotients']=len(derived)
    report['generated_vectors']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in list(div_vectors.values())+[vectors,tiny]}
    def run(name,cmd,reject=None):
        then=time.monotonic();p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=600)
        (out/f'{name}.log').write_text(p.stdout)
        report['steps'].append({'name':name,'returncode':p.returncode,'seconds':time.monotonic()-then,'command':cmd})
        print(name,p.returncode,p.stdout[-700:],flush=True)
        if reject is None and p.returncode:raise RuntimeError(name+' failed')
        if reject is not None and (p.returncode==0 or not any(s in p.stdout for s in reject)):raise RuntimeError(name+' mutant not rejected correctly')
    def build(name,top,sources,bench,params,flags=''):
        directory=out/name
        run(name,['verilator','--cc','--exe','--build','-j','2','--top-module',top,'--Mdir',str(directory),
                  *params,*(['-CFLAGS',flags] if flags else []),*map(str,sources),str(bench)])
        return str(directory/f'V{top}')
    try:
        for width in [77,47]:
            exe=build(f'build-divider-{width}','genefer_div_recip_narrow',[helper],div_cpp,[f'-GMAG_W={width}','-GPAYLOAD_W=32'],f'-DTEST_MAG_W={width}')
            run(f'test-divider-{width}',[exe,str(div_vectors[width])])
        for kind,lanes_set in [('wide',[4,8,16]),('vector',[4,16])]:
            for lanes in lanes_set:
                for aw,v in [(16,vectors),(1,tiny)]:
                    top=f'genefer_carry_prefix_{kind}_narrow';name=f'{kind}-w{lanes}-aw{aw}'
                    exe=build('build-'+name,top,shared+[tops[kind]],cpp[kind],[f'-GLANES={lanes}',f'-GAW={aw}'],f'-DTEST_LANES={lanes} -DTEST_AW={aw}')
                    run('test-'+name,[exe,str(v)])
        exe=build('build-size-aw17','genefer_carry_prefix_wide_narrow',shared+[tops['wide']],size_cpp,['-GAW=17','-GLANES=4'])
        run('test-size-aw17',[exe])
        if args.mutations:
            for width in [77,47]:
                for name,old,new in [
                    ('floor',"-$signed((MAG_W+1)'(unsigned_r!=0))",''),
                    ('correction','provisional_r>=base','provisional_r>base'),
                    ('payload','payload_out=payloads[6]','payload_out=payloads[5]'),
                    ('high-product','wire [LW-1:0] digit=magnitude[a*32+:LW];',"wire [LW-1:0] digit=(a==LIMBS-1) ? LW'(0) : magnitude[a*32+:LW];")]:
                    text=helper.read_text()
                    if old not in text:raise RuntimeError('mutation anchor '+name)
                    path=out/f'mutant-{name}-{width}.sv';path.write_text(text.replace(old,new))
                    exe=build(f'build-mutant-{name}-{width}','genefer_div_recip_narrow',[path],div_cpp,[f'-GMAG_W={width}','-GPAYLOAD_W=32'],f'-DTEST_MAG_W={width}')
                    run(f'reject-{name}-{width}',[exe,str(div_vectors[width])],['divider arithmetic/payload mismatch'])
            text=tops['wide'].read_text();old=' && coefficient_in_range)'
            if text.count(old)!=1:raise RuntimeError('input bound mutation anchor')
            path=out/'mutant-bound-gate.sv';path.write_text(text.replace(old,')'))
            exe=build('build-mutant-bound-gate','genefer_carry_prefix_wide_narrow',shared+[path],cpp['wide'],['-GLANES=4'])
            run('reject-bound-gate',[exe,str(vectors)],['narrow divider input outside magnitude contract'])
            text=tops['wide'].read_text();old='size_log2>16 || '
            if text.count(old)!=1:raise RuntimeError('size bound mutation anchor')
            path=out/'mutant-size.sv';path.write_text(text.replace(old,''))
            exe=build('build-mutant-size','genefer_carry_prefix_wide_narrow',shared+[path],size_cpp,['-GAW=17','-GLANES=4'])
            run('reject-size',[exe],['size rejection failed'])
        report['status']='passed'
    except BaseException as exc:
        report['status']='failed';report['error']=repr(exc);raise
    finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
