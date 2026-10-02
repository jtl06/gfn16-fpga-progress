"""Exact-build-cache experiment; correctness oracle always reruns, aethia only."""
import argparse
import hashlib
import json
import os
import platform
import shlex
import shutil
import sys
from pathlib import Path
import random
import resource
import socket
import subprocess
import time
from .build_cache import BuildCache, BuildProduct, BuildSpec, fingerprint_toolchain
from .ntt36_experiment import RADIX,select_basis,validate

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--quick',action='store_true')
    ap.add_argument('--cache',type=Path,required=True)
    ap.add_argument('--mutation-smoke',action='store_true');args=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30))
    root=Path(__file__).resolve().parents[1];out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    rtl=root/'rtl/kernel/genefer_montgomery_mul36_sparse_pipe.sv';cpp=root/'rtl/tb/montgomery36_pipe.cpp'
    report=dict(status='running',host=socket.gethostname(),radix_bits=36,stages=6,initiation_interval=1,
                memory_limit_bytes=6<<30,math=validate(),steps=[],branches={},sources={})
    for path in (rtl,cpp,Path(__file__),root/'reference/ntt36_experiment.py',root/'reference/build_cache.py',root/'tests/test_build_cache.py'):
        report['sources'][str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
    def run(name,command,rejection=None):
        then=time.monotonic();proc=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
        (out/f'{name}.log').write_text(proc.stdout)
        passed=proc.returncode==0 if rejection is None else proc.returncode!=0 and any(x in proc.stdout for x in rejection)
        report['steps'].append(dict(name=name,passed=passed,returncode=proc.returncode,seconds=time.monotonic()-then,command=command))
        print(f"{name}: {'PASS' if passed else 'FAIL'} {proc.stdout[-220:]}",flush=True)
        if not passed:raise RuntimeError(proc.stdout[-2000:])
    compiler=shutil.which('g++')
    def compiler_path(option):
        return Path(subprocess.check_output([compiler,option],text=True).strip()).resolve()
    tool_files=[Path('/bin/sh'),compiler_path('-print-prog-name=cc1plus'),compiler_path('-print-prog-name=collect2')]
    for name in ('libstdc++.so','libgcc_s.so.1','libgcc.a','libc.so','libc.so.6',
                 'libm.so','libm.so.6','libatomic.so','libpthread.so.0',
                 'crtbeginS.o','crtendS.o','crti.o','crtn.o','Scrt1.o'):
        path=compiler_path('-print-file-name='+name)
        if path.exists():tool_files.append(path)
    trees=[Path('/usr/include'),compiler_path('-print-file-name=include'),
           Path(os.environ['VERILATOR_ROOT'])/'include']
    fixed=compiler_path('-print-file-name=include-fixed')
    if fixed.is_dir():trees.append(fixed)
    toolchain=fingerprint_toolchain({
        'verilator':['verilator','-V'],'verilator_bin':['verilator_bin','--version'],
        'compiler':[compiler,'--version'],'make':['make','--version'],
        'compiler_specs':[compiler,'-dumpspecs'],
        'assembler':['as','--version'],'linker':['ld','--version'],
        'archiver':['ar','--version'],'ranlib':['ranlib','--version'],
        'verilator_interpreter':['perl','-V'],
    },files=tool_files,trees=trees)
    toolchain['platform']={'system':platform.system(),'machine':platform.machine(),'python':platform.python_version()}
    env_names=set(('PATH CC CXX CPPFLAGS CFLAGS CXXFLAGS LDFLAGS LD_LIBRARY_PATH LD_PRELOAD LD_AUDIT LIBRARY_PATH '
        'CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH OBJC_INCLUDE_PATH VERILATOR_ROOT MAKEFLAGS MFLAGS '
        'SOURCE_DATE_EPOCH LANG LC_ALL TZ GCC_EXEC_PREFIX COMPILER_PATH PERL5LIB PERLLIB PERL5OPT').split())
    env_names.update(k for k in os.environ if k.startswith(('CCACHE_','DISTCC_','VERILATOR_','GCC_')))
    environment={k:os.environ.get(k) for k in sorted(env_names)}
    report['build_cache']=[]
    cache=BuildCache(args.cache,log=lambda message:print(message,flush=True))
    def build(name,p,q,source=rtl):
        parameters=[f"-GP=36'd{p}",f"-GQ=36'd{q}"]
        flags=['--cc','--exe','--build','-j','2','--top-module','genefer_montgomery_mul36_sparse_pipe']
        spec=BuildSpec.capture(sources={'rtl':source,'cpp':cpp},
            configuration={'flags':flags,'parameters':parameters,'cwd':str(root),
                           'build_directory':'<private-stage>','executable':'Vgenefer_montgomery_mul36_sparse_pipe'},
            toolchain=toolchain,environment=environment)
        def compile_into(directory):
            run(f'build-{name}',['verilator',*flags,'--Mdir',str(directory),*parameters,str(source),str(cpp)])
            dependencies=set()
            for depfile in directory.glob('*.d'):
                content=depfile.read_text().replace(chr(92)+chr(10),' ')
                for rule in content.splitlines():
                    if ':' not in rule:continue
                    for word in shlex.split(rule.split(':',1)[1]):
                        path=Path(word)
                        dependencies.add(path if path.is_absolute() else directory/path)
            return BuildProduct('Vgenefer_montgomery_mul36_sparse_pipe',tuple(dependencies))
        result=cache.obtain(spec,compile_into)
        report['build_cache'].append(dict(name=name,key=result.key,status=result.cache_status,
            executable_sha256=result.executable_sha256,manifest=str(result.manifest)))
        return str(result.executable)
    try:
        run('cache-unit-tests',[sys.executable,'-m','unittest','tests.test_build_cache','-v'])
        for field in select_basis()[:1 if args.quick else 3]:
            p,q=field['p'],field['q'];rng=random.Random(0x36cafe+p);rows=[];branches=[0,0]
            inverse=pow(RADIX,-1,p)
            def emit(reset,valid,x,y):
                # Oracle uses ordinary Python big integers and modular inverse,
                # independently of the RTL sparse reduction identity.
                value=x*y*inverse%p
                if reset and valid:
                    assert 0<=x<p and 0<=y<p
                    t=x*y;m=t*q%RADIX;branches[int(t//RADIX<(m*p)//RADIX)]+=1
                rows.append(f'{reset} {valid} {x} {y} {value}\n')
            emit(0,1,RADIX-1,RADIX-1)
            edges=sorted({0,1,2,p//2-1,p//2,p//2+1,p-3,p-2,p-1,RADIX%p,
                          *[x for bit in (17,18,26,27,32,34,35) for x in ((1<<bit)-1,1<<bit,(1<<bit)+1) if x<p]})
            for x in edges:
                for y in edges:emit(1,1,x,y)
            for j in range(5000 if args.quick else 40000):
                reset=j%251!=250;valid=j%7!=6
                x,y=(rng.randrange(p),rng.randrange(p)) if reset and valid else (rng.randrange(RADIX),rng.randrange(RADIX))
                emit(int(reset),int(valid),x,y)
            for depth in range(1,7):
                for j in range(depth):emit(1,1,p-1-j,p-2-j)
                emit(0,1,RADIX-1,RADIX-1)
                for _ in range(12):emit(1,1,rng.randrange(p),rng.randrange(p))
            for _ in range(12):emit(1,0,RADIX-1,RADIX-1)
            assert min(branches)>0;report['branches'][str(p)]=branches
            vectors=out/f'vectors-{p}.txt';vectors.write_text(''.join(rows))
            report['sources'][str(vectors)]=hashlib.sha256(vectors.read_bytes()).hexdigest()
            exe=build(str(p),p,q);run(f'test-{p}',[exe,str(vectors),str(p)])
            for name,x,y in (('lhs-P',p,1),('rhs-P',1,p),('max-lhs',RADIX-1,1),('max-rhs',1,RADIX-1)):
                run(f'reject-{name}-{p}',[exe,'reject',str(p),str(x),str(y)],['noncanonical Montgomery36 input'])
            if not args.quick or args.mutation_smoke:
                mutants=[
                    ('variable-high','ab_s1<=lhs*rhs;',"ab_s1<={1'b0,lhs[34:0]}*rhs;"),
                    ('q-shift','m_head_s2<=lo-(lo<<35);','m_head_s2<=lo;'),
                    ('p-shift','sum_low_s4<=m_ext+(m_ext<<S);','sum_low_s4<=m_ext;'),
                    ('wide-m',"{36'b0,m_s3}","{37'b0,m_s3[34:0]}"),
                    ('negative','else result<=corrected[35:0];','else result<=hi_s5-mp_hi_s5;'),
                    ('equality','hi_s5>=mp_hi_s5','hi_s5>mp_hi_s5'),
                    ('latency','out_valid<=valid_pipe[4]','out_valid<=valid_pipe[3]'),
                    ('reset',"valid_pipe<='0","valid_pipe<='1"),
                    ('hold','if(valid_pipe[4])begin',"if(!valid_pipe[4])result<=36'd123;\n            if(valid_pipe[4])begin"),
                ]
                if len(field['shifts'])==3:mutants.append(('extra-q','m_tail_s2<=(lo<<S)+extra_q;','m_tail_s2<=(lo<<S);'))
                if args.quick:mutants=[mutants[1]]
                for name,old,new in mutants:
                    source=rtl.read_text()
                    if source.count(old)!=1:raise RuntimeError('bad mutation anchor '+name)
                    path=out/f'mutant-{name}-{p}.sv';path.write_text(source.replace(old,new))
                    exe=build(f'{name}-{p}',p,q,path)
                    run(f'reject-mutant-{name}-{p}',[exe,str(vectors),str(p)],['Montgomery arithmetic mismatch','valid/latency mismatch','invalid-cycle result hold mismatch'])
                if not args.quick:
                    old='$fatal(1,"noncanonical Montgomery36 input");';path=out/f'mutant-domain-{p}.sv'
                    path.write_text(rtl.read_text().replace(old,';'));exe=build(f'domain-{p}',p,q,path)
                    run(f'reject-mutant-domain-{p}',[exe,'reject',str(p)],['invalid input assertion missing'])
        if not args.quick:
            for name,p,q,message in (('modulus',3,1,'unsupported sparse Montgomery36 modulus'),
                                    ('inverse',select_basis()[0]['p'],select_basis()[0]['q']^2,'invalid sparse Montgomery36 inverse')):
                exe=build(name,p,q);run('reject-'+name,[exe,'reject',str(p)],[message])
        report['status']='passed'
    except BaseException as error:
        report.update(status='failed',error=repr(error));raise
    finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
