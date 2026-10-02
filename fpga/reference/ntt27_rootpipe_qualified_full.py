"""AW16/L64 all-field gate requiring the exact qualified recovery composite.

The original failed small report stays failed. This profile builds only three
new full-size models, with j4/CPU400, serial execution and the unchanged oracle.
"""
import argparse
import json
from pathlib import Path
import resource
import socket

from .ntt27_rootpipe_full_regression import FullLab,digest
from .ntt27_rootpipe_composite import validate_composite
from .ntt27_rootpipe_regression import (bench_proof,validate_files,cache_context,
    cases_for,centered_crt,EXPERIMENT_PRIMES,encode)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--failed-report',type=Path,required=True)
    parser.add_argument('--recovery-report',type=Path,required=True)
    parser.add_argument('--compile-lock',type=Path,required=True)
    args=parser.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30))
    root=Path(__file__).resolve().parents[1]
    if digest(root/'reference/ntt27_rootpipe_composite.py')!='a167c2a127dc4532d12671dce6ad97bfe3e1fab3718a8cde1b7ea4566f4e2f1c':
        raise RuntimeError('reviewed composite validator changed')
    qualified=validate_composite(args.failed_report,args.recovery_report,
                                 source_root=root,check_executables=True)
    args.output.mkdir(parents=True,exist_ok=False)
    lab=FullLab(args.output,'verilator');lab.lanes=64;lab.compile_lock=args.compile_lock.resolve()
    lab.report.update(profile='rootpipe-qualified-aw16-l64-j4-runtime1-v1',compile_workers=4,
        model_threads=1,memory_limit_bytes=6<<30,composite_prerequisite=qualified,
        profile_delta='Only AW16/all3fields; j4 and explicit threads1. RTL/bench/old helpers unchanged; no small/mutant rebuild forest.')
    try:
        lab.report['structure_proof']=validate_files(root);lab.report['bench_proof']=bench_proof(root)
        _,toolchain,environment=cache_context(args.output/'unused-cache-record-only')
        manifest=args.output/'toolchain.json'
        manifest.write_text(json.dumps(dict(toolchain=toolchain,environment=environment),indent=2)+'\n')
        lab.report['toolchain_manifest']={'path':str(manifest),'sha256':digest(manifest)}
        cases=cases_for(16)+[('max-base1e9',[999999999]*65536,1000000000)];planes=[]
        for field in range(3):
            exe=lab.build_ntt(field,16,64)
            planes.append(lab.cached_squares(field,16,exe,cases))
            lab.canonical_checks(field,16,exe)
            for lg in range(1,17):lab.transform_test(field,lg,exe,'-ntt27-aw16')
            lab.resets(field,exe,64)
        for i,(name,digits,base) in enumerate(cases):
            coeff=[centered_crt((planes[f][i][j] for f in range(3)),EXPERIMENT_PRIMES) for j in range(65536)]
            modulus=pow(base,65536)+1
            if encode(coeff,base)%modulus!=pow(encode(digits,base),2,modulus):
                raise RuntimeError('full bigint square mismatch')
            lab.report.setdefault('integer_squares',[]).append(dict(n=65536,name=name,base=base,passed=True))
        for name,sha in lab.report['source_sha256'].items():
            if digest(root/name)!=sha:raise RuntimeError('source changed '+name)
        if not all(s['passed'] for s in lab.report['steps']):raise RuntimeError('failed logical gate step')
        lab.report['status']='passed'
    except BaseException as error:
        lab.report.update(status='failed',error=repr(error));raise
    finally:
        lab.report['evidence_sha256']={str(p.relative_to(lab.output)):digest(p) for p in lab.output.iterdir()
            if p.suffix in ('.log','.txt')}
        (lab.output/'report.json').write_text(json.dumps(lab.report,indent=2)+'\n')


if __name__=='__main__':main()
