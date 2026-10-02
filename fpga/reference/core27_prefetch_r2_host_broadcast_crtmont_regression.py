"""Prepare/explicitly execute isolated broadcast+Montgomery-CRT normal gates.

Direct-script execution only: approved manifest and every source are checked
before importing any project module. Frozen R2 vectors and all non-CRT counters are reused;
only CRT and total cycle counts must drop exactly45. No automatic dispatch.
"""
import argparse
import fcntl
import hashlib
import importlib
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

TOP='genefer_square_core27_stream_prefetch_r2_host_broadcast_crtmont'
SOURCE=Path('/home/jtl/gfn-fpga-lab/agent-work/core27-prefetch-r2-host-broadcast-crtmont/snapshot-v1/fpga')
DESTINATION=SOURCE.parent.parent
LOCK=Path('/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock')
GiB=1<<30
MiB=1<<20

def require(value,message):
    if not value:raise ValueError(message)

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

# Closed reviewed ancestor/dependency pins, rather than import-discovered inputs.
FIXED_PINS={
    "reference/__init__.py": "1c6df6d638965f2bc1c163f4e66f7f9038ebedc21e2139988aa5962c0ed47efb",
    "reference/build_cache.py": "f67c4ae74b861181672ef533fdb0838569d99279119a3d78072d298f082fa615",
    "reference/core27_prefetch_r2_bench.py": "f6308e0e728471b9e703acd266c4b04d6c59918260f71ba3eb59ee7de27a56c4",
    "reference/core27_prefetch_r2_regression.py": "41a328dd0ac581c956c020d74478a5668e0032271c0656057c8de2d84907f50d",
    "reference/core27_prefetch_r2_structure.py": "2aa8c7a34a709433d5aeafa53f9cfeca996fd1d778bd45ee37b80bd84e798dc3",
    "reference/rns_reference.py": "cf52bdd75ea5b2951531f8b2a37f1fe395abf58d4d7e3ebbf59fdb1aa276f06f",
    "reference/square_core27_recovery.py": "cc24042a2e1ae647acb35343b4b5d08c8d65fd48107c342b90d282da0e7ab5de",
    "reference/square_core27_regression.py": "2bee8871c86c5d8da4f91cac2f216cc183f8c164a7c73984a13d2cbf2a8085af",
    "reference/square_core27_rootpipe_regression.py": "57e506800da41444495d7b6171336936f0a8a69ed695a6342acb6d698c0f2420",
    "reference/square_core27_rootpipe_structure.py": "be3b91a232fbb10ae9cdc95a92d6f044a76a825e9a2be689c68d8b9b36812bf1",
    "reference/square_core27_stream_prefetch_regression.py": "0b534808159e7262052577d66eb0f3d8b8e55fb90ba98db2096aa8c64bfca10a",
    "reference/square_core27_stream_regression.py": "65735e7dbd2ea876f34140f4fccc08a14a3e73713a6e513e0c1ba173f7bcc610",
    "reference/square_core_regression.py": "bb6838a3c9e2c7403d8c1f18a618c04635124de08c1c2bddf568182f56f0a732",
    "rtl/kernel/genefer_carry_prefix_stream_pipe.sv": "9838c6852cac57f7901f8b57dcbb4ee11b7fa129ef86e40158d67cc789b06e5e",
    "rtl/kernel/genefer_carry_prefix_stream_precision.sv": "ba7ce9d0c1a99ad959bfe9909c62f341fabd537c76f196c5bcb6394c161296d3",
    "rtl/kernel/genefer_crt3_27_pipe.sv": "279c6c8c3185eeaaa505283f858fd04904c6daccd30720f6b3bf78e14a6fa160",
    "rtl/kernel/genefer_digit_reduce27_pipe.sv": "61e14bb13c2dbcc13b5030756578a0d0358269beb24fb207a5641b98795883e8",
    "rtl/kernel/genefer_div_recip_narrow.sv": "eef327cee81d41895a068b746a3715daba95d43bea919edbddf9b498ecfc38bf",
    "rtl/kernel/genefer_div_recip_precision.sv": "832021ed0b3410dc867d92ac4436a725d5717f9630d233073e39896789ebbd7c",
    "rtl/kernel/genefer_mod64_pipe.sv": "e582dba87dce51794a38039fd02574f443c53750bcafc8fcb1f4d0d50fc60839",
    "rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv": "501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b",
    "rtl/kernel/genefer_ntt_banked27_engine.sv": "7ae89e702b671e3fbe8a1f90beb99ea595c832729e5e94232bf82515f1d74fe9",
    "rtl/kernel/genefer_ntt_banked27_prefetch_engine.sv": "9381ff17205c65f5b34ba355b845e15fa25cc7ce1370f81160c147aea51c4a9c",
    "rtl/kernel/genefer_ntt_banked27_prefetch_host_engine.sv": "b9248c7201d64b6f1e5ef63d5f9c44edd7711df092cef055450ada3554a0a605",
    "rtl/kernel/genefer_ntt_banked27_prefetch_r2_engine.sv": "552d273972af97c3363b77df0798e08a962d283869bcc95159f378a0f0070b17",
    "rtl/kernel/genefer_ntt_banked27_prefetch_r2_host_engine.sv": "b0fc9014b73eac3a989ce416b15e8c802a2a2fe54922af3c77489237679e0302",
    "rtl/kernel/genefer_root_profile27_r2_rom.sv": "cb851bec51f518a71d216d4a993ffa3aa937b8230474c38898b061e7ad42dea6",
    "rtl/kernel/genefer_root_profile27_rom.sv": "072487e042b3fc70bcda656ef80cfe0965b350f01fa605baa695c4df5af1c754",
    "rtl/kernel/genefer_root_recurrence27.sv": "c8adc265915192807efee46799a782f1649a4408313098baaed8b4a808afeb9e",
    "rtl/kernel/genefer_sdp_ram32.sv": "993567fb68fdc216b9ff04489d1810f743b86564434e4b48261ad606b25d53b0",
    "rtl/kernel/genefer_sp_ram.sv": "b97d2f43db1b1e1aa60b9b7fc2b720af1e302bd5ff9e35854c89b30e5fb610df",
    "rtl/kernel/genefer_square_core27_stream_prefetch.sv": "9824a29d3b5e12f29f6e1793d84dde554d91037c0c054f070ba6fbc8cbaed540",
    "rtl/kernel/genefer_square_core27_stream_prefetch_r2.sv": "452dbb922c4cd6145fc733a4036d526b9d5d465bfe92a93fd0e69f129f060af6",
    "rtl/tb/square_core27_stream_prefetch.cpp": "3f923cd47e7b9729dc16005e702c8d9ed0d7c50caa2988476e297a01caeb5d0c",
    "rtl/tb/square_core27_stream_prefetch_r2.cpp": "3537fdb2d83c25a94deb3fccbf177b09807db72e686ac13e6e290ab1ead70c4f",
    "rtl/tb/square_core27_stream_prefetch_r2_threaded.cpp": "1f9ac5aa5e70775417b8fa7a4d9f422c2825653d7e5aff43c250f187d9bf6ae9",
    "rtl/tb/square_core27_stream_prefetch_threaded.cpp": "68a4e6c2bbb6e32780d13467e94db82bc98a368991bd513ff3860d4ae9d688a2",
    "rtl/kernel/genefer_ntt_banked27_prefetch_r2_host_broadcast_engine.sv": "0960922332ea919a72a1ee591a70006bba76af7f26bc5308b68f50e327583e29",
    "rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast.sv": "ea2b518880cb1c3191c71d35a232d2483aee82046ecd4d930d7ac7ffa07a80e1",
    "rtl/tb/square_core27_stream_prefetch_r2_host_broadcast.cpp": "9e11a73d910cf6ca4f89a6cec42a41c43310f8baa9d504cf0476b27220bc0644",
    "rtl/tb/square_core27_stream_prefetch_r2_host_broadcast_threaded.cpp": "7a21cd62a4879ab1f24e4a46f05e01131a4f7f271764c6b988da701fda58f2eb",
    "reference/core27_prefetch_r2_host_broadcast_core_structure.py": "fefd9954a15e7dc9ebb9eed86d90a87626d4c780747236b2669c5ada2fc8d9a6"
}
FIXED_PINS.update({
    'reference/core27_prefetch_r2_host_broadcast_regression.py':'5abd833bfd0c35416ec818612ab4836838a0bea7d778a1f54515557c132f14eb',
    'reference/core27_prefetch_r2_host_broadcast_crtmont_structure.py':'6b0ce8b80624a765557d535d83c135cb4d4747f3de0c9f4b09541d00625952ab',
    'rtl/kernel/genefer_crt3_27_mont_pipe.sv':'8bb5b62423c1f61e069f131b5d393dd3dbc84d05348fc1945f6e9c419c104c58',
    'rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_crtmont.sv':'790582b6b9d8f3279a8a7f0fb385a5d98e6869996eb4a725005a321cf4b23820',
    'rtl/tb/square_core27_stream_prefetch_r2_host_broadcast_crtmont.cpp':'99216a00a5896461d9047466621841825fe5cc4cb4f4bb55355497607df33db0',
    'rtl/tb/square_core27_stream_prefetch_r2_host_broadcast_crtmont_threaded.cpp':'d8c35cfce602ba42135787917257732b48fa21745a32f5aff1caf10c9acd3733',
})
RUNNER='reference/core27_prefetch_r2_host_broadcast_crtmont_regression.py'
SUPPORTED_AW=(5,16)
PARENT_REPORTS={
    5:('results/throughput-20260929/core27-prefetch-r2-host-broadcast-aw5-v1/report.json','af86917c381a7ab56bcecf9007e30e3b5543eb1b6a88016c0497cba6ccce1c0f'),
    16:('results/throughput-20260929/core27-prefetch-r2-host-broadcast-aw16-v1/report.json','eb20a6237bf6da1f31d513fa59f2a1253d7615f64aa4b338bc6611cb5ebbcb29'),
}
G2_REPORT='results/throughput-20260929/crt27-mont-mutations-v1/report.json'
G2_SHA='551d5365dbd8059a372c9bed26fc860b47191a72b596e4f911af862753c3902e'
COMPILED_ORDER=(
 'genefer_montgomery_mul27_sparse_pipe.sv','genefer_digit_reduce27_pipe.sv','genefer_sdp_ram32.sv',
 'genefer_ntt_banked27_engine.sv','genefer_root_recurrence27.sv','genefer_ntt_banked27_prefetch_r2_engine.sv',
 'genefer_ntt_banked27_prefetch_r2_host_broadcast_engine.sv','genefer_root_profile27_r2_rom.sv',
 'genefer_mod64_pipe.sv','genefer_crt3_27_mont_pipe.sv','genefer_sp_ram.sv','genefer_div_recip_narrow.sv',
 'genefer_carry_prefix_stream_pipe.sv','genefer_div_recip_precision.sv','genefer_carry_prefix_stream_precision.sv',
 'genefer_square_core27_stream_prefetch_r2_host_broadcast_crtmont.sv')



