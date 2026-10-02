"""Draft one-at-a-time AW16 fusion fault gate. Never run during preparation.

Requires a completed retained AW16 normal control, its independently approved
report SHA, and the approved pre-import source manifest. A fresh full readback
of a directed impulse square precedes a single mutant build. Generic
failures, coefficient-bound errors, assertions, crashes and timeouts are NOT
semantic mutation rejections. All unsuccessful evidence and scratch remain.
"""
import argparse
import fcntl
from functools import lru_cache
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

SOURCE=Path('/home/jtl/gfn-fpga-lab/agent-work/core27-prefetch-r2/snapshot-v1/fpga')
PARENT=SOURCE.parent.parent
LOCK=Path('/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock')
TOP='genefer_square_core27_stream_prefetch_r2'
ROM='rtl/kernel/genefer_root_profile27_r2_rom.sv'
ROM_SHA='cb851bec51f518a71d216d4a993ffa3aa937b8230474c38898b061e7ad42dea6'
MANIFEST_SHA='6404854a21554820b6d365fa6e653352cd5dbe50edc2a913ed99bb1458028c33'
RUNNER='reference/core27_prefetch_r2_regression.py'
RUNNER_SHA='41a328dd0ac581c956c020d74478a5668e0032271c0656057c8de2d84907f50d'
CONTROL_REPORT_SHA='c871241aeca6b8c0e592aa757a785887d495859ddc5381c5e7e0ec055e6d5487'
CONTROL_EXE_SHA='59cafad4e96704fd62f256aafa2c3d14e2d456e72a7b09973cbf96c81772989c'
MUTATIONS={
    'seed-domain':('factor=key==0 ? R2 : IN;','factor=key==0 ? R : IN;'),
    'step-domain':("if(offset==4*LANES)profile_word=cmul(cpow(alpha,32'(4*LANES)),R);",
                   "if(offset==4*LANES)profile_word=cmul(cpow(alpha,32'(4*LANES)),key==0 ? R2 : R);"),
}
FIELDS=('cycles','conversion','roots','ntt','crt','carry','passes','base','profile_before',
        'profile_loads','profile_hits','profile_words','seed_setup','readback')
GiB=1<<30;MiB=1<<20


def require(value,message):
    if not value:raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def digest(data):return hashlib.sha256(data).hexdigest()


def mutation(text,name):
    require(name in MUTATIONS,'unknown fusion mutation')
    require(digest(text.encode())==ROM_SHA,'qualified ROM identity')
    old,new=MUTATIONS[name];require(text.count(old)==1,'ambiguous mutation anchor')
    altered=text.replace(old,new)
    require(altered!=text and altered.replace(new,old)==text,'exact reversible single delta')
    return altered


def radix_integer(words,base):
    @lru_cache(None)
    def power(count):return pow(base,count)
    def rec(lo,hi):
        if hi-lo<=64:
            x=0
            for word in reversed(words[lo:hi]):x=x*base+word
            return x
        mid=(lo+hi)//2
        return rec(lo,mid)+power(mid-lo)*rec(mid,hi)
    return rec(0,len(words))


def directed_case(name):
    """Whole-integer positive oracle and centered-CRT negative witness.

    One impulse avoids random wrong-domain coefficients exceeding the carry
    bound. At index256 the step mutant exercises feedback after all4*64 seeds.
    No RTL bound or bench error criterion is relaxed.
    """
    require(name in MUTATIONS,'unknown fusion mutation')
    n=65536;base=1000000000;index=0 if name=='seed-domain' else 256
    digit=1636 if name=='seed-domain' else 1;label='fusion-'+name+'-impulse'
    digits=[0]*n;digits[index]=digit;expected=[0]*n;expected[2*index]=digit*digit
    modulus=pow(base,n)+1;x=radix_integer(digits,base)%modulus
    require(radix_integer(expected,base)%modulus==x*x%modulus,'fresh independent square oracle')
    primes=(104857601,69206017,67239937);M=1
    for p in primes:M*=p
    R=1<<32
    wrong=(digit*digit*pow(R*R,-1,M))%M if name=='seed-domain' else R*R
    if wrong>M//2:wrong-=M
    require(wrong==(41972152391961575983 if name=='seed-domain' else 18446744073709551616),
            'directed centered CRT witness')
    for p in primes:
        residue=digit*digit*pow(R*R,-1,p)%p if name=='seed-domain' else R*R%p
        require(wrong%p==residue,'independent per-field domain ratio')
    require(0<wrong<(1<<66) and 2*wrong<M and wrong<2*n*(base-1)**2,
            'directed wrong coefficient exceeds proved carry/CRT domain')
    require(wrong%base!=expected[2*index],'directed witness lacks low-digit mismatch')
    payload=(f'{n}\nLOAD {label} {base}\n'+' '.join(map(str,digits))+
             f'\nRUN {label} 0\n'+' '.join(map(str,expected))+'\n').encode()
    return payload,dict(n=n,base=base,bit=0,label=label,expected=expected,
                        input_index=index,input_digit=digit,coefficient_index=2*index,
                        wrong_centered_coefficient=wrong,wrong_first_digit=wrong%base,
                        crt_modulus=M,sha256=digest(payload))


