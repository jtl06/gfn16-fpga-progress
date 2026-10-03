"""Finite pinned-method PL/GL interoperability fixture on Azure only.

Runs exact upstream algorithms through a small synthetic GMP transform ABI,
not its real CPU/OpenCL engine, hardware, full-N PRP or BOINC certificate server.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess

from .r15_arithmetic import SoftwareBackend, need
from .r15_genefer_format_fixture import UPSTREAM_PINS as FORMAT_PINS
from .r15_genefer_proof import (generate_proof, decode_proof, verify_proof,
                               challenge, digits, hash64)

UPSTREAM_PINS = dict(FORMAT_PINS, **{
    'src/transform.h':'603a54b84b4ef99b3981e8b6b3bc33d787dd1c72cdf78d313e96f4daf8d36957',
    'src/timer.h':'ecdb34069999fdea517d815ed384d54af666ad20b82eb72c180a8f8158609db7',
    'src/arith.h':'df96dac4da0742d24bdfb0e9de7808eb88e4f95c842987e56f3c210bcdd9a96e'})


def check_upstream(root):
    for name, pin in UPSTREAM_PINS.items():
        path=Path(root)/name
        need(path.is_file() and not path.is_symlink() and
             hashlib.sha256(path.read_bytes()).hexdigest()==pin, 'PL_UPSTREAM:'+name)


def capture(root, output):
    check_upstream(root)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    for name in UPSTREAM_PINS:
        path=output/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write((Path(root)/name).read_bytes())
    check_upstream(output)
    return dict(commit='d5060c61090942f42a908492628eba13ebd7cd82',sources=UPSTREAM_PINS,
                license='MIT',captured_only=True)


def proof_key(backend, raw):
    mus=decode_proof(raw,backend.base,backend.n,enabled=True)
    value=1
    for mu in mus:
        value=value*backend.power(mu,challenge(digits(mu,backend.base,backend.n)))%backend.modulus
    return hash64(digits(int(value),backend.base,backend.n))


def run(root, work, compiler):
    need(platform.system()=='Linux','PL_ORACLE_LINUX_ONLY')
    root,work,compiler=Path(root),Path(work),Path(compiler)
    check_upstream(root)
    need(compiler==Path('/usr/bin/g++') and work.is_absolute() and not work.exists(),
         'PL_EXACT_COMPILER_FRESH_WORK')
    work.mkdir(parents=True)
    driver=Path(__file__).with_name('r15_genefer_pl_oracle.cpp');exe=work/'pl-oracle'
    argv=[str(compiler),'-std=c++17','-O2','-I'+str(root/'src'),str(driver),
          '-lgmpxx','-lgmp','-pthread','-o',str(exe)]
    build=subprocess.run(argv,capture_output=True,text=True,timeout=60,check=True)
    result=subprocess.run([str(exe),str(work)],capture_output=True,text=True,timeout=15,check=True)
    rows=re.findall(r'R15_PL_ORACLE base=(\d+) pkey=(\d+) gl=1 bad_gl=1',result.stdout)
    need(len(rows)==3 and result.stderr=='','PL_ORACLE_EXACT_ROWS')
    checked=[]
    for (base_text,key_text),base in zip(rows,(10,599,600),strict=True):
        need(int(base_text)==base,'PL_BASE_ORDER')
        b=SoftwareBackend(base,32,enabled=True,engine='gmp')
        actual=(work/f'base{base}.proof').read_bytes()
        wanted=generate_proof(b,base**32,3,enabled=True)
        need(actual==wanted and verify_proof(b,base**32,actual,enabled=True) and
             int(key_text)==proof_key(b,actual),'PL_BYTES_RELATION_PKEY')
        checked.append(dict(base=base,n=32,depth=3,bytes=len(actual),
                            proof_sha256=hashlib.sha256(actual).hexdigest(),pkey=int(key_text),
                            upstream_GL_bad_result_rejected=True))
    return dict(schema='r15-pinned-genefer-pl-gl-oracle-v1',status='software_interop_equal',
                rows=checked,upstream_commit='d5060c61090942f42a908492628eba13ebd7cd82',
                upstream_PL_GL_methods_executed=True,synthetic_GMP_transform=True,
                real_genefer_transform=False,full_N_PRP=False,board=False,
                BOINC_server=False,promotion=False,build_stderr=build.stderr)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--upstream',type=Path,required=True)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--compiler',type=Path,default=Path('/usr/bin/g++'))
    args=parser.parse_args()
    print('R15_PL_RESULT '+json.dumps(run(args.upstream,args.work,args.compiler),sort_keys=True))
