"""Read-only format2 normal-profile evidence audit; no simulator/generator imports.

Only ordinary radix-integer packing is reused. Saved executables are hashed,
never executed. A passing receipt is bounded by the reported AW and vectors;
it is not an RTL formal proof, compiler attestation, or full PRP qualification.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import tarfile

from .verify_square_core27_rootpipe_offline import radix_integer

TOP='genefer_square_core27_stream_prefetch_r2'
MANIFEST_SHA='6404854a21554820b6d365fa6e653352cd5dbe50edc2a913ed99bb1458028c33'
SNAPSHOT='/home/jtl/gfn-fpga-lab/agent-work/core27-prefetch-r2/snapshot-v1/fpga'
RTL_PINS={
 'genefer_montgomery_mul27_sparse_pipe':'501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b',
 'genefer_digit_reduce27_pipe':'61e14bb13c2dbcc13b5030756578a0d0358269beb24fb207a5641b98795883e8',
 'genefer_sdp_ram32':'993567fb68fdc216b9ff04489d1810f743b86564434e4b48261ad606b25d53b0',
 'genefer_ntt_banked27_engine':'7ae89e702b671e3fbe8a1f90beb99ea595c832729e5e94232bf82515f1d74fe9',
 'genefer_root_recurrence27':'c8adc265915192807efee46799a782f1649a4408313098baaed8b4a808afeb9e',
 'genefer_ntt_banked27_prefetch_r2_engine':'552d273972af97c3363b77df0798e08a962d283869bcc95159f378a0f0070b17',
 'genefer_ntt_banked27_prefetch_r2_host_engine':'b0fc9014b73eac3a989ce416b15e8c802a2a2fe54922af3c77489237679e0302',
 'genefer_root_profile27_r2_rom':'cb851bec51f518a71d216d4a993ffa3aa937b8230474c38898b061e7ad42dea6',
 'genefer_mod64_pipe':'e582dba87dce51794a38039fd02574f443c53750bcafc8fcb1f4d0d50fc60839',
 'genefer_crt3_27_pipe':'279c6c8c3185eeaaa505283f858fd04904c6daccd30720f6b3bf78e14a6fa160',
 'genefer_sp_ram':'b97d2f43db1b1e1aa60b9b7fc2b720af1e302bd5ff9e35854c89b30e5fb610df',
 'genefer_div_recip_narrow':'eef327cee81d41895a068b746a3715daba95d43bea919edbddf9b498ecfc38bf',
 'genefer_carry_prefix_stream_pipe':'9838c6852cac57f7901f8b57dcbb4ee11b7fa129ef86e40158d67cc789b06e5e',
 'genefer_div_recip_precision':'832021ed0b3410dc867d92ac4436a725d5717f9630d233073e39896789ebbd7c',
 'genefer_carry_prefix_stream_precision':'ba7ce9d0c1a99ad959bfe9909c62f341fabd537c76f196c5bcb6394c161296d3',
 TOP:'452dbb922c4cd6145fc733a4036d526b9d5d465bfe92a93fd0e69f129f060af6',
}
SOURCE_PINS={**{'rtl/kernel/'+k+'.sv':v for k,v in RTL_PINS.items()},
 'rtl/kernel/genefer_square_core27_stream_prefetch.sv':'9824a29d3b5e12f29f6e1793d84dde554d91037c0c054f070ba6fbc8cbaed540',
 'rtl/kernel/genefer_root_profile27_rom.sv':'072487e042b3fc70bcda656ef80cfe0965b350f01fa605baa695c4df5af1c754',
 'rtl/kernel/genefer_ntt_banked27_prefetch_engine.sv':'9381ff17205c65f5b34ba355b845e15fa25cc7ce1370f81160c147aea51c4a9c',
 'rtl/kernel/genefer_ntt_banked27_prefetch_host_engine.sv':'b9248c7201d64b6f1e5ef63d5f9c44edd7711df092cef055450ada3554a0a605',
 'rtl/tb/square_core27_stream_prefetch_r2.cpp':'3537fdb2d83c25a94deb3fccbf177b09807db72e686ac13e6e290ab1ead70c4f',
 'rtl/tb/square_core27_stream_prefetch_r2_threaded.cpp':'1f9ac5aa5e70775417b8fa7a4d9f422c2825653d7e5aff43c250f187d9bf6ae9',
 'rtl/tb/square_core27_stream_prefetch.cpp':'3f923cd47e7b9729dc16005e702c8d9ed0d7c50caa2988476e297a01caeb5d0c',
 'rtl/tb/square_core27_stream_prefetch_threaded.cpp':'68a4e6c2bbb6e32780d13467e94db82bc98a368991bd513ff3860d4ae9d688a2',
 'reference/core27_prefetch_r2_structure.py':'2aa8c7a34a709433d5aeafa53f9cfeca996fd1d778bd45ee37b80bd84e798dc3',
 'reference/core27_prefetch_r2_bench.py':'f6308e0e728471b9e703acd266c4b04d6c59918260f71ba3eb59ee7de27a56c4',
 'reference/core27_prefetch_r2_regression.py':'41a328dd0ac581c956c020d74478a5668e0032271c0656057c8de2d84907f50d',
}
FIELDS=('cycles','conversion','roots','ntt','crt','carry','passes','base','profile_before',
        'profile_loads','profile_hits','profile_words','seed_setup','readback')
ABORTS={'conversion','root','ntt','crt','carry','root0','root1','root2','root3',
        'convert-m1','convert-0','convert-p1','crt-active','profile-lastavailable',
        'profile-consumed','profile-commit','profile-check'}


def require(value,message):
    if not value:raise ValueError(message)


def digest(data):return hashlib.sha256(data).hexdigest()
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def safe_name(name):
    require(isinstance(name,str) and name and not name.startswith('/') and '\\' not in name,
            'unsafe relative name')
    p=PurePosixPath(name)
    require(str(p)==name and '..' not in p.parts and '.' not in p.parts,'unsafe relative name')
    return name


def local_file(root,name):
    p=root/safe_name(name)
    require(p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(root.resolve()),'unsafe/missing artifact '+name)
    require(not any(x.is_symlink() for x in p.parents if x!=root and x.is_relative_to(root)),'symlink artifact parent')
    return p


def archive_members(path,expected):
    """Read regular members in memory; do not extract any archive path."""
    require(expected and all(re.fullmatch('[0-9a-f]{64}',v) for v in expected.values()),'invalid archive hash table')
    for name in expected:safe_name(name)
    with tarfile.open(path) as tar:
        members=tar.getmembers()
        require(len(members)==len(expected) and {m.name for m in members}==set(expected),'archive membership')
        require(all(m.isfile() and m.size>=0 for m in members) and sum(m.size for m in members)<=512<<20,'archive type/size')
        result={}
        for member in members:
            data=tar.extractfile(member).read()
            require(digest(data)==expected[member.name],'archive member hash: '+member.name)
            result[member.name]=data
    return result


def schedule(aw):
    """Independent accounting of two stage traversals and two rooted point passes."""
    n=1<<aw;groups=(n+127)//128;setup=0
    for stages in (range(aw-1,-1,-1),range(aw)):
        previous=None
        for stage in stages:
            period=1 if stage<7 else 2**(stage-6)
            seed_count=min(4,groups,period)*min(64,2**stage)
            setup+=seed_count+4 if previous is None else max(1,seed_count-groups-3)
            previous=stage
    setup+=2*(min(4,(n+63)//64)*min(64,n)+4)
    return 3*((n+63)//64+7)+2*aw*(groups+8)+setup+10,setup


def audit_vectors(raw,log,aw):
    require(type(aw) is int and aw in (1,5,7,16),'AW profile')
    lines=raw.splitlines();n=1<<aw
    require(lines and lines[0]==str(n) and all(lines),'vector header/blank line')
    pattern=re.compile(r'^(\S+) '+' '.join(k+r'=(\d+)' for k in FIELDS)+'$')
    metrics=[];footers=[]
    for line in log.splitlines():
        if not line.strip():continue
        match=pattern.fullmatch(line)
        if match:
            row=dict(zip(FIELDS,map(int,match.groups()[1:])),case=match[1],aw=aw,n=n)
            metrics.append(row)
        else:
            require(re.fullmatch(r'PASS n=\d+ squares=\d+ readbacks=\d+ aborts=\d+',line),'unexpected/malformed runtime log')
            footers.append(line)
    i=1;j=0;cache=0;x=None;base=None;modulus=None;pending_readback=False
    names=set();commands=Counter();aborts=[];cold=warm=0;bases=set();invalid_at=[];runs=[]
    ntt,seed_setup=schedule(aw);words=(2*aw+2)*257
    def canonical(digits,output=False):
        return digits==[-1]+[0]*(n-1) or all((0 if output else -1)<=d<base for d in digits)
    while i<len(lines):
        tokens=lines[i].split();i+=1;cmd=tokens[0];commands[cmd]+=1
        if cmd in ('LOAD','LOAD_KEEP'):
            require(len(tokens)==3 and not pending_readback,'load syntax/unobserved NOREAD chain')
            base=int(tokens[2]);require(2*n+4<base<=1000000000,'loaded base domain')
            require(i<len(lines),'truncated load');digits=list(map(int,lines[i].split()));i+=1
            require(len(digits)==n and canonical(digits),'load digit width/domain')
            modulus=pow(base,n)+1;x=radix_integer(digits,base)%modulus;bases.add(base)
            if cmd=='LOAD':cache=0
        elif cmd in ('RUN','RUN_NOREAD'):
            require(len(tokens)==3,'run syntax');name=tokens[1];bit=int(tokens[2])
            require(name not in names and bit in (0,1),'case/bit identity');names.add(name)
            require(x is not None and i<len(lines),'run without live input/truncated expected')
            expected=list(map(int,lines[i].split()));i+=1
            require(len(expected)==n and canonical(expected,True),'noncanonical expected digits')
            x=(x*x*(1<<bit))%modulus
            require(radix_integer(expected,base)%modulus==x,'independent integer oracle: '+name)
            require(j<len(metrics),'missing raw metric');row=metrics[j];j+=1
            require((row['case'],row['base'],row['profile_before'])==(name,base,cache),'transaction/cache order')
            require(row['readback']==int(cmd=='RUN'),'readback coverage')
            require(row['cycles']==sum(row[k] for k in ('conversion','roots','ntt','crt','carry')),'phase accounting')
            require(row['conversion']==(n+15)//16+6,'fusion conversion count')
            require((row['ntt'],row['seed_setup'])==(ntt,seed_setup),'NTT/seed schedule')
            require((row['profile_loads'],row['profile_hits'],row['profile_words'],row['roots'])==
                    ((0,1,0,0) if cache else (1,0,words,words+5)),'profile accounting')
            require(row['crt']==(n+15)//16+62+max(0,97-row['roots']-ntt),'CRT/reservation count')
            require(row['carry']==(n+15)//16+51 and row['passes']==2,'carry tail/passes')
            warm+=cache;cold+=1-cache;cache=1;pending_readback=cmd=='RUN_NOREAD'
            runs.append({'case':name,'base':base,'bit':bit,'residue':x})
        elif cmd=='ABORT':
            require(len(tokens)==3 and tokens[1] in ABORTS and int(tokens[2]) in (0,1) and x is not None and not pending_readback,'abort contract')
            require(tokens[1]!='crt-active' or n>=32,'crt-active size')
            aborts.append(tokens[1]);cache=0;x=None
        elif cmd=='BADBASE':
            require(len(tokens)==2 and not pending_readback,'BADBASE syntax')
            bad=int(tokens[1]);require(not 2*n+4<bad<=1000000000,'BADBASE is legal')
            cache=0;x=None
        elif cmd in ('BADDIGIT','BADDIGIT_AT'):
            require(len(tokens)==(4 if cmd=='BADDIGIT_AT' else 3) and not pending_readback,'BADDIGIT syntax')
            b=int(tokens[1]);bad=int(tokens[2]);at=int(tokens[3]) if cmd=='BADDIGIT_AT' else n//2
            require(2*n+4<b<=1000000000 and 0<=at<n and (bad < -1 or bad>=b),'invalid-digit case not invalid')
            if cmd=='BADDIGIT_AT':invalid_at.append((b,bad,at))
            cache=0;x=None
        else:raise ValueError('unexpected vector command: '+cmd)
    require(not pending_readback,'unobserved terminal NOREAD chain')
    require(j==len(metrics),'extra raw metrics')
    footer=f'PASS n={n} squares={j} readbacks={commands["RUN"]} aborts={commands["ABORT"]}'
    require(footers==[footer] and log.rstrip().endswith(footer),'terminal coverage footer')
    return metrics,dict(commands=dict(commands),abort_labels=aborts,cold_runs=cold,warm_runs=warm,
                        bases=sorted(bases),invalid_at=invalid_at,runs=runs)


def verify(root,manifest):
    root=Path(root);report=json.loads(local_file(root,'report.json').read_text())
    require(sha(manifest)==MANIFEST_SHA,'approved pre-import manifest identity')
    approved=json.loads(Path(manifest).read_text())
    require(approved['status']=='prepared_not_executed' and approved['target']==str(PurePosixPath(SNAPSHOT).parent),'manifest target/status')
    require(report['sources']==approved['sources'],'source map differs from approved pre-import manifest')
    require(report.get('status')=='passed','incomplete/failed normal profile')
    aw=report['aw'];require(type(aw) is int and aw in (1,5,7,16),'AW profile')
    require(report['n']==1<<aw and report['ntt_lanes']==64 and report['model_threads']==1 and report['compile_workers']==2,'geometry/thread profile')
    limits=report['limits'];cpu=limits['cpu_max']
    require(limits['affinity']==[0,2] and 0<int(limits['memory_max_bytes'])<=6<<30 and
            len(cpu)==2 and 0<int(cpu[0])<=2*int(cpu[1]) and
            len(limits['physical_cores'])==2 and len({tuple(x) for x in limits['physical_cores']})==2,
            'execution CPU/memory contract')
    for key,value in {'scratch_reservation_bytes':512<<20,'scratch_free_floor_bytes':2<<30,
                      'durable_reservation_bytes':64<<20,'durable_free_floor_bytes':10<<30,
                      'host_memory_floor_bytes':4<<30,'command_timeout_seconds':1800}.items():
        require(report[key]==value,'execution reservation: '+key)
    artifacts=report['artifacts']
    require(artifacts and all(re.fullmatch('[0-9a-f]{64}',d) for d in artifacts.values()),'artifact hash table')
    for name,h in artifacts.items():require(sha(local_file(root,name))==h,'artifact hash: '+name)
    sources=archive_members(local_file(root,'sources.tar.gz'),report['sources'])
    for name,h in SOURCE_PINS.items():require(report['sources'].get(name)==h,'qualified source pin: '+name)
    generated=archive_members(local_file(root,'generated-sources.tar.gz'),report['generated_source_sha256'])
    require(all('/' not in name and Path(name).suffix in ('.cpp','.h','.mk','.dat') for name in generated),'generated source member type')
    require('V'+TOP+'.h' in generated and 'V'+TOP+'.mk' in generated,'generated model closure')
    model=generated.get('V'+TOP+'.cpp',b'').decode()
    require(re.search(r'unsigned\s+V'+TOP+r'::threads\(\) const\s*\{\s*return 1;\s*\}',model),'generated model thread identity')
    steps={s['name']:s for s in report['steps']};require(len(steps)==len(report['steps']),'duplicate command stage')
    for s in steps.values():
        require(s['returncode']==0 and s['error'] is None,'failed command')
        duration=s['seconds']
        require(type(duration) in (int,float) and math.isfinite(duration) and 0<=duration<=1801,'step duration')
        require(s['log'] in artifacts and artifacts[s['log']]==s['sha256'],'step log identity')
    expected_steps={'verilator-version','compiler-version','build','probe'}
    require(expected_steps<=set(steps),'missing command stage')
    require(steps['verilator-version']['command']==['verilator','--version'] and steps['compiler-version']['command']==['g++','--version'],'tool version argv')
    for step,key in (('verilator-version','tool_version'),('compiler-version','compiler_version')):
        require(report[key]==(root/steps[step]['log']).read_text().strip() and report[key],'tool version consistency')
    tools=report['tool_executable_sha256']
    require(len(tools)==3 and all(Path(p).is_absolute() and re.fullmatch('[0-9a-f]{64}',h) for p,h in tools.items()),'recorded tool identities')
    require(isinstance(report['python_version'],str) and report['python_version'],'Python version missing')
    scratch=report['scratch'];require(PurePosixPath(scratch).parent==PurePosixPath('/dev/shm') and PurePosixPath(scratch).name.startswith('gfn16-prefetch-r2-'),'build scratch identity')
    require(report['compiler_temporary_directory']==scratch+'/tmp','compiler temporary directory')
    command=['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',TOP,
             f'-GAW={aw}','-GNTT_LANES=64','--Mdir',scratch+'/build',
             *[SNAPSHOT+'/rtl/kernel/'+name+'.sv' for name in RTL_PINS],
             SNAPSHOT+'/rtl/tb/square_core27_stream_prefetch_r2_threaded.cpp']
    require(steps['build']['command']==command,'exact compiled source/configuration closure')
    exe='V'+TOP;require(sha(local_file(root,exe))==report['executable_sha256'],'executable hash')
    remote=PurePosixPath(report['executable'])
    require(remote.is_absolute() and remote.name==exe and remote.parent.parent==PurePosixPath(SNAPSHOT).parent.parent,'durable executable path')
    require(steps['probe']['command']==[str(remote),'--runtime-probe'],'probe argv')
    probe=json.loads((root/steps['probe']['log']).read_text())
    require(probe=={'context_threads':1,'model_threads':1,'expected_threads':1} and all(type(x) is int for x in probe.values()),'runtime context/model probe')
    vector_name=f'vectors-aw{aw}.txt';raw=local_file(root,vector_name).read_bytes();lines=raw.splitlines(keepends=True)
    require(digest(raw)==report['vectors']['sha256'],'original vector hash')
    parts=report['segments'];require(parts and [s['index'] for s in parts]==list(range(len(parts))),'segment index coverage')
    rebuilt=lines[0];next_start=1;all_metrics=[];totals=Counter();aborts=[];invalid=[];runs=[];cold=warm=0;bases=set()
    for part in parts:
        index=part['index'];start=part['start'];end=part['end'];name=f'segment{index}.txt'
        require(type(start) is int and type(end) is int and start==next_start and start<end<=len(lines),'segment partition')
        payload=local_file(root,name).read_bytes()
        require(digest(payload)==part['sha256'] and payload==lines[0]+b''.join(lines[start:end]),'segment bytes/hash')
        if index:require(lines[start].startswith(b'LOAD '),'segment splits live LOAD_KEEP chain')
        rebuilt+=b''.join(lines[start:end]);next_start=end
        step=f'test-segment{index}';expected_steps.add(step)
        require(step in steps and steps[step]['command']==[str(remote),str(remote.parent/name),'profile'],'test argv')
        rows,coverage=audit_vectors(payload.decode(),(root/steps[step]['log']).read_text(),aw)
        all_metrics+=rows;totals.update(coverage['commands']);aborts+=coverage['abort_labels'];invalid+=coverage['invalid_at'];runs+=coverage['runs']
        cold+=coverage['cold_runs'];warm+=coverage['warm_runs'];bases.update(coverage['bases'])
    require(rebuilt==raw and next_start==len(lines),'segment omission/duplication')
    require(len({m['case'] for m in all_metrics})==len(all_metrics),'duplicate cross-segment transaction')
    require(all_metrics==report['metrics'],'report metrics vs raw log')
    info=report['vectors'];require(len(all_metrics)==info['squares'] and totals['RUN']==info['readbacks'],'reported coverage')
    require((len(all_metrics),totals['RUN'],len(aborts))==
            {1:(529,522,9),5:(568,561,20),7:(12,10,0),16:(12,10,0)}[aw],
            'normal profile operation/readback/abort coverage')
    n=1<<aw;last=[(b,b,i) for b in (2*n+5,1000000000) for i in sorted({max(0,n-16),n-1})]
    require(info['fusion_invalid_final_row_cases']==len(last) and invalid[-len(last):]==last,'fusion final-row invalid coverage')
    if aw in (1,5):require({'conversion','root','ntt','crt','carry','root0','root1','root2','root3'}<=set(aborts),'reset-phase coverage')
    if aw==5:
        require(all(aborts.count(x)==2 for x in ('convert-m1','convert-0','convert-p1')) and aborts.count('crt-active')==1,'fusion boundary reset coverage')
        require(all(aborts.count('profile-'+x)==1 for x in ('lastavailable','consumed','commit','check')),'profile boundary reset coverage')
    expected_fermat=[2*n+6,2*n+7] if aw in (1,5) else []
    require([chain['base'] for chain in info['fermat_chains']]==expected_fermat,'Fermat chain coverage')
    for chain in info['fermat_chains']:
        b=chain['base'];exponent=pow(b,n);selected=[r for r in runs if r['case'].startswith(f'fermat-b{b}-s')]
        require([r['bit'] for r in selected]==list(map(int,bin(exponent)[2:])) and len(selected)==chain['steps'],'Fermat exponent steps')
        require(selected and selected[-1]['residue']==int(chain['residue_hex'],16)==pow(2,exponent,exponent+1),'independent Fermat result')
    require(set(steps)==expected_steps,'unexpected/missing command stages')
    expected_artifacts={exe,'sources.tar.gz','generated-sources.tar.gz',vector_name,
                        *[s['log'] for s in steps.values()],*[f'segment{x["index"]}.txt' for x in parts]}
    require(set(artifacts)==expected_artifacts,'durable artifact closure')
    return dict(status='verified_normal_profile',aw=aw,n=n,operations=len(all_metrics),readbacks=totals['RUN'],
                no_readback_operations=totals['RUN_NOREAD'],cold_runs=cold,warm_runs=warm,
                abort_labels=aborts,bases=sorted(bases),artifacts=len(artifacts),source_members=len(sources),
                generated_members=len(generated),report_sha256=sha(root/'report.json'),verifier_sha256=sha(__file__),
                approved_manifest_sha256=MANIFEST_SHA,
                source_archive_sha256=sha(root/'sources.tar.gz'),executable_sha256=report['executable_sha256'],
                tool_executable_sha256=tools,
                limitation='Only this AW normal profile; no RTL mutation/whole-profile/fullPRP/board/timing claim. NOREAD states are not individually observed; final readback validates their chain. Archived binaries/generated code and tool identity/version records are cross-checked, but compiler execution and remote unarchived tool binaries remain trusted; no executable is run by this audit.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('roots',type=Path,nargs='+')
    parser.add_argument('--manifest',type=Path,required=True)
    args=parser.parse_args();print(json.dumps([verify(root,args.manifest) for root in args.roots],indent=2))