def source_pins(root):
    root=Path(root).resolve()
    pins=dict(FIXED_PINS)
    pins[RUNNER]=sha(root/RUNNER)
    for name,digest in pins.items():
        path=root/name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and
                not path.is_symlink() and path.resolve().is_relative_to(root) and
                sha(path)==digest,'pinned source changed: '+name)
    return pins


def verify_manifest(root,path,digest,aw):
    require(type(aw) is int and aw in SUPPORTED_AW,'supported explicit address width')
    require(re.fullmatch('[0-9a-f]{64}',digest) is not None and sha(path)==digest,'approved manifest SHA')
    manifest=json.loads(path.read_text())
    pins=source_pins(root)
    require(manifest['status']=='prepared_not_executed' and manifest['sources']==pins and
            manifest['target']==str(SOURCE.parent) and manifest['top']==TOP and
            manifest['supported_aw']==list(SUPPORTED_AW) and
            manifest['compiled_source_order']==list(COMPILED_ORDER) and manifest['g2_sha256']==G2_SHA,
            'approved closed snapshot mismatch')
    require(sha(path.parent/'parent-metrics.json')==manifest['parent_metrics_sha256'],'approved parent metric identity')
    check_g2(path.parent/'g2-report.json')
    return manifest,pins


def load_project(root,pins,isolated=False):
    # Recheck before the FIRST import, including reference/__init__.py.
    require(source_pins(root)==pins,'pre-import source drift')
    if isolated:
        require(not __package__ and not any(name=='reference' or name.startswith('reference.')
            for name in sys.modules),'execute directly before any project import')
        require(not any(p.suffix in ('.pyc','.so','.pyd') for p in (root/'reference').rglob('*')),
                'source-only project imports; compiled cache must not exist')
        sys.pycache_prefix=None
        sys.dont_write_bytecode=True
    sys.path.insert(0,str(root))
    baseline=importlib.import_module('reference.core27_prefetch_r2_regression')
    structure=importlib.import_module('reference.core27_prefetch_r2_host_broadcast_crtmont_structure')
    for name,module in tuple(sys.modules.items()):
        if name=='reference' or name.startswith('reference.'):
            filename=getattr(module,'__file__',None)
            require(filename is not None,'unexpected namespace module')
            path=Path(filename).resolve()
            require(path.is_relative_to(root),'import outside approved snapshot')
            relative=str(path.relative_to(root))
            require(relative in pins and sha(path)==pins[relative],'unlisted imported module: '+name)
    structure.validate_files(root)
    require(tuple(structure.KERNEL_PINS)==COMPILED_ORDER,'exact ordered G4 kernel closure')
    sources=[root/'rtl/kernel'/name for name in COMPILED_ORDER]
    modules=[]
    for path in sources:modules+=re.findall(r'^module\s+(\w+)',path.read_text(),re.M)
    require(len(modules)==len(set(modules)) and TOP in modules and
            'genefer_ntt_difdit_butterfly27' in modules,'exact compiled module closure')
    return baseline,structure,sources


