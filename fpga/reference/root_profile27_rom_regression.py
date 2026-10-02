"""Fixed profile ROM vs frozen independent pow producer; RTL runs on aethia."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import tarfile
import time
from .ntt27_generated_regression import profile,PRIMES

REFERENCE_FILES=('ntt27_generated_regression.py','engine_regression.py',
    'ntt_difdit_regression.py','ntt27_experiment.py','ntt_cached_regression.py',
    'ntt_stream_regression.py','ntt_parallel_regression.py','gfn_reference.py',
    'rtl_vectors.py','rns_reference.py')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--compile-lock',type=Path,required=True)
    args=parser.parse_args()
    if platform.node().split('.')[0]!='aethia':raise SystemExit('RTL restricted to aethia')
    root=Path(__file__).resolve().parents[1]
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    rtl=root/'rtl/kernel/genefer_root_profile27_rom.sv';cpp=root/'rtl/tb/root_profile27_rom.cpp'
    files=[rtl,cpp,Path(__file__)]+[root/'reference'/name for name in REFERENCE_FILES]
    hashes={str(p.relative_to(root)):sha(p) for p in files}
    report=dict(status='running',sources=hashes,steps=[],builds=[],vectors=[],
                scope='Fixed-size profile producer only; no generated NTT/core integration or ROM inference claim.')
    report['verilator_version']=subprocess.check_output(['verilator','--version'],text=True).strip()
    with tarfile.open(out/'source-snapshot.tar.gz','w:gz') as archive:
        for p in files:archive.add(p,arcname=str(p.relative_to(root)))
    report['source_archive_sha256']=sha(out/'source-snapshot.tar.gz')
    def save():(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def run(name,command,diagnostic=None):
        start=time.monotonic();proc=subprocess.Popen(command,cwd=root,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
        timed_out=False
        try:log,_=proc.communicate(timeout=1200)
        except subprocess.TimeoutExpired:
            timed_out=True;os.killpg(proc.pid,signal.SIGKILL);log,_=proc.communicate()
        path=out/(name+'.log');path.write_text(log)
        passed=not timed_out and (proc.returncode==0 if diagnostic is None else proc.returncode==1 and diagnostic in log)
        report['steps'].append(dict(name=name,command=command,returncode=proc.returncode,
            passed=passed,timed_out=timed_out,seconds=time.monotonic()-start,log_sha256=sha(path),diagnostic=diagnostic))
        save();print(name,'PASS' if passed else 'FAIL',flush=True)
        if not passed:raise RuntimeError(name+': '+log[-2000:])
    def case(name,source,field,aw,lanes,diagnostic=None):
        if shutil.disk_usage(out).free<10<<30:raise RuntimeError('free disk below10GiB')
        prime=PRIMES[field]
        vector=out/(name+'.txt');words=profile(field,aw,aw,lanes)
        vector.write_text('\n'.join(map(str,words))+'\n')
        report['vectors'].append(dict(name=name,words=len(words),field=field+1,aw=aw,lanes=lanes,sha256=sha(vector)))
        build=out/('build-'+name)
        run('build-'+name,['flock','--timeout','600',str(args.compile_lock),
            'verilator','--cc','--exe','--build','-j','2','--top-module','genefer_root_profile27_rom',
            '--Mdir',str(build),f'-GAW={aw}',f'-GLANES={lanes}',f'-GP={prime.p}',
            f'-GGENERATOR={prime.generator}',str(source),str(cpp)])
        exe=build/'Vgenefer_root_profile27_rom'
        report['builds'].append(dict(name=name,source_sha256=sha(source),executable=str(exe),executable_sha256=sha(exe)))
        run(name,[str(exe),str(vector)],diagnostic)
    save()
    try:
        for field in range(3):
            for aw in (1,4,10,16):case(f'p{field+1}-aw{aw}-l64',rtl,field,aw,64)
            case(f'p{field+1}-aw16-l16',rtl,field,16,16)
        mutations=[
            ('twist-format','factor=key==0 ? R : IN;',"factor=key==0 ? 32'd1 : IN;",'profile value mismatch'),
            ('post-format','factor=key==0 ? R : IN;','factor=R;','profile value mismatch'),
            ('inverse-sign','alpha=key>AW ? IOMEGA : OMEGA;','alpha=OMEGA;','profile value mismatch'),
            ('lane-insert','(lane>>coordinate)<<(coordinate+1)','(lane>>coordinate)<<coordinate','profile value mismatch'),
            ('recurrence-step','1<<(K+h+1)','1<<(K+h)','profile value mismatch'),
            ('address',"word_addr<=16'(index);","word_addr<=16'(index)^16'd1;",'ordered address mismatch'),
            ('done-edge',"index==PAW'(WORDS-1)","index==PAW'(WORDS-2)",'done/busy edge mismatch'),
            ('reset-valid','busy<=0;done<=0;word_valid<=0;','busy<=0;done<=0;word_valid<=1;','reset leak'),
        ]
        content=rtl.read_text()
        for index,(name,old,new,diagnostic) in enumerate(mutations):
            if content.count(old)!=1:raise ValueError('mutation anchor '+name)
            directory=out/('mutation-'+name);directory.mkdir()
            altered=directory/rtl.name;altered.write_text(content.replace(old,new))
            case('reject-'+name,altered,index%3,10,64,diagnostic)
        if hashes!={str(p.relative_to(root)):sha(p) for p in files}:raise ValueError('sources changed')
        report.update(status='passed',sources_rechecked=True)
    except BaseException as exc:report.update(status='failed',error=repr(exc));raise
    finally:save()


if __name__=='__main__':main()
