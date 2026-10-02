"""Pipelined bound setup without additional carry clocks; aethia only."""
from pathlib import Path
import argparse,hashlib,json,socket,subprocess,time

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--vectors',type=Path,required=True);ap.add_argument('--tiny-vectors',type=Path,required=True)
    ap.add_argument('--mutations',action='store_true');a=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    shared=[root/'rtl/kernel'/s for s in ['genefer_div_recip_narrow.sv','genefer_carry_transfer_tree.sv','genefer_sp_ram.sv']]
    tops={k:root/f'rtl/kernel/genefer_carry_prefix_{k}_pipe_v2.sv' for k in ['wide','vector']}
    cpp={k:root/f'rtl/tb/carry_prefix_{k}_pipe_v2.cpp' for k in tops}
    size_cpp=root/'rtl/tb/carry_pipe_v2_size.cpp'
    files=shared+list(tops.values())+list(cpp.values())+[size_cpp,Path(__file__),a.vectors,a.tiny_vectors]
    report={'status':'running','host':socket.gethostname(),'steps':[],
            'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    vectors=out/'vectors.txt';tiny=out/'vectors-aw1.txt'
    vectors.write_text(a.vectors.read_text());tiny.write_text(a.tiny_vectors.read_text())
    with vectors.open('a') as f:
        for elapsed,b in [(2,37),(3,604832956),(4,1000000000)]:
            f.write(f'ABORT {elapsed} 8 604832956\n'+' '.join(['0']*256)+'\n')
            n=16;bound=2*n*(b-1)**2;coeff=[bound if i%2 else -bound for i in range(n)]
            modulus=b**n+1;value=sum(x*b**i for i,x in enumerate(coeff))%modulus
            if value==modulus-1:answer=[-1]+[0]*(n-1)
            else:
                answer=[]
                for _ in range(n):answer.append(value%b);value//=b
                assert value==0
            f.write(f'OK after-bound-stage-{elapsed}-base{b} 4 {b}\n'+' '.join(map(str,coeff))+'\n'+' '.join(map(str,answer))+'\n')
    report['generated_vectors']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [vectors,tiny]}
    def run(name,cmd,reject=None):
        then=time.monotonic();r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=600)
        (out/f'{name}.log').write_text(r.stdout);report['steps'].append({'name':name,'returncode':r.returncode,'seconds':time.monotonic()-then,'command':cmd})
        print(name,r.returncode,r.stdout[-650:],flush=True)
        if reject is None and r.returncode:raise RuntimeError(name+' failed')
        if reject is not None and (r.returncode==0 or not any(t in r.stdout for t in reject)):raise RuntimeError(name+' mutant not rejected')
    def build(name,kind,lanes,aw,source=None,bench=None):
        top=f'genefer_carry_prefix_{kind}_pipe_v2';directory=out/name
        run(name,['verilator','--cc','--exe','--build','-j','2','--top-module',top,'--Mdir',str(directory),
                  f'-GLANES={lanes}',f'-GAW={aw}','-CFLAGS',f'-DTEST_LANES={lanes} -DTEST_AW={aw}',*map(str,shared+[source or tops[kind]]),str(bench or cpp[kind])])
        return str(directory/f'V{top}')
    try:
        for kind,lanes_set in [('wide',[4,8,16]),('vector',[4,16])]:
            for lanes in lanes_set:
                for aw,v in [(16,vectors),(1,tiny)]:
                    name=f'{kind}-w{lanes}-aw{aw}';exe=build('build-'+name,kind,lanes,aw);run('test-'+name,[exe,str(v)])
        exe=build('build-size-aw17','wide',4,17,bench=size_cpp);run('test-size-aw17',[exe])
        if a.mutations:
            defects=[
                ('stale-base',"bound_base_minus1<=base-32'd1","bound_base_minus1<=base_reg-32'd1"),
                ('missing-cross','bound_cross<=bound_base_minus1[15:0]*bound_base_minus1[31:16]',"bound_cross<=32'd0"),
                ('missing-high','bound_hi_sq<=bound_base_minus1[31:16]*bound_base_minus1[31:16]',"bound_hi_sq<=32'd0"),
                ('early-bound','if(reciprocal_round==1)begin','if(reciprocal_round==0)begin'),
                ('not-ready','bound_valid<=1;','bound_valid<=0;')]
            for name,old,new in defects:
                text=tops['wide'].read_text()
                if text.count(old)!=1:raise RuntimeError('mutation anchor '+name)
                path=out/f'mutant-{name}.sv';path.write_text(text.replace(old,new))
                exe=build('build-mutant-'+name,'wide',4,16,path)
                run('reject-'+name,[exe,str(vectors)],['bound setup value mismatch','bound not ready before SPLIT','unexpected error','carry mismatch','carry cycle regression'])
        report['status']='passed'
    except BaseException as exc:report['status']='failed';report['error']=repr(exc);raise
    finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
