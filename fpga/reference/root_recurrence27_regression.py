"""Standalone root-vector RTL versus frozen bank-layout root demands."""
from pathlib import Path
import argparse,hashlib,json,socket,subprocess,time
from .root_recurrence_proof import FIELDS,R,MAX_LG,check_geometry,powers,period

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--lanes',type=int,nargs='+',default=[16,64]);ap.add_argument('--mutations',action='store_true')
    ap.add_argument('--quick',action='store_true');a=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    top='genefer_root_recurrence27';src=root/f'rtl/kernel/{top}.sv';helper=root/'rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv'
    cpp=root/'rtl/tb/root_recurrence27.cpp';proof=root/'reference/root_recurrence_proof.py'
    files=[src,helper,cpp,proof,Path(__file__)]
    report={'status':'running','host':socket.gethostname(),'steps':[],
            'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'vectors':[]}
    def run(name,cmd,reject=False):
        then=time.monotonic();r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=900)
        (out/f'{name}.log').write_text(r.stdout);report['steps'].append({'name':name,'returncode':r.returncode,'seconds':time.monotonic()-then,'command':cmd})
        print(name,r.returncode,r.stdout[-650:],flush=True)
        if not reject and r.returncode:raise RuntimeError(name+' failed')
        if reject and (r.returncode==0 or not any(t in r.stdout for t in ['mismatch','backpressure','unexpected root recurrence stall','noncanonical','stale seed reset acceptance','config rejection missing'])):
            raise RuntimeError(name+' mutant not rejected')
    def build(name,w,p,source=src):
        directory=out/name
        run(name,['verilator','--cc','--exe','--build','-j','2','--top-module',top,'--Mdir',str(directory),
                  f'-GLANES={w}',f'-GP={p}',f'-GQ={pow(p,-1,R)}','-GTAG_W=32',
                  '-CFLAGS',f'-DTEST_LANES={w} -DTEST_P={p}u',str(helper),str(source),str(cpp)])
        return str(directory/f'V{top}')
    vectors={}
    try:
        for w in a.lanes:
            k=w.bit_length();geometry={lg:check_geometry(lg,w) for lg in ([1,4,8,16] if a.quick else range(1,17))}
            for p,generator in FIELDS[:1] if a.quick else FIELDS:
                path=out/f'vectors-l{w}-p{p}.txt';count=0;words=0
                with path.open('w') as f:
                    def emit(name,rows,active,t,step):
                        nonlocal count,words
                        contexts=min(4,t if t else len(rows),len(rows));seeds=[x for row in rows[:contexts] for x in row]
                        f.write(f'CASE {name} {len(rows)} {active} {t} {step} {contexts}\n')
                        f.write(' '.join(map(str,seeds))+'\n')
                        for row in rows:f.write(' '.join(map(str,row))+'\n')
                        count+=1;words+=len(rows)*active
                    for lg,(stages,point,_) in geometry.items():
                        n=1<<lg;mont=R%p;psi=pow(generator,(p-1)//(2*n),p);omega=psi*psi%p
                        for inv in [False,True]:
                            alpha=pow(omega,-1,p) if inv else omega;table=[x*mont%p for x in powers(alpha,n//2,p)]
                            for s,demand in enumerate(stages):
                                active=min(w,1<<s);t=period(s,k);shift=lg-1-s
                                step=mont if t<=4 else pow(alpha,1<<(k+shift+1),p)*mont%p
                                rows=[]
                                for indices,exponents in demand:
                                    row=[None]*active
                                    for j,e in zip(indices,exponents):
                                        if row[j] is not None:assert row[j]==table[e]
                                        row[j]=table[e]
                                    assert all(x is not None for x in row);rows.append(row)
                                emit(f'lg{lg}-inv{int(inv)}-stage{s}',rows,active,t,step)
                        for post in [False,True]:
                            alpha=pow(psi,-1,p) if post else psi;scale=pow(n,-1,p) if post else mont
                            table=[x*scale%p for x in powers(alpha,n,p)];rows=[];active=min(w,n)
                            for indices,addresses in point:
                                row=[None]*active
                                for j,address in zip(indices,addresses):row[j]=table[address]
                                assert all(x is not None for x in row);rows.append(row)
                            emit(f'lg{lg}-post{int(post)}',rows,active,0,pow(alpha,4*w,p)*mont%p)
                vectors[w,p]=path;report['vectors'].append({'path':str(path),'cases':count,'root_words':words,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
                exe=build(f'build-l{w}-p{p}',w,p);run(f'test-l{w}-p{p}',[exe,str(path)])
        if a.mutations:
            w=16;p=FIELDS[0][0];path=vectors[w,p]
            defects=[
                ('bypass','bypass ? update_result[j]',"1'b0 ? update_result[j]"),
                ('context-tag','context_pipe[3]==context_id','context_pipe[2]==context_id'),
                ('wrap-contexts','assign use_seed=position<4;',"assign use_seed=position==0 || issued<4;"),
                ('no-wrap','assign use_seed=position<4;','assign use_seed=issued<4;'),
                ('valid','assign fire=request_valid && request_ready;','assign fire=request_ready;'),
                ('active-write','(!busy || seed_bank!=active_bank)',"1'b1"),
                ('seed-width','seed_data<P',"32'(seed_data[26:0])<P"),
                ('drain','drain_left<=4','drain_left<=3'),
                ('tag','root_tag<=request_tag','root_tag<=request_tag+1'),
                ('reset-seeds','seed_valid[0][c]<=0;seed_valid[1][c]<=0;','seed_valid[0][c]<=seed_valid[0][c];seed_valid[1][c]<=seed_valid[1][c];')]
            for name,old,new in defects:
                text=src.read_text()
                if text.count(old)!=1:raise RuntimeError('mutation anchor '+name)
                mutant=out/f'mutant-{name}.sv';mutant.write_text(text.replace(old,new))
                exe=build('build-mutant-'+name,w,p,mutant);run('reject-'+name,[exe,str(path)],True)
        report['status']='passed'
    except BaseException as exc:report['status']='failed';report['error']=repr(exc);raise
    finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