def allocated_bytes(root):
    total=0
    for directory,_,names in os.walk(root):
        for name in names:
            try:total+=(Path(directory)/name).lstat().st_blocks*512
            except FileNotFoundError:continue
    return total



def compile_command(root,sources,build,aw):
    require(type(aw) is int and aw in SUPPORTED_AW,'supported compile profile')
    wrapper=root/'rtl/tb/square_core27_stream_prefetch_r2_host_broadcast_crtmont_threaded.cpp'
    return ['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',TOP,
            f'-GAW={aw}','-GNTT_LANES=64','-CFLAGS','-std=c++17 -Werror=return-type -DCORE27_PREFETCH_R2_RUNTIME_THREADS=1','--Mdir',str(build),*map(str,sources),str(wrapper)]


def check_g2(path):
    require(sha(path)==G2_SHA,'exact G2 negative/fresh-control receipt')
    report=json.loads(path.read_text())
    require(report['status']=='passed_required_mutations_and_fresh_controls' and
            set(report['mutations'])=={'cb-off-one','center-ge','t2m3-removed'} and
            len(report['input_rejections'])==30,'complete G2 prerequisite')
    require(report['sources']['rtl/kernel/genefer_crt3_27_mont_pipe.sv']==FIXED_PINS['rtl/kernel/genefer_crt3_27_mont_pipe.sv'],
            'G2 candidate source identity')
    require(report['profile']['candidate_delay']==15 and report['profile']['frozen_delay']==60 and
            report['profile']['random_cases']==1000000,'G2 unequal latency/profile')
    for row in report['mutations'].values():
        require(row['fresh_control_counts']==report['vectors']['counts'],'fresh G2 control coverage')
    return report


