"""Independent whole-integer oracle for carry_fast. Execute on aethia only."""
from pathlib import Path
import argparse
import random
import socket
import subprocess
import hashlib
import json

def encode(a, b):
    if len(a)==1: return a[0]
    h=len(a)//2
    return encode(a[:h],b)+pow(b,h)*encode(a[h:],b)

def decode(x,b,n):
    if n==1: return [x]
    h=n//2; high,low=divmod(x,pow(b,h))
    return decode(low,b,h)+decode(high,b,h)

def expected(a,b):
    modulus=pow(b,len(a))+1
    x=encode(a,b)%modulus
    return [-1]+[0]*(len(a)-1) if x==modulus-1 else decode(x,b,len(a))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--square-vectors',type=Path)
    ap.add_argument('--mutations',action='store_true')
    args=ap.parse_args()
    if socket.gethostname()!='aethia': raise RuntimeError('Run simulation on aethia only')
    root=Path(__file__).resolve().parents[1];out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    rng=random.Random(0xcafef00d);limit=(1<<94)-1;cases=[]
    def emit(name,a,b): cases.append((name,a,b,expected(a,b)))
    bases=[2,3,4,7,31,65535,65536,1<<29,604832956,999999999,1000000000]
    for b in bases:
        for lg in [1,2,5,8]:
            n=1<<lg
            patterns=[[limit]*n,[-limit]*n,[limit if i%2 else -limit for i in range(n)],
                      [-1]+[0]*(n-1),[b-1]*n,[0]*n,
                      [rng.randrange(-limit,limit+1) for _ in range(n)]]
            for k,a in enumerate(patterns):emit(f'b{b}-lg{lg}-p{k}',a,b)
    for i in range(100):
        b=rng.randrange(2,1000000001);a=[rng.randrange(-limit,limit+1) for _ in range(32)]
        emit(f'random{i}',a,b)
    # Alternate sizes and radices in one no-reset invocation of the testbench,
    # with full coefficient reload followed by twice re-normalizing its result.
    for kind in ['maximum','negative','minus-one']:
        for lg in [1,4,16]:
            n=1<<lg
            for b in [2,604832956,1000000000]:
                a=[limit]*n if kind=='maximum' else [-limit]*n if kind=='negative' else [-1]+[0]*(n-1)
                emit(f'chained-{kind}-lg{lg}-b{b}',a,b)
    # Full size, including tiny-base worst signed carry chains.
    for b in [2,604832956,1000000000]:
        emit(f'full-random-b{b}',[rng.randrange(-limit,limit+1) for _ in range(65536)],b)
        emit(f'full-negative-b{b}',[-limit]*65536,b)
    if args.square_vectors:
        for path in sorted(args.square_vectors.glob('square-gfn16-bit*-post.txt')):
            tokens=path.read_text().split()
            lg,b,bit=map(int,tokens[:3]); n=1<<lg
            # Existing postprocess vectors have N rows of three residues and
            # one centered coefficient, then N expected digits.
            rows=[tokens[3+i*4:3+(i+1)*4] for i in range(n)]
            coeff=[int(row[3])*(2 if bit else 1) for row in rows]
            emit(path.stem,coeff,b)
            if cases[-1][3]!=list(map(int,tokens[3+4*n:])):
                raise AssertionError('Existing square expected digits disagree with independent bigint oracle')
    # Recurrent independent bigint modular squares, derive coefficients by sparse
    # polynomial square for N32 then feed those signed negacyclic coefficients.
    for b in [2,7,604832956,1000000000]:
        a=[rng.randrange(b) for _ in range(32)]
        for step in range(12):
            coeff=[0]*32
            for i,x in enumerate(a):
                for j,y in enumerate(a):coeff[(i+j)%32]+=x*y*(1 if i+j<32 else -1)
            emit(f'recurrent-b{b}-step{step}',coeff,b)
            a=expected(coeff,b)
    vectors=out/'vectors.txt'
    with vectors.open('w') as f:
        for name,a,b,result in cases:
            f.write(f'{name} {len(a).bit_length()-1} {b}\n')
            f.write(' '.join(map(str,a))+'\n'+' '.join(map(str,result))+'\n')
    for baseline in [False,True]:
        top='genefer_carry' if baseline else 'genefer_carry_fast';build=out/top
        command=['verilator','--cc','--exe','--build','-j','2','--top-module',top,'--Mdir',str(build),
                 str(root/'rtl/kernel'/f'{top}.sv'),str(root/'rtl/tb/carry_fast.cpp')]
        if baseline:command+=['-CFLAGS','-DBASELINE']
        with (out/f'{top}-build.log').open('w') as log:subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
        with (out/f'{top}-run.log').open('w') as log:subprocess.run([str(build/f'V{top}'),str(vectors)],check=True,stdout=log,stderr=subprocess.STDOUT)
        with (out/f'{top}-chain.log').open('w') as log:subprocess.run([str(build/f'V{top}'),str(vectors),'--chain'],check=True,stdout=log,stderr=subprocess.STDOUT)
        print(f'{top}: PASS {len(cases)} cases',flush=True)
    if args.mutations:
        source=(root/'rtl/kernel/genefer_carry_fast.sv').read_text()
        for name,old,new in [('floor','quotient-96\'sd1','quotient'),
                             ('reciprocal-correction','provisional_rem>=base_reg[31:0]','provisional_rem>base_reg[31:0]')]:
            mutant=out/f'mutant-{name}';mutant.mkdir(exist_ok=True)
            if old not in source:raise AssertionError('Missing mutation anchor')
            rtl=mutant/'genefer_carry_fast.sv';rtl.write_text(source.replace(old,new))
            command=['verilator','--cc','--exe','--build','-j','2','--top-module','genefer_carry_fast',
                     '--Mdir',str(mutant/'build'),str(rtl),str(root/'rtl/tb/carry_fast.cpp')]
            with (mutant/'build.log').open('w') as log:subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
            run=subprocess.run([str(mutant/'build/Vgenefer_carry_fast'),str(vectors)],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            (mutant/'run.log').write_text(run.stdout)
            if run.returncode!=1 or 'carry mismatch' not in run.stdout:raise AssertionError(f'Mutant survived: {name}')
            print(f'mutant-{name}: REJECTED',flush=True)
    sources=[root/'rtl/kernel/genefer_carry_fast.sv',root/'rtl/kernel/genefer_carry.sv',root/'rtl/tb/carry_fast.cpp',Path(__file__)]
    report={'status':'passed','host':socket.gethostname(),'cases':len(cases),
            'runs_per_implementation':4*len(cases),'no_reset_runs_per_implementation':3*len(cases),
            'mutations_checked':args.mutations,
            'source_sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
            'vectors_sha256':hashlib.sha256(vectors.read_bytes()).hexdigest()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
