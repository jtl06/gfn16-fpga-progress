"""Standalone27-bit Montgomery pipeline test; no NTT/CRT/core changes."""
from pathlib import Path
import argparse,hashlib,json,random,socket,subprocess,time

FIELDS=[(104857601,4190109697),(69206017,4225761281),(67239937,4227727361)]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--mutations',action='store_true');a=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    rtl=root/'rtl/kernel/genefer_montgomery_mul27_pipe.sv';cpp=root/'rtl/tb/montgomery27_pipe.cpp'
    rng=random.Random(0x27a11ce);vectors={};branches={}
    for p,q in FIELDS:
        assert 3<=p<1<<27 and p%2 and (p*q)%(1<<32)==1
        rinv=pow(1<<32,-1,p);rows=[];branch=[0,0]
        def emit(reset,valid,lhs,rhs):
            value=lhs*rhs*rinv%p
            if reset and valid:
                assert lhs<p and rhs<p
                ab=lhs*rhs;m=(ab*q)&0xffffffff
                branch[int((ab>>32)<((m*p)>>32))]+=1
            rows.append(f'{reset} {valid} {lhs} {rhs} {value}\n')
        emit(0,1,0xffffffff,0xffffffff)
        edges=sorted({0,1,2,p//2-1,p//2,p//2+1,p-3,p-2,p-1,(1<<26)-1,1<<26,(1<<26)+1,(1<<32)%p})
        for x in edges:
            for y in edges:emit(1,1,x,y)
        for j in range(30000):
            reset=j%251!=250;valid=j%7!=6
            x,y=(rng.randrange(p),rng.randrange(p)) if reset and valid else (rng.randrange(1<<32),rng.randrange(1<<32))
            emit(int(reset),int(valid),x,y)
        # Every pipeline occupancy is canceled independently; then refill.
        for depth in range(1,5):
            for j in range(depth):emit(1,1,p-1-j,p-2-j)
            emit(0,1,0xffffffff,0xffffffff)
            for j in range(8):emit(1,1,rng.randrange(p),rng.randrange(p))
        for j in range(8):emit(1,0,0xffffffff,0xffffffff)
        path=out/f'vectors-{p}.txt';path.write_text(''.join(rows));vectors[p]=path;branches[str(p)]=branch
        assert min(branch)>0
    report={'status':'running','host':socket.gethostname(),'steps':[],'branch_accepts_noadd_add':branches,
            'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [rtl,cpp,Path(__file__),*vectors.values()]}}
    def run(name,cmd,reject=None):
        then=time.monotonic();r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=600)
        (out/f'{name}.log').write_text(r.stdout);report['steps'].append({'name':name,'returncode':r.returncode,'seconds':time.monotonic()-then,'command':cmd})
        print(name,r.returncode,r.stdout[-650:],flush=True)
        if reject is None and r.returncode:raise RuntimeError(name+' failed')
        if reject is not None and (r.returncode==0 or not any(t in r.stdout for t in reject)):raise RuntimeError(name+' not rejected as expected')
    def build(name,p,q,source=rtl):
        directory=out/name
        run(name,['verilator','--cc','--exe','--build','-j','2','--top-module','genefer_montgomery_mul27_pipe',
                  '--Mdir',str(directory),f'-GP={p}',f'-GQ={q}',str(source),str(cpp)])
        return str(directory/'Vgenefer_montgomery_mul27_pipe')
    try:
        for p,q in FIELDS:
            exe=build(f'build-{p}',p,q);run(f'test-{p}',[exe,str(vectors[p]),str(p)])
            for name,x,y in [('lhs-P',p,1),('rhs-P',1,p),('wide-lhs',1<<27,1),('wide-rhs',1,0xffffffff)]:
                run(f'reject-{name}-{p}',[exe,'reject',str(p),str(x),str(y)],['noncanonical Montgomery27 input'])
        for name,p,q in [('large-modulus',134217729,4160749569),('bad-inverse',FIELDS[0][0],FIELDS[0][1]^2)]:
            exe=build('build-'+name,p,q)
            run('reject-'+name,[exe,'reject',str(p)],['invalid27-bit Montgomery modulus','invalid positive Montgomery inverse'])
        if a.mutations:
            defects=[
                ('variable-high-bit','lhs[26:0]',"{1'b0,lhs[25:0]}"),
                ('reduction','m_s2<=ab_s1[31:0]*Q;',"m_s2<=(ab_s1[31:0]*Q)^32'd1;"),
                ('correction','hi_s3>=mp_hi','hi_s3>mp_hi'),
                ('negative','hi_s3+P-mp_hi','hi_s3-mp_hi'),
                ('latency','out_valid<=valid_pipe[2]','out_valid<=valid_pipe[1]'),
                ('reset',"valid_pipe<='0","valid_pipe<='1"),
                ('hold','if(valid_pipe[2])begin',"if(!valid_pipe[2])result<=32'hdeadbeef;\n            if(valid_pipe[2])begin")]
            for p,q in FIELDS:
                for name,old,new in defects:
                    text=rtl.read_text()
                    if text.count(old)!=1:raise RuntimeError('mutation anchor '+name)
                    path=out/f'mutant-{name}-{p}.sv';path.write_text(text.replace(old,new))
                    exe=build(f'build-mutant-{name}-{p}',p,q,path)
                    run(f'reject-mutant-{name}-{p}',[exe,str(vectors[p]),str(p)],['Montgomery arithmetic mismatch','valid/latency mismatch','invalid-cycle result hold mismatch'])
                text=rtl.read_text();old='$fatal(1,"noncanonical Montgomery27 input");'
                assert text.count(old)==1
                path=out/f'mutant-input-assert-{p}.sv';path.write_text(text.replace(old,';'))
                exe=build(f'build-mutant-input-assert-{p}',p,q,path)
                run(f'reject-mutant-input-assert-{p}',[exe,'reject',str(p)],['invalid input assertion missing'])
        report['status']='passed'
    except BaseException as exc:report['status']='failed';report['error']=repr(exc);raise
    finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
