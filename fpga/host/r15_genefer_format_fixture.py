"""Azure finite upstream gint/file oracle, never run on the coordinator.

Uses only N32 synthetic transcript records1,2,-1. It proves byte-format/hash
compatibility with actual pinned headers, NOT whole upstream PL execution.
Dispatcher must run this inside the existing source/compile/resource envelope.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from .r15_arithmetic import need
from .r15_genefer_proof import encode_proof, hash64, challenge, digits

UPSTREAM_PINS = {
    'LICENSE':'b04a46091103dec4f1ed62fd980ae1cead9c05f983b5679a0cb8c657a76a85a6',
    'src/genefer.h':'d436a100788d8e78b091fd423e9061e1c16a88d741b9394f9155888d974ea27f',
    'src/gint.h':'fb07253fe5147db6b8aca433baf46f11afc648e03424df2c7ef2ac1a0e94e9fd',
    'src/file.h':'7f91f5860a1049ccb0eca0b7cecdde21048992d8fc68d22046f41328d81994e4',
    'src/pio.h':'ad0fb9984917f720ae060612117968d1a16165e2c9f1d2556656bf5aa97fe2ef',
    'src/boinc.h':'23dd7a3dbe404aadf50b3c1934d7e34cc0d65b9d51cbca784e1c2a8d1e5b3290',
}


def check_upstream(root):
    root=Path(root)
    for name, pin in UPSTREAM_PINS.items():
        path=root/name
        need(path.is_file() and not path.is_symlink() and
             hashlib.sha256(path.read_bytes()).hexdigest()==pin, 'PINNED_GENEFER:'+name)


def capture(root, output):
    """Source-only capture; no compilation/arithmetic or source overwrites."""
    root, output=Path(root), Path(output)
    check_upstream(root)
    output.mkdir(parents=True, exist_ok=False)
    for name in UPSTREAM_PINS:
        target=output/name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write((root/name).read_bytes())
    check_upstream(output)
    return dict(commit='d5060c61090942f42a908492628eba13ebd7cd82',
                license='MIT', sources=UPSTREAM_PINS, captured_only=True)


def run(root, work, compiler):
    need(platform.system()=='Linux', 'FORMAT_ORACLE_LINUX_ONLY')
    root, work, compiler=Path(root), Path(work), Path(compiler)
    check_upstream(root)
    need(compiler == Path('/usr/bin/g++'), 'FORMAT_COMPILER_EXACT')
    need(work.is_absolute() and not work.exists(), 'FORMAT_FRESH_WORK')
    work.mkdir(parents=True)
    driver=Path(__file__).with_name('r15_genefer_format_oracle.cpp')
    exe=work/'genefer-format-oracle'
    compile_argv=[str(compiler), '-std=c++17', '-O2', '-I'+str(root/'src'),
                  str(driver), '-lgmp', '-pthread', '-o', str(exe)]
    build=subprocess.run(compile_argv, capture_output=True, text=True, timeout=60, check=True)
    expected_hashes=[(hash64(digits(x,10,32)),challenge(digits(x,10,32))) for x in (1,2,10**32)]
    result=subprocess.run([str(exe),str(work/'proof.bin')], capture_output=True,
                          text=True, timeout=10, check=True)
    observed=[tuple(map(int,line.split())) for line in result.stdout.splitlines()]
    need(observed==expected_hashes and result.stderr=='', 'FORMAT_UPSTREAM_HASHES')
    actual=(work/'proof.bin').read_bytes()
    need(actual==encode_proof(10,32,(1,2,10**32),enabled=True), 'FORMAT_UPSTREAM_BYTES')
    return dict(schema='r15-genefer-format-oracle-v1', status='upstream_format_equal',
                n=32,base=10,depth=2,records=3,bytes=len(actual),
                proof_sha256=hashlib.sha256(actual).hexdigest(),
                upstream_commit='d5060c61090942f42a908492628eba13ebd7cd82',
                compiler=str(compiler), build_stderr=build.stderr,
                upstream_full_PL_executed=False, board=False, promotion=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--upstream',type=Path,required=True)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--compiler',type=Path,default=Path('/usr/bin/g++'))
    args=parser.parse_args()
    print('R15_FORMAT_RESULT '+json.dumps(run(args.upstream,args.work,args.compiler),sort_keys=True))
