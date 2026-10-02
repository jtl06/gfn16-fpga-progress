"""Independent whole-integer modulo oracle for the two-bit CRT reducer."""
from pathlib import Path
import argparse,hashlib,json,random,socket,subprocess,time


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--mutations',action='store_true');args=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    root=Path(__file__).resolve().parents[1];out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    rtl=root/'rtl/kernel/genefer_mod27_pair_pipe.sv';cpp=root/'rtl/tb/mod27_pair_pipe.cpp'
    report={'status':'running','host':socket.gethostname(),'steps':[],
            'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (rtl,cpp,Path(__file__))}}
    def run(name,cmd,reject=False):
        then=time.monotonic();r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=600)
        (out/f'{name}.log').write_text(r.stdout)
        passed=(r.returncode==0 if not reject else r.returncode!=0 and any(s in r.stdout for s in
            ('mod27 latency/reset mismatch','mod27 arithmetic/payload mismatch','mod27 pair remainder bound')))
        report['steps'].append({'name':name,'command':cmd,'returncode':r.returncode,'passed':passed,'seconds':time.monotonic()-then})
        print(name,'PASS' if passed else 'FAIL',r.stdout[-450:],flush=True)
        if not passed:raise RuntimeError(name)
    def build(name,width,p,source=rtl):
        directory=out/name
        run(name,['verilator','--cc','--exe','--build','-j','2','--top-module','genefer_mod27_pair_pipe',
                  '--Mdir',str(directory),f'-GWORD_W={width}',f"-GMODULUS=27'd{p}",'-GPAYLOAD_W=32',
                  '-CFLAGS',f'-DTEST_WORD_W={width}',str(source),str(cpp)])
        return str(directory/'Vgenefer_mod27_pair_pipe')
    try:
        # Independent small-width induction check, including odd padded widths.
        proof_cases=0
        for width in range(1,11):
            padded=2*((width+1)//2)
            for p in range(2,min(1<<width,64)+1):
                for word in range(1<<width):
                    rem=0
                    for position in range(padded-1,-1,-1):
                        work=2*rem+((word>>position)&1)
                        assert 0<=work<2*p
                        rem=work-p if work>=p else work
                        assert 0<=rem<p
                    assert rem==word%p
                    proof_cases+=1
        report['exhaustive_modulo_proof_cases']=proof_cases
        vectors={}
        for width,p in ((53,69206017),(53,67239937),(51,67239937),(64,104857601),(1,2)):
            rng=random.Random(width*100+p);maximum=(1<<width)-1;stages=(width+1)//2;rows=[];tag=0
            def emit(reset,valid,x):
                nonlocal tag
                assert 0<=x<=maximum
                rows.append(f'{reset} {valid} {x} {tag} {x%p}\n');tag=(tag+0x1020305)&0xffffffff
            emit(0,1,maximum)
            boundary={0,1,maximum,maximum//2}
            for k in (0,1,2,3,31,32,maximum//p-1,maximum//p):
                for delta in (-1,0,1):
                    if 0<=k*p+delta<=maximum:boundary.add(k*p+delta)
            for bit in range(width):
                for delta in (-1,0,1):
                    if 0<=(1<<bit)+delta<=maximum:boundary.add((1<<bit)+delta)
            for x in sorted(boundary):emit(1,1,x)
            for j in range(12000):emit(int(j%401!=400),int(j%11!=10),rng.randrange(maximum+1))
            for depth in range(1,stages+2):
                emit(0,1,maximum)
                for j in range(depth):emit(1,1,rng.randrange(maximum+1))
                emit(0,1,maximum)
                for j in range(2*stages+3):emit(1,1,rng.randrange(maximum+1))
                for j in range(stages):emit(1,0,maximum)
            for j in range(stages):emit(1,0,maximum)
            path=out/f'vectors-{width}-{p}.txt';path.write_text(''.join(rows));vectors[width,p]=path
            report['sources'][str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
            exe=build(f'build-{width}-{p}',width,p);run(f'test-{width}-{p}',[exe,str(path)])
        if args.mutations:
            defects=[('compare',"work_rem>={1'b0,MODULUS}","work_rem>{1'b0,MODULUS}"),
                     ('shift','next_word=next_word<<1','next_word=next_word<<2'),
                     ('seed','next_rem=rems[s-1]','next_rem=0'),
                     ('input-bit','next_word[PAD_W-1]','next_word[PAD_W-2]'),
                     ('high-remainder','next_rem=work_rem[26:0]',"next_rem={1'b0,work_rem[25:0]}"),
                     ('payload','payloads[s]<=payloads[s-1]','payloads[s]<=payload_in'),
                     ('valid','assign stage_valid=valid[s-1]','assign stage_valid=in_valid'),
                     ('reset','if(!rst_n)valid[s]<=0',"if(!rst_n)valid[s]<=1")]
            for name,old,new in defects:
                text=rtl.read_text();assert text.count(old)==1
                source=out/f'mutant-{name}.sv';source.write_text(text.replace(old,new))
                exe=build('build-mutant-'+name,53,69206017,source)
                run('reject-mutant-'+name,[exe,str(vectors[53,69206017])],True)
        report['status']='passed'
    except BaseException as exc:report['status']='failed';report['error']=repr(exc);raise
    finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