def parent_evidence(root):
    result={}
    for aw,(relative,digest) in PARENT_REPORTS.items():
        path=root/relative;require(sha(path)==digest,'frozen native parent report')
        report=json.loads(path.read_text())
        require(report['status']=='passed' and report['aw']==aw and report['top']==TOP.removesuffix('_crtmont'),
                'passed exact parent profile')
        for name,value in report['sources'].items():
            require(name in FIXED_PINS and FIXED_PINS[name]==value,'native parent source mismatch')
        result[str(aw)]=dict(report_sha256=digest,metrics=report['metrics'],vectors=report['vectors'])
    return result


def validate_output(output,vectors,aw,baseline):
    # Reuse frozen independent phase/coverage validator, restoring exactly the
    #45 clocks solely for that validation, then return unmodified candidate data.
    restored=[]
    for line in output.splitlines():
        if ' cycles=' in line:
            line=re.sub(r'\b(cycles|crt)=(\d+)',lambda m:m[1]+'='+str(int(m[2])+45),line)
        restored.append(line)
    rows=baseline.validate_output('\n'.join(restored)+'\n',vectors,aw)
    return [dict(row,cycles=row['cycles']-45,crt=row['crt']-45) for row in rows]


def check_matched_metrics(actual,parent):
    expected=[dict(row,cycles=row['cycles']-45,crt=row['crt']-45) for row in parent]
    require(actual==expected,'exact parent metrics except CRT/total minus45')


