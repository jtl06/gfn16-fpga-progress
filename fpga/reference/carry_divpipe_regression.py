"""Exact retimed divider and streamed carry gate; aethia only, two workers."""
from pathlib import Path
import argparse, hashlib, json, random, resource, socket, subprocess, time

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--vectors',type=Path,required=True);ap.add_argument('--tiny-vectors',type=Path,required=True)
    ap.add_argument('--lanes',nargs='+',type=int,default=[4,16]);ap.add_argument('--mutations',action='store_true')
    a=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30))
    root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    helper=root/'rtl/kernel/genefer_div_recip_narrow_pipe.sv'
    top='genefer_carry_prefix_stream_divpipe';src=root/f'rtl/kernel/{top}.sv'
    cpp=root/'rtl/tb/carry_prefix_stream_divpipe.cpp';div_cpp=root/'rtl/tb/carry_div_narrow_pipe.cpp'
    size_cpp=root/'rtl/tb/carry_stream_divpipe_size.cpp'
    # The frozen file contributes only its unchanged scan-helper definition.
    shared=[helper,root/'rtl/kernel/genefer_sp_ram.sv',root/'rtl/kernel/genefer_carry_prefix_stream_pipe.sv']
    files=shared+[src,cpp,div_cpp,size_cpp,Path(__file__),a.vectors,a.tiny_vectors]
    report={'status':'running','host':socket.gethostname(),'steps':[],
            'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    # Keep the frozen oracle vectors intact and add cancellation at every
    # newly retimed stage plus immediately before the final RAM commit.
    vectors={}
    b=604832956;bound=4*(b-1)**2
    extra=''
    for when in list(map(str,range(98,127)))+['last']:
        extra+=f'ABORT {when} 1 {b}\n{bound-1} {-bound+1}\n'
        extra+=f'OK after-new-stage-{when} 1 97\n-1 0\n-1 0\n'
    for aw,original in ((16,a.vectors),(1,a.tiny_vectors)):
        path=out/f'carry-vectors-aw{aw}.txt';path.write_text(original.read_text()+extra);vectors[aw]=path
    report['carry_vectors']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in vectors.values()}
    def run(name,cmd,reject=None):
        t=time.monotonic();r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=600)
        (out/f'{name}.log').write_text(r.stdout)
        passed=r.returncode==0 if reject is None else r.returncode!=0 and any(s in r.stdout for s in reject)
        report['steps'].append({'name':name,'passed':passed,'returncode':r.returncode,'seconds':time.monotonic()-t,'command':cmd})
        print(name, 'PASS' if passed else 'FAIL',r.stdout[-600:],flush=True)
        if not passed:raise RuntimeError(name+' failed')
    def build(name,module,rtl,bench,params,flags):
        directory=out/name
        run(name,['verilator','--cc','--exe','--build','-j','2','--top-module',module,'--Mdir',str(directory),
                  *params,'-CFLAGS',flags,*map(str,rtl),str(bench)])
        return str(directory/f'V{module}')
    def divider_build(name,width,source=helper):
        return build(name,'genefer_div_recip_narrow_pipe',[source],div_cpp,
                     [f'-GMAG_W={width}','-GPAYLOAD_W=32'],f'-DTEST_MAG_W={width}')
    def carry_build(name,w,aw,source=src,bench=cpp):
        return build(name,top,shared+[source],bench,[f'-GLANES={w}',f'-GAW={aw}'],f'-DTEST_LANES={w} -DTEST_AW={aw}')
    rng=random.Random(0xd1a1de10);div_vectors={};derived=[]
    for lg in range(1,17):
        n=1<<lg
        for b in (2*n+5,2*n+6,604832956,1000000000):
            bound=2*n*(b-1)**2
            assert bound<1<<77 and (bound+b-1)//b==2*n*(b-2)+1<1<<47
            for x in [0,bound,-bound,bound-1,-bound+1]+[rng.randrange(-bound,bound+1) for _ in range(50)]:
                q,r=divmod(x,b);assert abs(q)<1<<47;derived.append((b,q))
    for width in (77,47):
        m=(1<<width)-1;records=[];tag=0
        def row(reset,valid,b,x):
            nonlocal tag
            assert abs(x)<1<<width
            q,r=divmod(x,b);records.append(f'{reset} {valid} {b} {(1<<96)//b} {x} {q} {r} {tag}\n');tag+=1
        bases=[2,3,7,9,37,131077,604832956,999999999,1000000000]+[rng.randrange(2,1000000001) for _ in range(16)]
        row(0,0,bases[0],0)
        for b in bases:
            # Change base after a complete drain, deliberately without reset.
            edges=[0,1,-1,b-1,b,b+1,-b-1,-b,-b+1,m,-m]
            for multiple in (m//b*b,(m//b-1)*b):
                edges.extend(sign*(multiple+d) for sign in (-1,1) for d in (-1,0,1) if abs(multiple+d)<=m)
            for bit in (16,17,31,32,46,47,63,64,76):
                edges.extend(sign*((1<<bit)+d) for sign in (-1,1) for d in (-1,0,1) if 0<=(1<<bit)+d<=m)
            for j in range(2200):
                x=edges[j] if j<len(edges) else rng.randrange(-m,m+1)
                row(int(j%293!=292),int(j%11!=10),b,x)
            for j in range(11):row(1,0,b,0)
            # Reset after each possible in-flight pipeline age, then drain.
            for age in range(10):
                row(1,1,b,edges[age])
                for j in range(age):row(1,0,b,0)
                row(0,0,b,0)
                for j in range(11):row(1,0,b,0)
        if width==47:
            for b,q in derived:
                row(1,1,b,q)
                for j in range(11):row(1,0,b,0)
        path=out/f'divide-{width}.txt';path.write_text(''.join(records));div_vectors[width]=path
    report['derived_first_quotients']=len(derived)
    report['divider_vectors']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in div_vectors.values()}
    try:
        for width in (77,47):
            exe=divider_build(f'build-divider-{width}',width)
            run(f'test-divider-{width}',[exe,str(div_vectors[width])])
            for label,b,x,message in [('magnitude',2,-(1<<width),'outside magnitude contract'),
                ('base-zero',0,0,'base outside contract'),('base-one',1,0,'base outside contract'),
                ('base-large',1000000001,0,'base outside contract')]:
                path=out/f'bad-{label}-{width}.txt';recip=(1<<96)//b if b>=2 else 0
                path.write_text(f'0 0 {b} {recip} 0 0 0 0\n1 1 {b} {recip} {x} 0 0 1\n')
                run(f'reject-input-{label}-{width}',[exe,str(path)],[message])
        for w in a.lanes:
            for aw,v in vectors.items():
                name=f'w{w}-aw{aw}';exe=carry_build('build-'+name,w,aw);run('test-'+name,[exe,str(v)])
        exe=carry_build('build-size-aw17',4,17,bench=size_cpp);run('test-size-aw17',[exe])
        if a.mutations:
            defects=[
                ('floor',"quotient<=signed_q-$signed((MAG_W+1)'(negative_fraction));",'quotient<=signed_q;'),
                ('correction','correction<=provisional_r>=base;','correction<=provisional_r>base;'),
                ('low-tag','provisional_r<=lows[4]-residue_product;','provisional_r<=lows[3]-residue_product;'),
                ('estimate-tag',"unsigned_q<=estimate_f+MAG_W'(correction);","unsigned_q<=estimate_e+MAG_W'(correction);"),
                ('sign-tag','negative[7]','negative[6]'),
                ('remainder-tag','remainder<=signed_r;','remainder<=unsigned_r;'),
                ('valid','out_valid=valid[9]','out_valid=valid[8]'),
                ('payload','payload_out=payloads[9]','payload_out=payloads[8]'),
                ('reset','if(!rst_n)valid<=0;','if(!rst_n)valid<=1;'),
                ('high-product','wire [LW-1:0] digit=magnitude[a*32+:LW];',"wire [LW-1:0] digit=(a==LIMBS-1) ? LW'(0) : magnitude[a*32+:LW];")]
            for width in (77,47):
                for name,old,new in defects:
                    text=helper.read_text()
                    if old not in text:raise RuntimeError('divider mutation anchor '+name)
                    path=out/f'mutant-{name}-{width}.sv';path.write_text(text.replace(old,new))
                    exe=divider_build(f'build-mutant-{name}-{width}',width,path)
                    run(f'reject-{name}-{width}',[exe,str(div_vectors[width])],['divider valid mismatch','divider arithmetic/payload mismatch'])
            defects=[
                ('bound',"if(active_mask[g] && (stream_word[g]<-$signed(bound) || stream_word[g]>$signed(bound)))","if(1'b0)"),
                ('row-valid','stream_fire && stream_ok && active_mask[g]','stream_ready && stream_ok && active_mask[g]'),
                ('quotient-remainder-tag','.payload_in(first_r[g])','.payload_in(first_r[(g+1)%LANES])'),
                ('stream-sign','.value(stream_word[g][77:0])',".value({1'b0,stream_word[g][76:0]})")]
            for name,old,new in defects:
                text=src.read_text()
                if text.count(old)!=1:raise RuntimeError('carry mutation anchor '+name)
                path=out/f'mutant-carry-{name}.sv';path.write_text(text.replace(old,new))
                exe=carry_build('build-mutant-carry-'+name,4,16,path)
                run('reject-carry-'+name,[exe,str(vectors[16])],['mismatch','regression','unexpected error','rejection missing','wide split','outside signed','outside magnitude'])
        report['status']='passed'
    except BaseException as exc:report['status']='failed';report['error']=repr(exc);raise
    finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
