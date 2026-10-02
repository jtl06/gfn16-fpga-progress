"""One AW7 host-quarter RTL mutant; compile in private tmpfs on aethia only.

The frozen passing source tree/model are read-only. Durable evidence includes
sources, compiler output, generated-source archive, executable and both runs.
No scratch deletion is performed by this tool.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import re
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import time

SOURCE=Path('/home/jtl/gfn-fpga-lab/agent-work/square-core27-rootpipe/profiles/small-v1/fpga')
CONTROL=SOURCE/'artifacts/aw7-v1'
OUTPUT=Path('/home/jtl/gfn-fpga-lab/agent-work/square-core27-rootpipe/faults/host-quarter-v1')
REPORT_SHA='cc0a83f3b698923b8f9a1e2c966cee1fe73d8405f67930530248e422dcc36525'
HELPER_SHA='57e506800da41444495d7b6171336936f0a8a69ed695a6342acb6d698c0f2420'
HOST='genefer_ntt_banked27_host_rootpipe_engine.sv'
TOP='genefer_square_core27_stream_rootpipe'
GiB=1<<30
MiB=1<<20
LOCK=Path('/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock')


def require(value,message):
    if not value:raise RuntimeError(message)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def mutation(text):
    old='read_group<=host_group;'
    require(text.count(old)==1,'ambiguous host-quarter mutation')
    return text.replace(old,'read_group<=0;')


def expected_rejection(returncode,output):
    diagnostic = re.compile(
        r'^\[\d+\] %Fatal: (?:[^\n:]+/)?genefer_square_core27_stream_rootpipe\.sv:288: '
        r'Assertion failed in TOP\.genefer_square_core27_stream_rootpipe\.unnamedblk3: residue mask skew$',
        re.M)
    return returncode in (1,-6,134) and len(diagnostic.findall(output))==1 and 'PASS n=' not in output


def allocated(root):
    result=0
    for directory,_,names in os.walk(root):
        for name in names:
            try:result+=(Path(directory)/name).lstat().st_blocks*512
            except FileNotFoundError:continue
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    require(args.execute and __debug__ and socket.gethostname()=='aethia','explicit aethia execution with assertions required')
    require(SOURCE.resolve()==SOURCE and LOCK.resolve()==LOCK and LOCK.is_file(),'fixed source/lock identity')
    require(sha(CONTROL/'report.json')==REPORT_SHA,'passing AW7 report changed')
    require(sha(SOURCE/'reference/square_core27_rootpipe_regression.py')==HELPER_SHA,'reviewed helper changed')
    sys.dont_write_bytecode=True
    control=json.loads((CONTROL/'report.json').read_text())
    require(control['status']=='passed' and control['aw']==[7] and control['ntt_lanes']==64,'wrong control profile')
    pins=control['sources']
    def recheck():
        require(sha(CONTROL/'report.json')==REPORT_SHA,'control report changed')
        require(all(sha(SOURCE/name)==value for name,value in pins.items()),'frozen source changed')
        require(all(sha(CONTROL/name)==value for name,value in control['artifacts'].items()),'control evidence changed')
    recheck()  # Pin every imported project dependency before executing it.
    sys.path.insert(0,str(SOURCE))
    from reference import square_core27_rootpipe_regression as base
    limits=base.execution_limits()
    require(limits['affinity']==[0,2],'require reviewed physical CPUs0/2')
    sources=base.check_sources(SOURCE)
    tool_paths=[Path(sys.executable).resolve()]
    for name in ('g++','verilator'):
        found=shutil.which(name);require(found is not None,'missing tool: '+name)
        tool_paths.append(Path(found).resolve())
    tool_pins={str(path):sha(path) for path in tool_paths}
    require(tool_pins==control['tool_executable_sha256'],'toolchain differs from passing control')
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_AS,(6*GiB,6*GiB))
    require(not OUTPUT.exists(),'fresh durable output required')
    OUTPUT.mkdir(parents=True)
    scratch=Path(tempfile.mkdtemp(prefix='gfn16-rootpipe-host-fault-',dir='/dev/shm'))
    os.chmod(scratch,0o700)
    tmp=scratch/'tmp';tmp.mkdir()
    report=dict(status='running',scope='AW7 host-quarter integration mutant only',
        tool_sha256=sha(__file__),control_report_sha256=REPORT_SHA,source_sha256=pins,
        scratch=str(scratch),durable_output=str(OUTPUT),limits=limits,steps=[],artifacts={},
        tool_executable_sha256=tool_pins,python_version=sys.version,
        scratch_reservation_bytes=512*MiB,scratch_free_floor_bytes=2*GiB,
        durable_reservation_bytes=32*MiB,durable_free_floor_bytes=10*GiB,
        host_memory_floor_bytes=4*GiB,cleanup='No scratch deletion; archive and verify before cleanup.')
    def guard():
        require(shutil.disk_usage(OUTPUT).free>=10*GiB+max(0,32*MiB-allocated(OUTPUT)),'durable disk reservation/floor')
        require(shutil.disk_usage(scratch).free>=2*GiB+max(0,512*MiB-allocated(scratch)),'tmpfs reservation/floor')
        mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
        require(int(mem['MemAvailable'].split()[0])*1024>=4*GiB,'host available memory floor')
    env={k:v for k,v in os.environ.items() if k not in (
        'MAKEFLAGS','MFLAGS','CFLAGS','CXXFLAGS','CPPFLAGS','LDFLAGS','CC','CXX','AR',
        'OBJCACHE','OPT_FAST','OPT_SLOW','OPT_GLOBAL','TMPDIR','TMP','TEMP') and not k.startswith('NTT_')}
    env.update(TMPDIR=str(tmp),TMP=str(tmp),TEMP=str(tmp))
    def remember(path):report['artifacts'][str(path.relative_to(OUTPUT))]=sha(path)
    def save():
        (OUTPUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def run(name,command,reject=False):
        guard();log=OUTPUT/(name+'.log');before=time.monotonic();failure=None
        with log.open('x') as stream:
            process=subprocess.Popen(command,cwd=SOURCE,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                while process.poll() is None:
                    guard();require(time.monotonic()-before<900,'command timeout');time.sleep(1)
            except BaseException as error:
                failure=error
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                process.wait()
        remember(log);output=log.read_text()
        report['steps'].append(dict(name=name,command=command,returncode=process.returncode,
            seconds=time.monotonic()-before,log=log.name,sha256=sha(log),expected_rejection=reject,
            failure=repr(failure) if failure else None));save()
        print(name,process.returncode,flush=True)
        if failure:raise failure
        guard()
        if reject:require(expected_rejection(process.returncode,output),'mutant did not hit the exact expected semantic check')
        else:require(process.returncode==0,name+' failed')
        return output
    try:
        guard()
        report['tool_version']=run('verilator-version',['verilator','--version']).strip()
        report['compiler_version']=run('compiler-version',['g++','--version']).strip()
        require(report['tool_version']==control['tool_version'],'Verilator version changed')
        require(report['compiler_version']==control['compiler_version'],'compiler version changed')
        vector=OUTPUT/'vectors-aw7.txt';shutil.copyfile(CONTROL/'aw7-segment0.txt',vector)
        require(sha(vector)==control['artifacts']['aw7-segment0.txt'],'control vector copy');remember(vector)
        host=SOURCE/'rtl/kernel'/HOST;changed=OUTPUT/'mutant-host-quarter.sv'
        changed.write_text(mutation(host.read_text()));remember(changed)
        report['mutation']=dict(ancestor=HOST,ancestor_sha256=sha(host),mutant_sha256=sha(changed),
            old='read_group<=host_group;',new='read_group<=0;',expected='residue mask skew')
        with tarfile.open(OUTPUT/'sources.tar.gz','x:gz') as tar:
            for name in pins:tar.add(SOURCE/name,arcname=name,recursive=False)
            tar.add(Path(__file__),arcname='tools/run_rootpipe_host_fault.py',recursive=False)
            tar.add(changed,arcname=changed.name,recursive=False)
        remember(OUTPUT/'sources.tar.gz')
        old_exe=CONTROL/f'build-aw7/V{TOP}'
        report['control_executable_sha256']=sha(old_exe)
        base.check_probe(run('control-probe',[str(old_exe),'--runtime-probe']),1)
        rows=base.validate_output(run('control',[str(old_exe),str(vector),'cache']),vector.read_text(),7)
        require(rows==control['metrics'],'fresh control counters differ from archived passing gate')
        report['control_metrics']=rows
        build=scratch/'build';wrapper=SOURCE/'rtl/tb/square_core27_stream_rootpipe_threaded.cpp'
        selected=[changed if path==host else path for path in sources]
        command=['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',TOP,
            '-GAW=7','-GNTT_LANES=64','--Mdir',str(build),*map(str,selected),str(wrapper)]
        with LOCK.open('r') as lock:
            deadline=time.monotonic()+900
            while True:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:
                    guard();require(time.monotonic()<deadline,'compile lock timeout');time.sleep(1)
            recheck();run('build-mutant',command)
        exe=build/f'V{TOP}';copied=OUTPUT/f'V{TOP}-host-quarter-mutant'
        shutil.copy2(exe,copied);require(sha(copied)==sha(exe),'mutant executable copy');remember(copied)
        require(sha(copied)!=sha(old_exe),'mutant executable did not change')
        report['mutant_executable_sha256']=sha(copied)
        # Generated code and makefiles are durable, without retaining disposable PCH/object caches.
        generated={p.name:sha(p) for p in build.iterdir() if p.is_file() and p.suffix in ('.cpp','.h','.mk','.dat')}
        with tarfile.open(OUTPUT/'generated-sources.tar.gz','x:gz') as tar:
            for name in sorted(generated):tar.add(build/name,arcname=name,recursive=False)
        report['generated_source_sha256']=generated;remember(OUTPUT/'generated-sources.tar.gz')
        report['compiler_temporary_directory']=str(tmp)
        base.check_probe(run('mutant-probe',[str(copied),'--runtime-probe']),1)
        run('reject-host-quarter',[str(copied),str(vector),'cache'],reject=True)
        recheck();guard()
        require(all(sha(path)==value for path,value in tool_pins.items()),'toolchain changed during run')
        require(all(sha(OUTPUT/name)==value for name,value in report['artifacts'].items()),'durable artifacts changed')
        report['status']='passed';report['limitation']='One targeted integration fault only; no new clock, fit, PRP or board claim.'
    except BaseException as error:
        report.update(status='failed_or_incomplete',error=repr(error));raise
    finally:save()


if __name__=='__main__':main()
