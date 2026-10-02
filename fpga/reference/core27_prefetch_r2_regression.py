"""Isolated normal RTL gate for format2 fusion; simulation on aethia only.

Build scratch is private tmpfs. Durable sources, executable, generated source,
vectors and logs remain on disk. A profile pass is not full qualification.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import time

from .core27_prefetch_r2_structure import ANCESTORS, NAMES as RENAMES, validate_files
from .core27_prefetch_r2_bench import validate_bench_files
from .square_core27_stream_prefetch_regression import NAMES as BASE_NAMES, write_vectors as original_vectors
from .square_core27_rootpipe_regression import execution_limits, allocated_bytes, check_probe
from .square_core27_recovery import segments

TOP='genefer_square_core27_stream_prefetch_r2'
SOURCE=Path('/home/jtl/gfn-fpga-lab/agent-work/core27-prefetch-r2/snapshot-v1/fpga')
DESTINATION=SOURCE.parent.parent
LOCK=Path('/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock')
GiB=1<<30
MiB=1<<20
FIELDS=('cycles','conversion','roots','ntt','crt','carry','passes','base','profile_before',
        'profile_loads','profile_hits','profile_words','seed_setup','readback')

def require(value,message):
    if not value:raise ValueError(message)

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def write_vectors(path,aw,seed,prefix_carry=True):
    info=original_vectors(path,aw,seed,prefix_carry)
    n=1<<aw
    extra=[f'BADDIGIT_AT {base} {base} {index}' for base in (2*n+5,1000000000)
        for index in sorted({max(0,n-16),n-1})]
    path.write_text(path.read_text()+'\n'.join(extra)+'\n')
    info['fusion_invalid_final_row_cases']=len(extra);info['sha256']=sha(path)
    return info

def check_sources(root):
    validate_files(root);validate_bench_files(root)
    sources=[root/'rtl/kernel'/(RENAMES.get(name,name)+'.sv') for name in BASE_NAMES]
    modules=[]
    for path in sources:modules+=re.findall(r'^module\s+(\w+)',path.read_text(),re.M)
    require(len(modules)==len(set(modules)),'duplicate modules')
    require(TOP in modules and 'genefer_ntt_difdit_butterfly27' in modules,'missing top/helper')
    return sources

def source_inputs(root,sources):
    paths=set(sources)
    paths.update(root/'rtl/kernel'/(name+'.sv') for name in ANCESTORS)
    paths.update(root/'rtl/tb'/name for name in ('square_core27_stream_prefetch.cpp',
        'square_core27_stream_prefetch_threaded.cpp','square_core27_stream_prefetch_r2.cpp',
        'square_core27_stream_prefetch_r2_threaded.cpp'))
    paths.update(Path(m.__file__).resolve() for m in tuple(sys.modules.values())
        if getattr(m,'__file__',None) and Path(m.__file__).resolve().is_relative_to(root/'reference'))
    paths.add(Path(__file__).resolve())
    return {str(path.relative_to(root)):sha(path) for path in sorted(paths)}

def ntt_schedule(aw):
    n=1<<aw;groups=(n+127)//128
    setup=0
    for reverse in (False,True):
        for index in range(aw):
            stage=aw-1-index if reverse else index
            period=1 if stage<7 else 1<<(stage-6)
            seeds=min(4,groups,period)*min(64,1<<stage)
            setup+=seeds+4 if index==0 else 1+max(0,seeds-groups-4)
    setup+=2*(min(4,(n+63)//64)*min(64,n)+4)
    return 3*((n+63)//64+7)+2*aw*(groups+8)+setup+10,setup

def validate_output(output,vectors,aw):
    commands=[line.split() for line in vectors.splitlines() if line.startswith(('RUN ','RUN_NOREAD ','ABORT '))]
    runs=[row for row in commands if row[0]!='ABORT']
    n=1<<aw;ntt,setup=ntt_schedule(aw);profile_words=(2*aw+2)*257
    pattern=re.compile(r'^(\S+) '+' '.join(key+r'=(\d+)' for key in FIELDS)+'$')
    rows=[]
    for line in output.splitlines():
        if ' cycles=' not in line:continue
        match=pattern.fullmatch(line);require(match is not None,'malformed metric')
        row=dict(zip(FIELDS,map(int,match.groups()[1:])),case=match[1],aw=aw,n=n)
        require(row['cycles']==sum(row[k] for k in ('conversion','roots','ntt','crt','carry')),'phase accounting')
        require(row['conversion']==(n+15)//16+6,'fusion conversion latency')
        require((row['ntt'],row['seed_setup'])==(ntt,setup),'NTT/seed schedule')
        require(row['profile_before'] in (0,1),'profile cache state')
        warm=bool(row['profile_before'])
        require((row['profile_loads'],row['profile_hits'],row['profile_words'],row['roots'])==
            ((0,1,0,0) if warm else (1,0,profile_words,profile_words+5)),'profile accounting')
        require(row['crt']==(n+15)//16+62+max(0,97-row['roots']-row['ntt']),'carry setup overlap')
        require(2*n+4<row['base']<=1000000000,'base domain')
        rows.append(row)
    require([r['case'] for r in rows]==[r[1] for r in runs],'transaction order/coverage')
    require(len({r['case'] for r in rows})==len(rows),'duplicate cases')
    require([r['readback'] for r in rows]==[int(r[0]=='RUN') for r in runs],'readback coverage')
    footer=f'PASS n={n} squares={len(runs)} readbacks={sum(r[0]=="RUN" for r in runs)} aborts={sum(r[0]=="ABORT" for r in commands)}'
    require(output.splitlines().count(footer)==1,'terminal coverage footer')
    return rows

def prepare(out):
    root=Path(__file__).resolve().parents[1];pins=source_inputs(root,check_sources(root))
    out.mkdir(parents=True,exist_ok=False)
    archive=out/'source.tar.gz'
    with tarfile.open(archive,'x:gz') as tar:
        for name,digest in pins.items():
            path=root/name;require(not path.is_symlink() and sha(path)==digest,'source drift/link')
            tar.add(path,arcname='fpga/'+name,recursive=False)
    manifest={'status':'prepared_not_executed','sources':pins,'archive_sha256':sha(archive),
        'target':str(SOURCE.parent),'limitation':'Source snapshot, not RTL validation.'}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'files':len(pins),'bytes':archive.stat().st_size,'sha256':sha(archive)}))

def execute(aw,out):
    require(__debug__ and socket.gethostname()=='aethia','aethia with assertions required')
    root=Path(__file__).resolve().parents[1]
    require(root==SOURCE and root.resolve()==SOURCE,'isolated snapshot identity')
    require(out.resolve().parent==DESTINATION and not out.exists(),'fresh output in experiment directory')
    require(LOCK.resolve()==LOCK and LOCK.is_file(),'shared compiler lock identity')
    limits=execution_limits();require(limits['affinity']==[0,2],'physical CPU0/2 allocation')
    sources=check_sources(root);pins=source_inputs(root,sources)
    resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(6*GiB,6*GiB))
    out.mkdir();scratch=Path(tempfile.mkdtemp(prefix='gfn16-prefetch-r2-',dir='/dev/shm'));os.chmod(scratch,0o700)
    tmp=scratch/'tmp';tmp.mkdir()
    report=dict(status='running',aw=aw,n=1<<aw,ntt_lanes=64,model_threads=1,compile_workers=2,
        scope='Single-profile normal format2 whole-core simulation',sources=pins,limits=limits,
        scratch=str(scratch),compiler_temporary_directory=str(tmp),steps=[],metrics=[],segments=[],artifacts={},
        scratch_reservation_bytes=512*MiB,scratch_free_floor_bytes=2*GiB,
        durable_reservation_bytes=64*MiB,durable_free_floor_bytes=10*GiB,host_memory_floor_bytes=4*GiB,
        command_timeout_seconds=1800,cleanup='Scratch retained; no deletion.',
        limitation='Not a complete multi-profile or mutation qualification, fit, clock, board or full PRP result.')
    def guard():
        require(shutil.disk_usage(out).free>=10*GiB+max(0,64*MiB-allocated_bytes(out)),'durable disk reservation/floor')
        require(shutil.disk_usage(scratch).free>=2*GiB+max(0,512*MiB-allocated_bytes(scratch)),'tmpfs reservation/floor')
        mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
        require(int(mem['MemAvailable'].split()[0])*1024>=4*GiB,'host memory floor')
    def recheck():require(all(sha(root/name)==digest for name,digest in pins.items()),'source drift')
    def remember(path):report['artifacts'][str(path.relative_to(out))]=sha(path)
    def save():(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    env={k:v for k,v in os.environ.items() if k not in ('MAKEFLAGS','MFLAGS','CFLAGS','CXXFLAGS',
        'CPPFLAGS','LDFLAGS','CC','CXX','AR','OBJCACHE','OPT_FAST','OPT_SLOW','OPT_GLOBAL','TMPDIR','TMP','TEMP')
        and not k.startswith('NTT_')}
    env.update(TMPDIR=str(tmp),TMP=str(tmp),TEMP=str(tmp))
    def run(name,argv):
        guard();log=out/(name+'.log');before=time.monotonic();failure=None
        with log.open('x') as stream:
            child=subprocess.Popen(argv,cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                while child.poll() is None:
                    guard();require(time.monotonic()-before<1800,'command timeout');time.sleep(1)
            except BaseException as error:
                failure=error
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                child.wait()
        remember(log);report['steps'].append(dict(name=name,command=argv,returncode=child.returncode,
            seconds=time.monotonic()-before,error=repr(failure) if failure else None,log=log.name,sha256=sha(log)))
        save();print(name,child.returncode,flush=True)
        if failure:raise failure
        require(child.returncode==0,name+' failed');guard();return log.read_text()
    try:
        guard();recheck()
        tool_paths=[Path(sys.executable).resolve()]
        for name in ('g++','verilator'):
            found=shutil.which(name);require(found is not None,'missing '+name);tool_paths.append(Path(found).resolve())
        report['tool_executable_sha256']={str(path):sha(path) for path in tool_paths}
        report['python_version']=sys.version
        report['tool_version']=run('verilator-version',['verilator','--version']).strip()
        report['compiler_version']=run('compiler-version',['g++','--version']).strip()
        with tarfile.open(out/'sources.tar.gz','x:gz') as tar:
            for name in pins:tar.add(root/name,arcname=name,recursive=False)
        remember(out/'sources.tar.gz')
        vector=out/f'vectors-aw{aw}.txt';report['vectors']=write_vectors(vector,aw,20260929,True);remember(vector)
        require(sha(vector)==report['vectors']['sha256'],'vector generation hash');guard()
        build=scratch/'build';wrapper=root/'rtl/tb/square_core27_stream_prefetch_r2_threaded.cpp'
        command=['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',TOP,
            f'-GAW={aw}','-GNTT_LANES=64','--Mdir',str(build),*map(str,sources),str(wrapper)]
        with LOCK.open('r') as lock:
            deadline=time.monotonic()+1800
            while True:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:guard();require(time.monotonic()<deadline,'compile lock timeout');time.sleep(1)
            recheck();run('build',command)
        exe=out/('V'+TOP);shutil.copy2(build/exe.name,exe);remember(exe)
        require(sha(exe)==sha(build/exe.name),'durable executable copy')
        report['executable_sha256']=sha(exe);report['executable']=str(exe)
        generated={p.name:sha(p) for p in build.iterdir() if p.is_file() and p.suffix in ('.cpp','.h','.mk','.dat')}
        with tarfile.open(out/'generated-sources.tar.gz','x:gz') as tar:
            for name in sorted(generated):tar.add(build/name,arcname=name,recursive=False)
        report['generated_source_sha256']=generated;remember(out/'generated-sources.tar.gz')
        check_probe(run('probe',[str(exe),'--runtime-probe']),1)
        raw=vector.read_bytes()
        if aw==16:_,parts,_,_=segments(raw)
        else:parts=[(1,len(raw.splitlines()),raw)]
        for index,(start,end,payload) in enumerate(parts):
            piece=out/f'segment{index}.txt';piece.write_bytes(payload);remember(piece)
            report['segments'].append(dict(index=index,start=start,end=end,sha256=sha(piece)))
            output=run(f'test-segment{index}',[str(exe),str(piece),'profile'])
            report['metrics']+=validate_output(output,payload.decode(),aw)
            require(sha(exe)==report['executable_sha256'],'model changed during test')
        require(len(report['metrics'])==report['vectors']['squares'],'operation coverage')
        require(sum(m['readback'] for m in report['metrics'])==report['vectors']['readbacks'],'readback coverage')
        recheck();guard()
        require(all(sha(out/name)==digest for name,digest in report['artifacts'].items()),'durable artifact drift')
        require(all(sha(path)==digest for path,digest in report['tool_executable_sha256'].items()),'toolchain drift')
        report['status']='passed'
    except BaseException as error:report.update(status='failed_or_incomplete',error=repr(error));raise
    finally:save()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',type=Path);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--aw',type=int,choices=(1,5,7,16));parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.prepare:
        require(not args.execute and args.aw is None and args.output is None,'exclusive preparation mode')
        prepare(args.prepare.resolve())
    else:
        require(args.execute and args.aw is not None and args.output is not None,'explicit profile/output execution')
        execute(args.aw,args.output.resolve())

if __name__=='__main__':main()
