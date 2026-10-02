"""Pair-step96-stage CRT27 validation with independent centered integer oracle."""
from pathlib import Path
import argparse,hashlib,itertools,json,random,socket,subprocess,time

PRIMES=(104857601,69206017,67239937)
P12=7256776917385217
MODULUS=487945222748036195811329
WORST=131071999737856000131072

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--mutations',action='store_true');a=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    root=Path(__file__).resolve().parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    rtl=root/'rtl/kernel/genefer_crt3_27_pair_pipe.sv';mod=root/'rtl/kernel/genefer_mod27_pair_pipe.sv';cpp=root/'rtl/tb/crt3_27_pair_pipe.cpp'
    p1,p2,p3=PRIMES;half=MODULUS//2
    assert p1*p2==P12 and P12*p3==MODULUS and p1<2*p2 and WORST<half
    assert pow(p1,-1,p2)==44780362 and pow(P12,-1,p3)==10355480
    assert P12<1<<53 and MODULUS<1<<79
    # All canonical residues: a=INV12*delta2; x12=P1*t2+r1; c=INV123*delta3.
    assert 44780362*(p2-1)<1<<53
    assert p1*(p2-1)+(p1-1)==P12-1<1<<53
    assert 10355480*(p3-1)<1<<51
    terms=[(MODULUS//p)*pow(MODULUS//p,-1,p) for p in PRIMES]
    def center(x):
        x%=MODULUS;return x-MODULUS if x>half else x
    def oracle(residues):return center(sum(r*t for r,t in zip(residues,terms)))
    rng=random.Random(0x27c37);rows=[];counts={'corners':0,'centered':0,'multiples':0,'random':0}
    def emit(reset,valid,residues):
        if reset and valid:assert all(0<=r<p for r,p in zip(residues,PRIMES))
        rows.append(f'{reset} {valid} '+' '.join(map(str,residues))+f' {oracle(residues)}\n')
    def from_int(x,label):
        r=[x%p for p in PRIMES];assert oracle(r)==center(x);emit(1,1,r);counts[label]+=1
    emit(0,1,[0xffffffff]*3)
    for r in itertools.product(*[[0,1,2,p//2,p-2,p-1]+([p2-1,p2,p2+1] if p==p1 else []) for p in PRIMES]):emit(1,1,r);counts['corners']+=1
    for x in [0,1,-1,2,-2,half-1,half,half+1,-half-1,-half,-half+1,MODULUS-1,MODULUS,MODULUS+1,
              -MODULUS-1,-MODULUS,-MODULUS+1,WORST-1,WORST,WORST+1,-WORST-1,-WORST,-WORST+1]:from_int(x,'centered')
    for p in PRIMES:
        for k in [0,1,2,3,31,32,half//p-1,half//p,half//p+1,MODULUS//p-1,MODULUS//p,MODULUS//p+1]:
            for sign in [-1,1]:
                for d in [-1,0,1]:from_int(sign*k*p+d,'multiples')
    for j in range(24000):
        reset=j%503!=502;valid=j%11!=10
        r=[rng.randrange(p) for p in PRIMES] if reset and valid else [rng.randrange(1<<32) for _ in PRIMES]
        emit(int(reset),int(valid),r);counts['random']+=int(reset and valid)
    for depth in range(1,98):
        emit(0,1,[0xffffffff]*3)
        for j in range(depth):from_int(half-j,'centered')
        emit(0,1,[0xffffffff]*3)
        for j in range(96):emit(1,1,[rng.randrange(p) for p in PRIMES])
        for j in range(96):emit(1,0,[0xffffffff]*3)
    for j in range(96):emit(1,0,[0xffffffff]*3)
    vectors=out/'vectors.txt';vectors.write_text(''.join(rows))
    report={'status':'running','host':socket.gethostname(),'cases':counts,'steps':[],
            'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [rtl,mod,cpp,Path(__file__),vectors]}}
    def run(name,cmd,reject=None):
        then=time.monotonic();r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=600)
        (out/f'{name}.log').write_text(r.stdout);report['steps'].append({'name':name,'returncode':r.returncode,'seconds':time.monotonic()-then,'command':cmd})
        print(name,r.returncode,r.stdout[-650:],flush=True)
        if reject is None and r.returncode:raise RuntimeError(name+' failed')
        if reject is not None and (r.returncode==0 or not any(t in r.stdout for t in reject)):raise RuntimeError(name+' not rejected correctly')
    def build(name,source=rtl):
        directory=out/name
        run(name,['verilator','--cc','--exe','--build','-j','2','--top-module','genefer_crt3_27_pair_pipe',
                  '--Mdir',str(directory),str(mod),str(source),str(cpp)])
        return str(directory/'Vgenefer_crt3_27_pair_pipe')
    try:
        exe=build('build-crt27');run('test-crt27',[exe,str(vectors)])
        for i,p in enumerate(PRIMES):
            for value in [p,1<<27,0xffffffff]:
                r=[0]*3;r[i]=value
                run(f'reject-input{i}-{value}',[exe,'reject',*map(str,r)],['noncanonical CRT27 input'])
        if a.mutations:
            defects=[
                ('inverse12',"26'd44780362","26'd44780363"),
                ('inverse123',"24'd10355480","24'd10355481"),
                ('r1-reduction','r1_small>=P2 ? r1_small-P2 : r1_small','r1_small'),
                ('input-payload','a_payload[0]<=input_payload[1]','a_payload[0]<=input_payload[0]'),
                ('input-valid','va<={va[1:0],input_valid[1]}','va<={va[1:0],input_valid[0]}'),
                ('delta2-sign','delta2_diff[27] ?','!delta2_diff[27] ?'),
                ('delta3-sign','delta3_diff[27] ?','!delta3_diff[27] ?'),
                ('delta3-payload','c_payload[0]<=x_payload_d','c_payload[0]<=px[79:27]'),
                ('delta3-valid','vc<={vc[1:0],vx_d}','vc<={vc[1:0],vx}'),
                ('early-payload','payload_in(a_payload[2])','payload_in(a_payload[1])'),
                ('x-payload','{x12,b_payload[2][26:0]}','{x12,b_payload[1][26:0]}'),
                ('center','value>(MODULUS>>1)','value>=(MODULUS>>1)'),
                ('sign',"$signed({17'b0,value})-$signed({17'b0,MODULUS})","$signed({17'b0,MODULUS})-$signed({17'b0,value})"),
                ('latency','out_valid<=vd[2]','out_valid<=vd[1]'),
                ('reset','vd<=0;',"vd<=3'b111;"),
                ('high-product','d_hi<=P12*t3[26:16]',"d_hi<=64'd0")]
            for name,old,new in defects:
                text=rtl.read_text()
                if text.count(old)!=1:raise RuntimeError('mutation anchor '+name)
                path=out/f'mutant-{name}.sv';path.write_text(text.replace(old,new))
                exe=build('build-mutant-'+name,path)
                run('reject-mutant-'+name,[exe,str(vectors)],['CRT27 arithmetic/sign/tag mismatch','CRT27 ready/latency mismatch','CRT27 x12 bound','CRT27 value bound','CRT27 delta2 bound','CRT27 delta3 bound'])
            text=rtl.read_text();old='$fatal(1,"noncanonical CRT27 input");';assert text.count(old)==1
            path=out/'mutant-input-assert.sv';path.write_text(text.replace(old,';'))
            exe=build('build-mutant-input-assert',path)
            run('reject-mutant-input-assert',[exe,'reject',str(p1),'0','0'],['CRT27 input assertion missing'])
        report['status']='passed'
    except BaseException as exc:report['status']='failed';report['error']=repr(exc);raise
    finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