def parse_metric(line):
    pattern=r'^(\S+) '+' '.join(key+r'=(\d+)' for key in FIELDS)+'$'
    match=re.fullmatch(pattern,line);require(match is not None,'metric syntax')
    return dict(zip(FIELDS,map(int,match.groups()[1:])),case=match[1],aw=16,n=65536)


def check_positive(returncode,output,info,archived_row):
    lines=output.splitlines();require(returncode==0,'positive control execution failed')
    require(len(lines)==2 and lines[1]=='PASS n=65536 squares=1 readbacks=1 aborts=0','positive full readback/footer')
    row=parse_metric(lines[0])
    matching=dict(archived_row,case=info['label'],base=info['base'])
    require(row==matching,'fresh directed phase counts differ from retained cold control')
    require(row['case']==info['label'] and row['base']==info['base'] and row['profile_before']==0 and row['readback']==1,'positive case identity')
    require(row['conversion']==4102 and row['cycles']==sum(row[k] for k in ('conversion','roots','ntt','crt','carry')),'positive phase accounting')
    return lines[0]


def expected_rejection(returncode,output,info,positive_metric):
    """Only an actual observed wrong output word is accepted, never rc alone."""
    if type(returncode) is not int or returncode!=1:return False
    lines=output.splitlines()
    if len(lines)!=2 or lines[0]!=positive_metric:return False
    match=re.fullmatch(r'square mismatch '+re.escape(info['label'])+r' index=(\d+) got_low=(\d+) expected=(-?\d+)',lines[1])
    if match is None:return False
    index,got,expected=map(int,match.groups())
    return (0<=index<info['n'] and index==info['coefficient_index'] and 0<=got<1<<32
            and got==info['wrong_first_digit'] and expected==info['expected'][index]
            and got!=(expected&0xffffffff))


