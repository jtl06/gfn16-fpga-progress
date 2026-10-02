"""Four-stage checked digit reduction versus independent Python modulo."""
from pathlib import Path
import argparse,hashlib,json,random,socket,subprocess,time

PRIMES=[104857601,69206017,67239937]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--mutations',action='store_true');a=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    top='genefer_digit_reduce27_pipe';src=root/f'rtl/kernel/{top}.sv';cpp=root/'rtl/tb/digit_reduce27_pipe.cpp'
    report={'status':'running','host':socket.gethostname(),'steps':[],
            'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [src,cpp,Path(__file__)]},'vectors':{}}
    def run(name,cmd,reject=False):
        then=time.monotonic();r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=300)
        (out/f'{name}.log').write_text(r.stdout);report['steps'].append({'name':name,'returncode':r.returncode,'seconds':time.monotonic()-then,'command':cmd})
        print(name,r.returncode,r.stdout[-550:],flush=True)
        if not reject and r.returncode:raise RuntimeError(name+' failed')
        if reject and (r.returncode==0 or not any(x in r.stdout for x in ['mismatch','digit stage','output range','unsupported digit reducer modulus'])):
            raise RuntimeError(name+' mutant not rejected')
    def build(name,p,source=src):
        directory=out/name
        # Deliberately illegal parameters can fold unsigned comparisons to
        # constants. Suppress only that diagnostic for those negative tests,
        # so the explicit parameter assertion is what rejects execution.
        diagnostics=[] if 62500000<=p<134217728 else ['-Wno-UNSIGNED']
        run(name,['verilator','--cc','--exe','--build','-j','2',*diagnostics,'--top-module',top,'--Mdir',str(directory),f'-GP={p}','-GPAYLOAD_W=32',str(source),str(cpp)])
        return str(directory/f'V{top}')
    try:
        for p in PRIMES:
            rng=random.Random(p);rows=[];tag=0
            def emit(rst,valid,x):
                nonlocal tag
                tag=(tag+0x9e3779b9)&0xffffffff
                good=x<=999999999 or x==0xffffffff
                value=(p-1 if x==0xffffffff else x%p) if good else 0
                rows.append(f'{rst} {valid} {x} {tag} {int(not good)} {value}\n')
            emit(0,1,0xffffffff)
            thresholds={0,1,2,999999998,999999999,1000000000,1000000001,0x3fffffff,0x40000000,0x7fffffff,0x80000000,0xfffffffe,0xffffffff}
            for k in range(17):
                for delta in range(-2,3):
                    if 0<=k*p+delta<=0xffffffff:thresholds.add(k*p+delta)
            for x in sorted(thresholds):emit(1,1,x)
            for _ in range(8):emit(1,0,0xffffffff)
            for j in range(24000):
                x=rng.randrange(1000000000) if j%3 else rng.getrandbits(32)
                if j%17==0:x=0xffffffff
                emit(int(j%317!=316),int(j%7!=6),x)
            # Reset each occupied stage with legal and invalid words in flight.
            for depth in range(1,5):
                for x in [p,999999999,0xffffffff,1000000000,0x80000000]:
                    for _ in range(depth):emit(1,1,x)
                    emit(0,1,x)
                    for _ in range(5):emit(1,0,x)
            # Finish with mixed consecutive valid/error responses and long
            # bubbles: output data holds on invalid requests and on errors.
            for x in [0xffffffff,1000000000,0,p-1,0xfffffffe,p,999999999]:emit(1,1,x)
            for _ in range(12):emit(1,0,0x80000000)
            vectors=out/f'vectors-{p}.txt';vectors.write_text(''.join(rows))
            report['vectors'][str(p)]={'path':str(vectors),'rows':len(rows),'sha256':hashlib.sha256(vectors.read_bytes()).hexdigest()}
            exe=build(f'build-{p}',p);run(f'test-{p}',[exe,str(vectors)])
            if a.mutations:
                defects=[
                    ('threshold8','normalized>=P8','normalized>P8'),
                    ('threshold4','s1>=P4','s1>P4'),
                    ('threshold2','s2>=P2','s2>P2'),
                    ('threshold1',"s3>=28'(P)","s3>28'(P)"),
                    ('special',"P-32'd1 : digit","32'd0 : digit"),
                    ('fullword',"digit<=32'd999999999","digit[29:0]<=30'd999999999"),
                    ('latency','out_valid<=good[2]','out_valid<=good[1]'),
                    ('payload','payload_out<=tag3','payload_out<=tag2'),
                    ('error-valid','out_valid<=good[2]','out_valid<=good[2] || bad[2]'),
                    ('reset',"good<='0;bad<='0;",'good<=good;bad<=bad;'),
                    ('hold',"if(good[2])residue<=","if(good[2] || bad[2])residue<=")]
                for name,old,new in defects:
                    text=src.read_text()
                    if text.count(old)!=1:raise RuntimeError('mutation anchor '+name)
                    path=out/f'mutant-{p}-{name}.sv';path.write_text(text.replace(old,new))
                    exe=build(f'build-{p}-{name}',p,path);run(f'reject-{p}-{name}',[exe,str(vectors)],True)
        # A value with16P exactly at/below the maximum cannot use four bits
        # of quotient; a modulus at2^27 cannot fit the27-bit result contract.
        vectors=out/f'vectors-{PRIMES[0]}.txt'
        for p in [0,62499999,134217728]:
            exe=build(f'build-invalid-{p}',p);run(f'reject-invalid-{p}',[exe,str(vectors)],True)
        report['status']='passed'
    except BaseException as exc:report['status']='failed';report['error']=repr(exc);raise
    finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