def prepare(out):
    root=Path(__file__).resolve().parents[1];pins=source_pins(root)
    load_project(root,pins);parents=parent_evidence(root);check_g2(root/G2_REPORT)
    out.mkdir(parents=True,exist_ok=False)
    (out/'parent-metrics.json').write_text(json.dumps(parents,indent=2)+'\n')
    shutil.copyfile(root/G2_REPORT,out/'g2-report.json')
    archive=out/'source.tar.gz'
    with tarfile.open(archive,'x:gz') as tar:
        for name,digest in pins.items():
            path=root/name;require(not path.is_symlink() and sha(path)==digest,'source drift/link')
            tar.add(path,arcname='fpga/'+name,recursive=False)
    require(source_pins(root)==pins,'source drift during preparation')
    manifest={'status':'prepared_not_executed','sources':pins,'archive_sha256':sha(archive),
        'target':str(SOURCE.parent),'top':TOP,'supported_aw':list(SUPPORTED_AW),
        'compiled_source_order':list(COMPILED_ORDER),'g2_sha256':G2_SHA,
        'parent_metrics_sha256':sha(out/'parent-metrics.json'),
        'limitation':'Source snapshot only. G2 independent audit and dispatch review still required. AW5 first, then AW16. No automatic simulation or physical dispatch.'}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'files':len(pins),'bytes':archive.stat().st_size,'sha256':sha(archive)}))
    return manifest