def root_witnesses(name):
    require(name in MUTATIONS,'unknown mutation');result=[]
    for p,g in ((104857601,3),(69206017,5),(67239937,10)):
        r=(1<<32)%p;r2=r*r%p;psi=pow(g,(p-1)//131072,p)
        index=0 if name=='seed-domain' else 256
        correct=pow(psi,index,p)*r2%p
        wrong=r if name=='seed-domain' else r2*(pow(psi,256,p)*r2%p)*pow(1<<32,-1,p)%p
        require(correct!=wrong,'mutation root witness is equivalent')
        result.append(dict(p=p,index=index,correct=correct,mutant=wrong))
    return result


def allocated(root):
    result=0
    for directory,_,names in os.walk(root):
        for name in names:
            try:result+=(Path(directory)/name).lstat().st_blocks*512
            except FileNotFoundError:continue
    return result


def execute(name,control,report_sha,manifest_path,out):
    require(__debug__ and socket.gethostname()=='aethia','explicit aethia execution with assertions')
    require(SOURCE.resolve()==SOURCE and LOCK.resolve()==LOCK and LOCK.is_file(),'fixed source/lock identity')
    require(control.resolve()==control and control==PARENT/'aw16-v1' and out.resolve().parent==PARENT and not out.exists(),'scoped control/fresh output')
    require(report_sha==CONTROL_REPORT_SHA and sha(control/'report.json')==report_sha,'approved retained control report')
    require(sha(manifest_path)==MANIFEST_SHA,'approved pre-import manifest')
    control_report=json.loads((control/'report.json').read_text());manifest=json.loads(manifest_path.read_text())
    require(control_report['status']=='passed' and control_report['aw']==16 and control_report['n']==65536 and
            control_report['ntt_lanes']==64 and control_report['model_threads']==1,'complete AW16 normal control required')
    require(control_report['vectors']['squares']==12 and control_report['vectors']['readbacks']==10 and
            len(control_report['metrics'])==12,'complete full-size operation coverage')
    pins=manifest['sources'];require(control_report['sources']==pins and pins[RUNNER]==RUNNER_SHA and pins[ROM]==ROM_SHA,'exact37-source approved control')
    def recheck():
        require(sha(control/'report.json')==report_sha,'control report drift')
        for relative,h in pins.items():
            p=SOURCE/relative
            require(not Path(relative).is_absolute() and '..' not in Path(relative).parts and not p.is_symlink() and sha(p)==h,'source pin drift')
        for relative,h in control_report['artifacts'].items():
            p=control/relative
            require(not Path(relative).is_absolute() and '..' not in Path(relative).parts and not p.is_symlink() and sha(p)==h,'retained artifact drift')
    recheck()  # Verify ALL imported project dependencies before import.
    sys.dont_write_bytecode=True;sys.path.insert(0,str(SOURCE))
    from reference import core27_prefetch_r2_regression as base
    limits=base.execution_limits();require(limits['affinity']==[0,2],'physical CPU0/2 allocation')
    sources=base.check_sources(SOURCE)
    require(len(sources)==16 and sum(p==SOURCE/ROM for p in sources)==1,'compiled source closure')
    tools=[Path(sys.executable).resolve()]+[Path(shutil.which(x)).resolve() for x in ('g++','verilator')]
    tool_pins={str(p):sha(p) for p in tools};require(tool_pins==control_report['tool_executable_sha256'],'matching control toolchain')
    resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(6*GiB,6*GiB))
    out.mkdir();scratch=Path(tempfile.mkdtemp(prefix='gfn16-prefetch-r2-fault-',dir='/dev/shm'));os.chmod(scratch,0o700)
    tmp=scratch/'tmp';tmp.mkdir()
    report=dict(status='running',scope='One AW16 phase0 fusion mutation, directed cold impulse square only',mutation=name,
                harness_sha256=sha(__file__),control_root=str(control),control_report_sha256=report_sha,manifest_sha256=MANIFEST_SHA,
                sources=pins,limits=limits,tool_executable_sha256=tool_pins,steps=[],artifacts={},scratch=str(scratch),
                compiler_temporary_directory=str(tmp),durable_reservation_bytes=32*MiB,durable_free_floor_bytes=10*GiB,
                scratch_reservation_bytes=512*MiB,scratch_free_floor_bytes=2*GiB,host_memory_floor_bytes=4*GiB,
                command_timeout_seconds=1800,root_witnesses=root_witnesses(name),cleanup='Nothing deleted; preserve failures and scratch.')
    def remember(path):report['artifacts'][str(path.relative_to(out))]=sha(path)
    def save():(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def guard():
        require(shutil.disk_usage(out).free>=10*GiB+max(0,32*MiB-allocated(out)),'durable reservation/floor')
        require(shutil.disk_usage(scratch).free>=2*GiB+max(0,512*MiB-allocated(scratch)),'tmpfs reservation/floor')
        mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
        require(int(mem['MemAvailable'].split()[0])*1024>=4*GiB,'host memory floor')
    env={k:v for k,v in os.environ.items() if k not in ('MAKEFLAGS','MFLAGS','CFLAGS','CXXFLAGS','CPPFLAGS',
        'LDFLAGS','CC','CXX','AR','OBJCACHE','OPT_FAST','OPT_SLOW','OPT_GLOBAL','TMPDIR','TMP','TEMP') and not k.startswith('NTT_')}
    env.update(TMPDIR=str(tmp),TMP=str(tmp),TEMP=str(tmp))
    def run(label,argv,allow_semantic_exit=False):
        guard();log=out/(label+'.log');begin=time.monotonic();failure=None
        with log.open('x') as stream:
            proc=subprocess.Popen(argv,cwd=SOURCE,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                while proc.poll() is None:
                    guard();require(time.monotonic()-begin<1800,'command timeout');time.sleep(1)
            except BaseException as error:
                failure=error
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                proc.wait()
        remember(log);report['steps'].append(dict(name=label,command=argv,returncode=proc.returncode,
            seconds=time.monotonic()-begin,error=repr(failure) if failure else None,log=log.name,sha256=sha(log)));save()
        if failure:raise failure
        require(proc.returncode==0 or (allow_semantic_exit and proc.returncode==1),'unexpected process failure')
        guard();return proc.returncode,log.read_text()
    try:
        guard();recheck();save()
        for original,destination in ((control/'report.json','control-report.json'),(manifest_path,'approved-manifest.json')):
            copied=out/destination;shutil.copyfile(original,copied);require(sha(copied)==sha(original),'provenance copy');remember(copied)
        for tool,key in (('verilator','tool_version'),('g++','compiler_version')):
            _,text=run(tool+'-version',[tool,'--version']);require(text.strip()==control_report[key],'tool version differs');report[key]=text.strip()
        vector=control/'vectors-aw16.txt';require(sha(vector)==control_report['vectors']['sha256'],'original control vector pin')
        payload,info=directed_case(name);piece=out/'directed-cold-aw16.txt';piece.write_bytes(payload);remember(piece)
        report['case']={k:v for k,v in info.items() if k!='expected'}
        old_exe=control/('V'+TOP);require(sha(old_exe)==control_report['executable_sha256']==CONTROL_EXE_SHA,'retained executable identity')
        report['control_executable_sha256']=sha(old_exe)
        _,text=run('control-probe',[str(old_exe),'--runtime-probe']);base.check_probe(text,1)
        rc,text=run('fresh-control',[str(old_exe),str(piece),'profile'])
        metric=check_positive(rc,text,info,control_report['metrics'][0]);report['fresh_control_metric']=parse_metric(metric)
        changed=out/'mutant-root-profile27-r2.sv';changed.write_text(mutation((SOURCE/ROM).read_text(),name));remember(changed)
        report['mutation_delta']=dict(ancestor_sha256=ROM_SHA,mutant_sha256=sha(changed),old=MUTATIONS[name][0],new=MUTATIONS[name][1])
        with tarfile.open(out/'sources.tar.gz','x:gz') as tar:
            for relative in pins:tar.add(SOURCE/relative,arcname=relative,recursive=False)
            tar.add(Path(__file__),arcname='tools/run_prefetch_r2_faults.py',recursive=False)
            tar.add(changed,arcname=changed.name,recursive=False)
        remember(out/'sources.tar.gz')
        build=scratch/'build';selected=[changed if p==SOURCE/ROM else p for p in sources]
        command=['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',TOP,'-GAW=16','-GNTT_LANES=64',
                 '--Mdir',str(build),*map(str,selected),str(SOURCE/'rtl/tb/square_core27_stream_prefetch_r2_threaded.cpp')]
        with LOCK.open('r') as lock:
            deadline=time.monotonic()+1800
            while True:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:guard();require(time.monotonic()<deadline,'compile lock timeout');time.sleep(1)
            recheck();run('build-mutant',command)
        exe=out/('V'+TOP+'-'+name);shutil.copy2(build/('V'+TOP),exe);remember(exe)
        require(sha(exe)==sha(build/('V'+TOP)) and sha(exe)!=sha(old_exe),'mutant executable copy/identity')
        report['mutant_executable_sha256']=sha(exe)
        generated={p.name:sha(p) for p in build.iterdir() if p.is_file() and p.suffix in ('.cpp','.h','.mk','.dat')}
        with tarfile.open(out/'generated-sources.tar.gz','x:gz') as tar:
            for relative in sorted(generated):tar.add(build/relative,arcname=relative,recursive=False)
        remember(out/'generated-sources.tar.gz');report['generated_source_sha256']=generated
        _,text=run('mutant-probe',[str(exe),'--runtime-probe']);base.check_probe(text,1)
        rc,text=run('targeted-mutant',[str(exe),str(piece),'profile'],True)
        require(expected_rejection(rc,text,info,metric),'inconclusive: no exact targeted square-mismatch witness')
        recheck();guard();require(all(sha(p)==h for p,h in tool_pins.items()),'tool drift')
        require(all(sha(out/p)==h for p,h in report['artifacts'].items()),'durable evidence drift')
        report.update(status='passed_targeted_semantic_rejection',limitation='One cold square and one source delta; no full mutation/profile/PRP/physical qualification.')
    except BaseException as error:report.update(status='failed_or_inconclusive',error=repr(error));raise
    finally:save()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--mutant',choices=tuple(MUTATIONS),required=True)
    parser.add_argument('--control',type=Path,required=True);parser.add_argument('--control-report-sha',required=True)
    parser.add_argument('--manifest',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();require(args.execute,'explicit --execute required; draft must be reviewed first')
    execute(args.mutant,args.control,args.control_report_sha,args.manifest,args.output)
