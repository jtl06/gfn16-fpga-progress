"""Atomic27 R2-root profile gate; standalone artifacts, aethia only."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import resource
import shutil
import signal
import subprocess
import time
from .rns_reference import RADIX,RNSPrime

PINS={
    'rtl/kernel/genefer_root_stream32_r2.sv':'7ca72dbdec54ab0cf7ff0f914b3f764f7751295e4ce60580eee5bd734eef210f',
    'rtl/kernel/genefer_montgomery_mul32_pipe.sv':'e8df84884f8d5a079d358cde9c4d349660df83460312781ace31ff2ce166def9',
    'rtl/kernel/genefer_square_core27_stream.sv':'75eb580540fc6a7939f824182d244123e03e3b780e65e57722352564b145b648',
}
FIELDS=[(104857601,4190109697,45971250,3),(69206017,4225761281,50081300,5),(67239937,4227727361,63576045,10)]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--mutations',action='store_true')
    ap.add_argument('--compile-lock',type=Path,required=True)
    args=ap.parse_args()
    if platform.node()!='aethia':raise RuntimeError('RTL simulation is aethia only')
    resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    root=Path(__file__).resolve().parents[1];out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    source=root/'rtl/kernel/genefer_root_stream32_r2.sv';mul=root/'rtl/kernel/genefer_montgomery_mul32_pipe.sv'
    cpp=root/'rtl/tb/root_stream27_r2.cpp';core=root/'rtl/kernel/genefer_square_core27_stream.sv'
    tracked=[source,mul,cpp,core,Path(__file__),root/'reference/rns_reference.py']
    report=dict(status='running',host=platform.node(),profile='atomic27-radix32-phase0-r2-v1',
        radix_bits=32,fields=[dict(p=p,q=q,r2=r2,generator=g) for p,q,r2,g in FIELDS],
        compile_workers=2,runtime_threads=1,memory_bytes=6<<30,scope_cpu_percent=200,
        build_wall_seconds=180,run_wall_seconds=180,lock_wait_seconds=600,disk_floor_bytes=10<<30,
        sources={str(p.relative_to(root)):sha(p) for p in tracked},steps=[],builds=[],metrics=[],mutants={})
    def run(name,command,reject=None):
        before=time.monotonic();p=subprocess.Popen(list(map(str,command)),cwd=root,text=True,stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,start_new_session=True)
        timeout=False
        try:output,_=p.communicate(timeout=180)
        except subprocess.TimeoutExpired:
            timeout=True;os.killpg(p.pid,signal.SIGKILL);output,_=p.communicate()
        log=out/(name+'.log');log.write_text(output)
        passed=not timeout and (p.returncode==0 if reject is None else p.returncode==1 and reject in output)
        report['steps'].append(dict(name=name,command=list(map(str,command)),returncode=p.returncode,
            passed=passed,seconds=time.monotonic()-before,timed_out=timeout,reject=reject,log=log.name,sha256=sha(log)))
        print(name,'PASS' if passed else 'FAIL',output[-500:],flush=True)
        if not passed:raise RuntimeError(name+' failed')
        return output
    def build(name,aw,field,actual=source):
        p,q,r2,g=FIELDS[field];directory=out/name
        # Waiting for another compiler is not charged to this build's timeout.
        with args.compile_lock.open('a') as lock:
            before=time.monotonic()
            while True:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:
                    if time.monotonic()-before>=600:raise TimeoutError('compile lock wait exceeded600 seconds')
                    time.sleep(.2)
            lock_wait=time.monotonic()-before
            if shutil.disk_usage(out).free<10<<30:raise RuntimeError('no build below10GiB free')
            command=['verilator','--cc','--exe','--build','-j','2','--top-module','genefer_root_stream32_r2',
                     '--Mdir',str(directory),f'-GAW={aw}',f'-GP={p}',f'-GQ={q}',f'-GGENERATOR={g}',str(mul),str(actual),str(cpp)]
            run(name,command)
        exe=directory/'Vgenefer_root_stream32_r2'
        report['builds'].append(dict(name=name,aw=aw,field=field+1,p=p,q=q,generator=g,
            lock_wait_seconds=lock_wait,executable=str(exe),executable_sha256=sha(exe),
            rtl_sources={str(path):sha(path) for path in (mul,actual)},bench_sha256=sha(cpp)))
        return exe
    try:
        if RADIX!=1<<32:raise ValueError('Montgomery radix must remain32 bits')
        for name,digest in PINS.items():
            if sha(root/name)!=digest:raise ValueError('frozen source changed: '+name)
        text=core.read_text()
        for label,column in [('P',0),('Q',1),('R2',2),('G',3)]:
            line=next(line for line in text.splitlines() if f'{label}[0:2]' in line)
            if list(map(int,re.findall(r"32'd(\d+)",line)))!=[field[column] for field in FIELDS]:raise ValueError('atomic profile mismatch '+label)
        for field,(p,q,r2,g) in enumerate(FIELDS):
            prime=RNSPrime(f'atomic27_{field+1}',p,q,RADIX%p,r2,g);prime.validate()
            for aw in range(1,17):prime.primitive_root(2<<aw)
        report['versions']={name:run('version-'+name,command).strip() for name,command in
            [('verilator',['verilator','--version']),('cxx',['g++','--version'])]}
        for field,(p,q,r2,g) in enumerate(FIELDS):
            for aw in (1,2,3,4,16):
                exe=build(f'build-p{field+1}-aw{aw}',aw,field)
                output=run(f'roots-p{field+1}-aw{aw}',[exe,p,g,aw]);result=json.loads(output)
                if result['prime']!=p or result['aw']!=aw or result['radix_bits']!=32 or result['cycles_per_table']!=1<<aw:raise ValueError('bench profile/cycle mismatch')
                report['metrics'].append(dict(field=field+1,**result))
        if args.mutations:
            cases=[
                ('seed-format','R2=cmul(R,R)','R2=R','root mismatch'),
                ('step-format','cmul(R,cpow(PSI,4))','cmul(R2,cpow(PSI,4))','root mismatch'),
                ('inverse-format',"IN=cpow(32'(N),P-2)","IN=cmul(R,cpow(32'(N),P-2))",'root mismatch'),
                ('seed-lane','0: seed=S0[index[1:0]]','0: seed=S0[0]','root mismatch'),
                ('phase-latch','phase_reg<=phase',"phase_reg<=phase+1'b1",'root mismatch'),
                ('done-edge',"int'(index)==N-1","int'(index)==N-2",'done cycle'),
            ]
            original=source.read_text()
            for index,(name,old,new,diagnostic) in enumerate(cases):
                if original.count(old)!=1:raise ValueError('mutation anchor '+name)
                field=index%3;p,q,r2,g=FIELDS[field]
                changed=out/(name+'.sv');changed.write_text(original.replace(old,new))
                report['mutants'][name]=dict(field=field+1,p=p,q=q,generator=g,sha256=sha(changed))
                exe=build('build-mutant-'+name,4,field,changed)
                run('reject-'+name,[exe,p,g,4],diagnostic)
        for name,expected in report['sources'].items():
            if sha(root/name)!=expected:raise ValueError('source changed during gate '+name)
        for entry in report['builds']:
            if sha(Path(entry['executable']))!=entry['executable_sha256']:raise ValueError('executable changed')
        report['status']='passed'
    except BaseException as error:
        report.update(status='failed',error=repr(error));raise
    finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