def execute(aw,out,manifest_path,manifest_sha):
    require(__debug__ and socket.gethostname()=='aethia','aethia with assertions required')
    root=Path(__file__).resolve().parents[1]
    require(root==SOURCE and root.resolve()==SOURCE,'isolated snapshot identity')
    require(out.resolve().parent==DESTINATION and not out.exists(),'fresh output in experiment directory')
    require(LOCK.resolve()==LOCK and LOCK.is_file(),'shared compiler lock identity')
    manifest,pins=verify_manifest(root,manifest_path,manifest_sha,aw)
    baseline,structure,sources=load_project(root,pins,isolated=True)
    parents=json.loads((manifest_path.parent/'parent-metrics.json').read_text())
    limits=baseline.execution_limits();require(limits['affinity']==[0,2],'physical CPU0/2 allocation')
    require(len({tuple(x) for x in limits['physical_cores']})==2,'distinct physical CPUs')
    resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(6*GiB,6*GiB))
    out.mkdir();scratch=Path(tempfile.mkdtemp(prefix='gfn16-prefetch-r2-host-broadcast-crtmont-',dir='/dev/shm'));os.chmod(scratch,0o700)
    tmp=scratch/'tmp';tmp.mkdir()
    report=dict(status='running',aw=aw,n=1<<aw,ntt_lanes=64,model_threads=1,compile_workers=2,
        scope='Single-profile broadcast plus Montgomery CRT whole-core normal gate, exact parent-minus45 clocks',sources=pins,limits=limits,
        top=TOP,manifest_sha256=manifest_sha,g2_sha256=G2_SHA,parent_report_sha256=parents[str(aw)]['report_sha256'],compiled_source_order=[str(p.relative_to(root)) for p in sources],
        scratch=str(scratch),compiler_temporary_directory=str(tmp),steps=[],metrics=[],segments=[],artifacts={},
        scratch_reservation_bytes=768*MiB,scratch_free_floor_bytes=2*GiB,
        durable_reservation_bytes=64*MiB,durable_free_floor_bytes=10*GiB,host_memory_floor_bytes=4*GiB,
        command_timeout_seconds=1800,lock_wait_timeout_seconds=1800,cleanup='Scratch retained; no deletion.',
        limitation='Not a complete multi-profile or mutation qualification, fit, clock, board or full PRP result.')
    def guard():
        require(shutil.disk_usage(out).free>=10*GiB+max(0,64*MiB-allocated_bytes(out)),'durable disk reservation/floor')
        require(shutil.disk_usage(scratch).free>=2*GiB+max(0,768*MiB-allocated_bytes(scratch)),'tmpfs reservation/floor')
        mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
        require(int(mem['MemAvailable'].split()[0])*1024>=4*GiB,'host memory floor')
    def recheck():
        require(source_pins(root)==pins,'source drift')
        require(sha(manifest_path)==manifest_sha and sha(manifest_path.parent/'parent-metrics.json')==manifest['parent_metrics_sha256'],
                'approved input drift')
        check_g2(manifest_path.parent/'g2-report.json')
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
        for name in ('g++','verilator','verilator_bin','make'):
            found=shutil.which(name);require(found is not None,'missing '+name);tool_paths.append(Path(found).resolve())
        report['tool_executable_sha256']={str(path):sha(path) for path in tool_paths}
        report['python_version']=sys.version
        report['tool_version']=run('verilator-version',['verilator','--version']).strip()
        report['compiler_version']=run('compiler-version',['g++','--version']).strip()
        shutil.copyfile(manifest_path,out/'approved-manifest.json');remember(out/'approved-manifest.json')
        with tarfile.open(out/'sources.tar.gz','x:gz') as tar:
            for name in pins:tar.add(root/name,arcname=name,recursive=False)
        remember(out/'sources.tar.gz')
        vector=out/f'vectors-aw{aw}.txt';report['vectors']=baseline.write_vectors(vector,aw,20260929,True);remember(vector)
        require(sha(vector)==report['vectors']['sha256'],'vector generation hash')
        require(report['vectors']==parents[str(aw)]['vectors'],'exact frozen parent vector identity/coverage')
        for name in ('parent-metrics.json','g2-report.json'):
            shutil.copyfile(manifest_path.parent/name,out/name);remember(out/name)
        guard()
        build=scratch/'build';command=compile_command(root,sources,build,aw)
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
        baseline.check_probe(run('probe',[str(exe),'--runtime-probe']),1)
        raw=vector.read_bytes()
        if aw==16:_,parts,_,_=baseline.segments(raw)
        else:parts=[(1,len(raw.splitlines()),raw)]
        for index,(start,end,payload) in enumerate(parts):
            piece=out/f'segment{index}.txt';piece.write_bytes(payload);remember(piece)
            report['segments'].append(dict(index=index,start=start,end=end,sha256=sha(piece)))
            output=run(f'test-segment{index}',[str(exe),str(piece),'profile'])
            report['metrics']+=validate_output(output,payload.decode(),aw,baseline)
            require(sha(exe)==report['executable_sha256'],'model changed during test')
        require(len(report['metrics'])==report['vectors']['squares'],'operation coverage')
        check_matched_metrics(report['metrics'],parents[str(aw)]['metrics'])
        report['matched_cycle_delta']=dict(crt=-45,cycles=-45,all_other_fields_identical=True)
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
    parser.add_argument('--aw',type=int,choices=SUPPORTED_AW);parser.add_argument('--output',type=Path)
    parser.add_argument('--manifest',type=Path);parser.add_argument('--manifest-sha')
    args=parser.parse_args()
    if args.prepare:
        require(not args.execute and args.aw is None and args.output is None and args.manifest is None and args.manifest_sha is None,'exclusive preparation mode')
        prepare(args.prepare.resolve())
    else:
        require(args.execute and args.aw is not None and args.output is not None and args.manifest and args.manifest_sha,'explicit profile/output execution')
        execute(args.aw,args.output.resolve(),args.manifest.resolve(),args.manifest_sha)

if __name__=='__main__':main()
