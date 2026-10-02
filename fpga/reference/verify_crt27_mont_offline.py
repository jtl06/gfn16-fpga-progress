"""Independent OFFLINE G2 CRT27 positive and mutation evidence audit.

Never import the CRT runner/candidate arithmetic, and never execute any saved
binary. Regenerate the seeded input stream and direct ordinary-integer CRT
answers, then verify distinct-latency transaction accounting and all raw
native/source/artifact/control bindings. Physical qualification is separate.
"""
import argparse
from collections import Counter,deque
import hashlib
import json
import math
from pathlib import Path,PurePosixPath
import random
import re
import shlex

TOP='crt3_27_mont_pair'
PROFILE={"candidate_delay":15,"candidate_stages":16,"frozen_delay":60,"frozen_stages":61,"coefficient_bits":96,"random_cases":1000000,"seed":20260930}
PROFILE['seed']=20260930
PRIMES=(104857601,69206017,67239937);M=487945222748036195811329;HALF=M//2
CRT_TERMS=tuple((M//p)*pow(M//p,-1,p) for p in PRIMES)
ORDER=["rtl/kernel/genefer_mod64_pipe.sv","rtl/kernel/genefer_crt3_27_pipe.sv","rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv","rtl/kernel/genefer_crt3_27_mont_pipe.sv","rtl/tb/crt3_27_mont_pair.sv","rtl/tb/crt3_27_mont_pair.cpp"]
PINS={
 "rtl/kernel/genefer_mod64_pipe.sv": "e582dba87dce51794a38039fd02574f443c53750bcafc8fcb1f4d0d50fc60839",
 "rtl/kernel/genefer_crt3_27_pipe.sv": "279c6c8c3185eeaaa505283f858fd04904c6daccd30720f6b3bf78e14a6fa160",
 "rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv": "501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b",
 "rtl/kernel/genefer_crt3_27_mont_pipe.sv": "8bb5b62423c1f61e069f131b5d393dd3dbc84d05348fc1945f6e9c419c104c58",
 "rtl/tb/crt3_27_mont_pair.sv": "a449b4c4474a582207580db9e4ebc983aadc4edbf4402fd475812d7f511e3c1a",
 "rtl/tb/crt3_27_mont_pair.cpp": "415c313a549aa3fe387af84eec23a6860ced0be72fa56fe73908d7d903751ef6",
 "docs/briefs/crt27_mont_oracle.py": "1b211c9c83b86b2427e2e605d53d376af863cd143775ea5894673c4001a55757",
 "docs/briefs/2026-09-30-codex-handoff.md": "486aee63bacaa895041736af6d7bf7e51ba2e87e5ac5c820230e84f90b85fa8d",
 "reference/crt27_mont_regression.py": "c1a2af418bd615d7af5e1d495d22b071dfbb2013022b8a92e96c03d7654c80aa",
 "docs/briefs/2026-09-30-answers-B20260930.md": "1745c17b26b9953c49761a3a7eaf338a6c865e34e5f17d4241f53e942f757e6c",
 "reference/crt27_mont_mutation_regression.py": "738e556e1b332a08d0b47a2bb072405269542bff7b0ca17512a0ac3a2d665cf1"
}
RUNNER='reference/crt27_mont_mutation_regression.py';POSITIVE='reference/crt27_mont_regression.py'
SOURCE='/home/jtl/gfn-fpga-lab/agent-work/crt27-mont/snapshot-v2/fpga'
REMOTE='/home/jtl/gfn-fpga-lab/agent-work/crt27-mont/mutations-v1'
POSITIVE_REMOTE='/home/jtl/gfn-fpga-lab/agent-work/crt27-mont/positive-v1'
POSITIVE_SOURCE=SOURCE.replace('snapshot-v2','snapshot-v1')
MANIFEST_SHA='9fc362426b92a77842091eaed3a50c57aa8314b4fcb64f564d6368d0c6acf68c'
POSITIVE_MANIFEST_SHA='814055f825fcafedc2caaf43ae8f034f0822eebdff562e8732d340d21fbc08a4'
POSITIVE_REPORT_SHA='0de1c9265012e430c3af8e1d4992538ba25f62c13021ed9eb7ab88dde980a3fd'
STAGE_ARCHIVE_SHA='b3e49e381fe7c35c8d30da9915d67313c65de428d49c1152e11d9a3e01e24718'
VECTOR_SHA='8ffb02df5fc819ac47c4ab06713c4b2ed0669cb3323a418905d0fe938ea58167'
VECTOR_BYTES=75776289
CANDIDATE='rtl/kernel/genefer_crt3_27_mont_pipe.sv'
MUTATIONS=('cb-off-one','center-ge','t2m3-removed')
FOOTER=('cycles','accepted','baseline_checked','candidate_checked','matched','baseline_canceled','candidate_canceled',
        'hold_checks','async_checks','port_checks','resets','bubbles','discarded_partial')
TOOL_PINS={
 '/usr/bin/python3.14':'52e0a13e60a981d8c4b6478be2ba5176f69da07948a056bf49cf6f077e30cb41',
 '/usr/bin/x86_64-linux-gnu-g++-15':'e6718f7e0c7d057c3ff77b550c603da9bc4030e3ede3c053705acce1293dbe4d',
 '/home/jtl/gfn-fpga-lab/tools/verilator/usr/bin/verilator':'672a1ccf3468902f66387049f001b04f254bbcece7d5e816e3861715889bf252',
 '/usr/bin/make':'27c9f6d806aee15882b01c2c61848f7aa75caa14bc7b6f608ba422f9e46a7d49',
 '/home/jtl/gfn-fpga-lab/tools/verilator/usr/bin/verilator_bin':'90fe12f3b2c752b607690cb05a566646398d1e07f38e83f5f7a7f35c20560247'}
COMMON_SHA='84c3d9416b1b2306f737f30066b00601fd5c13085a971ee8466028910528a749'


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def digest(data):return hashlib.sha256(data).hexdigest()


def common():
    directory=Path(__file__).resolve().parent;path=directory/'verify_root_recurrence27_periodmask_pair_offline.py'
    require(sha(path)==COMMON_SHA and __package__,'pinned generic offline archive helper; use python -m')
    from . import verify_root_recurrence27_periodmask_pair_offline as result
    require(Path(result.__file__).resolve()==path and sha(path)==COMMON_SHA,'generic helper import identity')
    return result


def strict(actual,wanted,label):common().strict_equal(actual,wanted,label)


def original_pins():
    return {key:value for key,value in PINS.items() if key not in (RUNNER,'docs/briefs/2026-09-30-answers-B20260930.md')}


def expected_records(random_cases=1000000):
    """Independent input-sequence reconstruction; expected values use CRT sum."""
    rng=random.Random(20260930)
    def value(x,label):return ('STEP',True,tuple(x%p for p in PRIMES),label)
    def drain():
        for _ in range(64):yield ('STEP',False,(0xffffffff,0x80000001,1<<27),'drain')
    yield ('RESET',)
    edge=[sorted(set([0,1,2,p//2-1,p//2,p//2+1,p-2,p-1])) for p in PRIMES]
    edge[0]=sorted(set(edge[0]+[PRIMES[1]-1,PRIMES[1],PRIMES[1]+1,PRIMES[2]-1,PRIMES[2],PRIMES[2]+1]))
    for r1 in edge[0]:
        for r2 in edge[1]:
            for r3 in edge[2]:yield ('STEP',True,(r1,r2,r3),'cross_edges')
    for x in [0,1,-1,2,-2,HALF-1,HALF,HALF+1,-HALF-1,-HALF,-HALF+1,M-1,M,M+1,-M-1,-M,-M+1]:yield value(x,'center')
    for r1 in [0,1,PRIMES[2]-1,PRIMES[2],PRIMES[0]-1]:
        for t2 in [0,1,PRIMES[2]-1,PRIMES[2],PRIMES[2]+1,PRIMES[1]-2,PRIMES[1]-1]:
            r2=(r1+PRIMES[0]*t2)%PRIMES[1]
            for r3 in [0,1,PRIMES[2]-1]:yield ('STEP',True,(r1,r2,r3),'t2m3_witness')
    yield from drain()
    for _ in range(random_cases):
        yield ('STEP',True,tuple(rng.randrange(p) for p in PRIMES),'random_accepted')
        if rng.randrange(5)==0:
            for _ in range(1+rng.randrange(3)):yield ('STEP',False,tuple(rng.randrange(1<<32) for _ in PRIMES),'random_bubble')
    yield from drain()
    for age in range(61):
        yield ('RESET',);yield value(HALF-age,'age_input')
        for _ in range(age):yield ('STEP',False,(0xffffffff,0xffffffff,0xffffffff),'age_bubble')
        yield ('RESET',)
        for offset in range(16):yield value(HALF-offset-1,'age_recovery')
        yield from drain()
    for index in range(4096):
        if index%101==100:yield ('RESET',)
        valid=rng.randrange(4)!=0
        residues=tuple(rng.randrange(p) for p in PRIMES) if valid else tuple(rng.randrange(1<<32) for _ in PRIMES)
        yield ('STEP',valid,residues,'reset_stress_valid' if valid else 'reset_stress_bubble')
    yield from drain()


def direct_crt(residues):
    require(len(residues)==3 and all(type(r) is int and 0<=r<p for r,p in zip(residues,PRIMES)),'canonical independent CRT residues')
    # Textbook CRT, unrelated to the candidate's Montgomery/Garner schedule.
    value=sum(r*term for r,term in zip(residues,CRT_TERMS))%M
    return value-M if value>HALF else value


def audit_vectors(path,random_cases=1000000):
    """Fresh coefficients, seed/geometry sequence and separate transaction IDs."""
    row=dict.fromkeys(FOOTER,0);queues=(deque(),deque());records={};categories=Counter()
    with Path(path).open('r',encoding='ascii',newline='') as stream:
        require(stream.readline()=='CRT27_MONT_V1 candidate_delay=15 frozen_delay=60 coefficient_bits=96\n','vector header')
        for event in expected_records(random_cases):
            if event[0]=='RESET':
                require(stream.readline()=='RESET\n','reset event vector')
                row['baseline_canceled']+=len(queues[0]);row['candidate_canceled']+=len(queues[1]);row['discarded_partial']+=len(records)
                for queue in queues:queue.clear()
                records.clear();row['resets']+=1;row['async_checks']+=4;row['port_checks']+=4
                continue
            _,valid,residues,label=event;categories[label]+=1
            expected=direct_crt(residues) if valid else 0
            line='STEP '+str(int(valid))+' '+' '.join(map(str,residues))+' '+str(expected)+'\n'
            require(stream.readline()==line,'fresh independent CRT/input sequence mismatch')
            clock=row['cycles']
            if valid:
                index=row['accepted'];row['accepted']+=1;records[index]=0
                for queue,delay in zip(queues,(60,15)):queue.append((clock+delay,index))
            else:row['bubbles']+=1
            fired=0
            for side,(queue,key) in enumerate(zip(queues,('baseline_checked','candidate_checked'))):
                if queue and queue[0][0]==clock:
                    _,index=queue.popleft();row[key]+=1;fired+=1;records[index]|=1<<side
                    if records[index]==3:row['matched']+=1;del records[index]
                require(not queue or queue[0][0]>clock,'unconsumed due event')
            row['hold_checks']+=2-fired;row['port_checks']+=4;row['cycles']+=1
        require(stream.readline()=='' and not any(queues) and not records,'complete vectors and output drain')
    return dict(sha256=sha(path),bytes=Path(path).stat().st_size,seed=20260930,random_accepted=random_cases,
        categories=dict(categories),reset_ages=list(range(61)),counts=row,
        oracle='Direct ordinary-integer CRT sum; no candidate Montgomery/Garner expression.')


def check_footer(text,wanted):
    match=re.fullmatch('PASS '+' '.join(key+r'=(\d+)' for key in FOOTER)+r'\n?',text)
    require(match is not None,'one complete exact CRT footer')
    actual=dict(zip(FOOTER,map(int,match.groups())));strict(actual,wanted,'independent raw normal counters');return actual


def probe(text):
    actual=json.loads(text);wanted=dict(context_threads=1,model_threads=1,candidate_delay=15,frozen_delay=60,
        coefficient_bits=96,p1=PRIMES[0],p2=PRIMES[1],p3=PRIMES[2])
    strict(actual,wanted,'typed compiled delay/profile probe');return actual


def once(text,old,new):
    require(text.count(old)==1,'unique independent source anchor');return text.replace(old,new)


def derived_sources(candidate):
    require(digest(candidate.encode())==PINS[CANDIDATE],'frozen candidate source identity')
    begin='    // CRT27_CONSTANT_CHECK_BEGIN\n';end='    // CRT27_CONSTANT_CHECK_END\n'
    require(candidate.count(begin)==candidate.count(end)==1,'constant block fences')
    first=candidate.index(begin);last=candidate.index(end)+len(end)
    stripped=candidate[:first]+'    // G2 arithmetic sensitivity only: constant checker omitted in this control/mutant pair.\n'+candidate[last:]
    cb=lambda text:once(text,"localparam logic [31:0] CB=32'd62755090;","localparam logic [31:0] CB=32'd62755091;")
    return {
      'mutant-active-cb-guard.sv':cb(candidate),'control-cb-off-one.sv':stripped,'mutant-cb-off-one.sv':cb(stripped),
      'control-center-ge.sv':candidate,
      'mutant-center-ge.sv':once(candidate,'wire signed [95:0] centered_work=value>(MODULUS>>1) ?','wire signed [95:0] centered_work=value>=(MODULUS>>1) ?'),
      'control-t2m3-removed.sv':candidate,
      'mutant-t2m3-removed.sv':once(candidate,'wire [26:0] t2_mod3=t2[26:0]>=P3 ? t2[26:0]-P3 : t2[26:0];','wire [26:0] t2_mod3=t2[26:0];')}


def rejection(step,text,wanted,arithmetic=False):
    require(type(step['returncode']) is int and step['returncode']!=0 and step['error'] is None,'typed negative process status')
    require(step['expected_typed_rejection']==wanted,'explicit negative class expectation')
    matched=[token for token in wanted if token in text];require(matched,'missing raw typed negative diagnosis')
    strict(step['matched_typed_rejections'],matched,'raw/recorded rejection markers')
    if arithmetic:require(step['returncode']==1 and text=='CRT27_MONT_ARITHMETIC_SIGN_MISMATCH\n','caught arithmetic mismatch, not early guard/crash')
    require('PASS cycles=' not in text,'negative cannot contain a passing normal footer')


def build_command(source,scratch,name,candidate):
    return ['verilator','--cc','--exe','--build','-j','2','--threads','1','--assert','--top-module',TOP,
        '-GCANDIDATE_DELAY=15','-GFROZEN_DELAY=60','-CFLAGS',
        '-std=c++17 -Werror=return-type -DCRT27_CANDIDATE_DELAY=15 -DCRT27_FROZEN_DELAY=60',
        '--Mdir',scratch+'/build-'+name,*[candidate if path==CANDIDATE else source+'/'+path for path in ORDER]]


def generated(members,build_log,source):
    prefix='V'+TOP
    require(len(members)==15 and all('/' not in key and PurePosixPath(key).suffix in ('.cpp','.h','.mk','.dat') for key in members),'exact generated artifact kinds')
    for suffix in ('.cpp','.h','.mk','___024root.h','__verFiles.dat'):require(prefix+suffix in members,'generated model closure')
    cpp=members[prefix+'.cpp'].decode();header=members[prefix+'.h'].decode();make=members[prefix+'.mk'].decode()
    require(re.search(r'unsigned '+prefix+r'::threads\(\) const \{ return 1; \}',cpp),'single generated model thread')
    for name in ('baseline','candidate'):
        for token in (f'VL_OUT8(&{name}_ready,0,0);',f'VL_OUT8(&{name}_valid,0,0);',f'VL_OUTW(&{name}_coefficient,95,0,3);'):
            require(header.count(token)==1,'both complete output port dimensions')
    require('explicit '+prefix+'(VerilatedContext* contextp, const char* name = "TOP");' in header,'explicit generated context ABI')
    flags=['-std=c++17','-Werror=return-type','-DCRT27_CANDIDATE_DELAY=15','-DCRT27_FROZEN_DELAY=60']
    match=re.search(r'VM_USER_CFLAGS = \\\n(.*?)\n\n',make,re.S)
    require(match and shlex.split(match.group(1).replace('\\',''))==flags,'generated strict delay/warning flags')
    require('VM_USER_CLASSES = \\\n\t'+TOP+' \\\n' in make,'one reviewed bench translation unit')
    rows=[]
    for line in build_log.splitlines():
        if line.startswith('g++ '):
            tokens=shlex.split(line)
            if '-c' in tokens and source+'/rtl/tb/'+TOP+'.cpp' in tokens:rows.append(tokens)
    require(len(rows)==1,'actual bench compiled once')
    tokens=rows[0];require(tokens[-1]==source+'/rtl/tb/'+TOP+'.cpp' and tokens[tokens.index('-o')+1]==TOP+'.o','exact compiled bench/source')
    require([token for token in tokens if token.startswith('-DCRT27_')]==flags[2:] and tokens.count('-Werror=return-type')==1 and
        not any(token.startswith('-U') for token in tokens) and '-w' not in tokens and '-Wno-error=return-type' not in tokens,'actual compiler macro/return contract')
    require('control reaches end of non-void function' not in build_log,'no renamed-main undefined-return warning')


def resource_contract(report,durable,suffix):
    wanted=dict(compile_workers=2,model_threads=1,scratch_reservation_bytes=768<<20,scratch_free_floor_bytes=2<<30,
        durable_reservation_bytes=durable<<20,durable_free_floor_bytes=10<<30,host_memory_floor_bytes=4<<30,
        command_timeout_seconds=1800,lock_wait_timeout_seconds=1800)
    for name,value in wanted.items():strict(report[name],value,'resource '+name)
    limits=report['limits'];strict(limits['affinity'],[0,2],'physical CPU affinity')
    require(type(limits['memory_max_bytes']) is int and 0<limits['memory_max_bytes']<=6<<30,'finite memory limit')
    cpu=limits['cpu_max'];require(type(cpu) is list and len(cpu)==2 and all(type(v) is str and re.fullmatch(r'\d+',v) for v in cpu) and
        int(cpu[1])>0 and 0<int(cpu[0])<=2*int(cpu[1]),'finite two-CPU quota')
    cores=limits['physical_cores'];require(type(cores) is list and len(cores)==2 and all(type(pair) is list and len(pair)==2 and
        all(type(v) is int and v>=0 for v in pair) for pair in cores) and len({tuple(pair) for pair in cores})==2,'two distinct physical cores')
    require(limits['cgroup'].endswith('/'+suffix+'.service'),'native unit identity')
    prefix='/dev/shm/gfn16-crt27-mont-'+('neg-' if durable==64 else '')
    require(re.fullmatch(re.escape(prefix)+r'[a-z0-9_]+',report['scratch']) and
        report['compiler_temporary_directory']==report['scratch']+'/tmp','isolated scratch/temp')


def raw_artifacts(root,report,roles):
    c=common();require(set(report['artifacts'])==set(roles),'complete exact durable artifact roles')
    for name,value in report['artifacts'].items():
        require(type(value) is str and re.fullmatch('[0-9a-f]{64}',value) and sha(c.local_file(root,name))==value,'raw artifact hash: '+name)


def step_contract(root,report,names,negative_names):
    c=common();require([step['name'] for step in report['steps']]==names,'exact ordered native step coverage')
    steps={step['name']:step for step in report['steps']}
    for name,step in steps.items():
        require(type(step['returncode']) is int and step['error'] is None,'native step exit/error type')
        if name not in negative_names:require(step['returncode']==0,'failed passing-control/build step')
        require(type(step['seconds']) in (int,float) and math.isfinite(step['seconds']) and 0<=step['seconds']<=1802,'bounded finite step time')
        require(step['log']==name+'.log' and step['sha256']==report['artifacts'][step['log']] and
            sha(c.local_file(root,step['log']))==step['sha256'],'step/raw artifact hash binding')
    return steps


def audit_positive(root,coverage):
    c=common();root=Path(root).resolve();report=json.loads(c.local_file(root,'report.json').read_text())
    require(sha(root/'report.json')==POSITIVE_REPORT_SHA and sha(c.local_file(root,'approved-manifest.json'))==POSITIVE_MANIFEST_SHA,'original positive receipt identity')
    manifest=json.loads((root/'approved-manifest.json').read_text())
    require(report['status']=='passed_positive_only_mutations_pending' and 'error' not in report and
        report['scope']=='Unequal-latency paired CRT27 component positive stream only' and report['top']==TOP,'positive receipt scope, not full G2 alone')
    strict(report['sources'],original_pins(),'nine-source parent closure');strict(manifest['sources'],original_pins(),'positive prepared closure')
    strict(report['profile'],PROFILE,'positive profile');strict(manifest['profile'],PROFILE,'positive manifest profile')
    strict(report['compiled_source_order'],ORDER,'positive compiled six sources')
    strict(report['vectors'],coverage,'positive independent vectors');strict(manifest['vectors'],coverage,'prepared independent vectors')
    require(report['manifest_sha256']==POSITIVE_MANIFEST_SHA and manifest['source_root']==POSITIVE_SOURCE and manifest['top']==TOP and
        manifest['status']=='prepared_positive_only_not_executed','positive source/manifest binding')
    resource_contract(report,192,'gfn-crt27-mont-positive-v1')
    tools={name:value for name,value in TOOL_PINS.items() if name not in ('/usr/bin/make','/home/jtl/gfn-fpga-lab/tools/verilator/usr/bin/verilator_bin')}
    strict(report['tool_executable_sha256'],tools,'positive tool receipts')
    names=['verilator-version','g++-version','g1-oracle','build','probe','normal']
    roles=[name+'.log' for name in names]+['approved-manifest.json','sources.tar.gz','vectors.txt','V'+TOP,'generated-sources.tar.gz']
    raw_artifacts(root,report,roles);steps=step_contract(root,report,names,set())
    sources=c.archive(root/'sources.tar.gz',original_pins());members=c.archive(root/'generated-sources.tar.gz')
    strict({key:digest(value) for key,value in members.items()},report['generated_source_sha256'],'positive generated source hashes')
    generated(members,(root/'build.log').read_text(),POSITIVE_SOURCE)
    executable=POSITIVE_REMOTE+'/V'+TOP
    require(report['executable']==executable and report['executable_sha256']==report['artifacts']['V'+TOP],'positive executable binding')
    command=build_command(POSITIVE_SOURCE,report['scratch'],'unused',POSITIVE_SOURCE+'/'+CANDIDATE)
    command[command.index('--Mdir')+1]=report['scratch']+'/build'
    wanted={'verilator-version':['verilator','--version'],'g++-version':['g++','--version'],
        'g1-oracle':['/usr/bin/python3','-B',POSITIVE_SOURCE+'/docs/briefs/crt27_mont_oracle.py'],
        'build':command,'probe':[executable,'--runtime-probe'],'normal':[executable,'--normal',POSITIVE_REMOTE+'/vectors.txt']}
    for name,argv in wanted.items():strict(steps[name]['command'],argv,'positive command '+name)
    require((root/'g1-oracle.log').read_text()=='C2=12212947 (0xba5ad3) CA=28766354 (0x1b6f092) CB=62755090 (0x3bd9112) P12=7256776917385217\nPASS 300775 cases\n','actual G1 oracle result')
    strict(probe((root/'probe.log').read_text()),report['probe'],'positive raw/reported probe')
    strict(check_footer((root/'normal.log').read_text(),coverage['counts']),report['normal_counts'],'positive raw/reported normal counters')
    return report,manifest,sources


def verify(negative_root,positive_root):
    c=common();root=Path(negative_root).resolve();parent=Path(positive_root).resolve()
    # Fresh math and RNG/input sequence, not execution of any archived program.
    vector=c.local_file(parent,'vectors.txt');require(sha(vector)==VECTOR_SHA and vector.stat().st_size==VECTOR_BYTES,'frozen reused vector identity')
    coverage=audit_vectors(vector);require(coverage['random_accepted']==1000000 and coverage['counts']['matched']>=1000000,'million accepted/matched random scope')
    prior,positive_manifest,old_sources=audit_positive(parent,coverage)
    report_file=c.local_file(root,'report.json');report=json.loads(report_file.read_text())
    require(report['status']=='passed_required_mutations_and_fresh_controls' and 'error' not in report and
        report['scope']=='CRT27 required typed negatives plus freshly rebuilt unequal-latency paired controls' and report['top']==TOP,'complete mutation receipt scope/status')
    manifest_path=c.local_file(root,'approved-manifest.json');require(sha(manifest_path)==MANIFEST_SHA,'approved mutation manifest bytes')
    manifest=json.loads(manifest_path.read_text())
    require(manifest['status']=='prepared_required_mutations_not_executed' and manifest['source_root']==SOURCE and manifest['top']==TOP and
        manifest['archive_sha256']==STAGE_ARCHIVE_SHA and report['manifest_sha256']==MANIFEST_SHA,'mutation prepared source/manifest identity')
    strict(report['sources'],PINS,'eleven-source mutation closure');strict(manifest['sources'],PINS,'approved mutation closure')
    strict(report['profile'],PROFILE,'mutation profile');strict(manifest['profile'],PROFILE,'approved profile')
    strict(manifest['compiled_source_order'],ORDER,'six-source compile order')
    strict(report['vectors'],coverage,'mutation fresh vector coverage');strict(manifest['vectors'],coverage,'mutation approved vector coverage')
    require(sha(c.local_file(root,'approved-positive-manifest.json'))==POSITIVE_MANIFEST_SHA and
        manifest['positive_manifest_sha256']==POSITIVE_MANIFEST_SHA and manifest['positive_report_sha256']==POSITIVE_REPORT_SHA and
        manifest['reused_vector_path']==POSITIVE_REMOTE+'/vectors.txt','original positive linkage')
    reused={POSITIVE_REMOTE+'/vectors.txt':VECTOR_SHA,POSITIVE_REMOTE+'/report.json':POSITIVE_REPORT_SHA,
            POSITIVE_REMOTE+'/approved-manifest.json':POSITIVE_MANIFEST_SHA}
    strict(report['reused_inputs'],reused,'external read-only input identities')
    resource_contract(report,64,'gfn-crt27-mont-mutations-v2');strict(report['tool_executable_sha256'],TOOL_PINS,'five native tool receipts')
    names=['verilator-version','g++-version','make-version','verilator-bin-version','build-pristine','probe-pristine','normal-pristine']
    input_rows=[]
    for role in ('baseline','candidate'):
        for port,prime in enumerate(PRIMES):
            for value in (prime,prime+1,1<<27,0x80000001,0xffffffff):
                name=f'reject-{role}-p{port}-{value}';names.append(name);input_rows.append(dict(role=role,port=port,value=value,step=name))
    names+=['build-active-cb-guard','reject-active-cb-guard']
    for name in MUTATIONS:names+=['build-mutant-'+name,'reject-'+name,'build-control-'+name,'probe-control-'+name,'normal-control-'+name]
    builds=['pristine','active-cb-guard']+[prefix+name for name in MUTATIONS for prefix in ('mutant-','control-')]
    derived=derived_sources(old_sources[CANDIDATE].decode())
    roles=({name+'.log' for name in names}|set(derived)|{'V'+TOP+'-'+name for name in builds}|{'generated-'+name+'.tar.gz' for name in builds}|
        {'approved-manifest.json','approved-positive-manifest.json','sources.tar.gz'})
    raw_artifacts(root,report,roles)
    negative_names={row['step'] for row in input_rows}|{'reject-active-cb-guard'}|{'reject-'+name for name in MUTATIONS}
    steps=step_contract(root,report,names,negative_names)
    strict(report['input_rejections'],input_rows,'all thirty port/role/high-bit rejections')
    sources=c.archive(root/'sources.tar.gz',PINS)
    require(all(sources[key]==value for key,value in old_sources.items()),'frozen original nine bytes unchanged')
    strict(report['derived_sources'],{name:digest(text.encode()) for name,text in derived.items()},'exact seven derived source identities')
    for name,text in derived.items():require(c.local_file(root,name).read_bytes()==text.encode(),'literal independent mutation/control transformation')
    wanted_versions={'verilator-version':['verilator','--version'],'g++-version':['g++','--version'],'make-version':['make','--version'],
        'verilator-bin-version':['/home/jtl/gfn-fpga-lab/tools/verilator/usr/bin/verilator_bin','--version']}
    for name,argv in wanted_versions.items():strict(steps[name]['command'],argv,'tool version command')
    for name,key in [('verilator-version','verilator_version'),('g++-version','g++_version'),('make-version','make_version'),('verilator-bin-version','verilator_bin_version')]:
        require((root/(name+'.log')).read_text().strip()==report[key],'raw tool-version receipt')
    require(report['verilator_version']==prior['verilator_version'] and report['g++_version']==prior['g++_version'],'matched parent tool versions')
    require(list(report['builds'])==builds,'exact eight fresh compilation identities')
    generated_total=0
    for name in builds:
        row=report['builds'][name]
        source=SOURCE+'/'+CANDIDATE if name=='pristine' else REMOTE+'/'+('mutant-active-cb-guard.sv' if name=='active-cb-guard' else name+'.sv')
        local_source=root/CANDIDATE if name=='pristine' else root/('mutant-active-cb-guard.sv' if name=='active-cb-guard' else name+'.sv')
        expected_sha=PINS[CANDIDATE] if name=='pristine' else digest(derived[local_source.name].encode())
        executable=REMOTE+'/V'+TOP+'-'+name
        strict(row['candidate'],source,'compiled candidate path');strict(row['candidate_sha256'],expected_sha,'compiled candidate source identity')
        require(row['executable']==executable and row['executable_sha256']==report['artifacts']['V'+TOP+'-'+name] and
            row['generated_archive']=='generated-'+name+'.tar.gz','fresh executable/generated archive binding')
        strict(steps['build-'+name]['command'],build_command(SOURCE,report['scratch'],name,source),'exact source-ordered build command')
        members=c.archive(root/row['generated_archive']);generated_total+=len(members)
        strict({key:digest(value) for key,value in members.items()},row['generated_source_sha256'],'all generated member identities')
        generated(members,(root/('build-'+name+'.log')).read_text(),SOURCE)
    pristine=REMOTE+'/V'+TOP+'-pristine';vectors=POSITIVE_REMOTE+'/vectors.txt'
    strict(steps['probe-pristine']['command'],[pristine,'--runtime-probe'],'pristine compiled probe command')
    strict(steps['normal-pristine']['command'],[pristine,'--normal',vectors],'pristine million-case command')
    strict(probe((root/'probe-pristine.log').read_text()),report['probe'],'pristine raw probe')
    strict(check_footer((root/'normal-pristine.log').read_text(),coverage['counts']),report['pristine_counts'],'pristine full positive counters')
    for row in input_rows:
        name=row['step'];strict(steps[name]['command'],[pristine,'--reject',row['role'],str(row['port']),str(row['value'])],'isolated canonical guard command')
        rejection(steps[name],(root/(name+'.log')).read_text(),['noncanonical CRT27 input'])
    strict(steps['reject-active-cb-guard']['command'],[REMOTE+'/V'+TOP+'-active-cb-guard','--runtime-probe'],'active constant guard command')
    rejection(steps['reject-active-cb-guard'],(root/'reject-active-cb-guard.log').read_text(),['CRT27 Montgomery constants'])
    require(report['active_constant_guard']=='typed constant identity rejection; not an arithmetic mismatch','separate active constant guard category')
    strict(set(report['mutations']),set(MUTATIONS),'all required mutation verdicts')
    mutation_verdicts={}
    for name in MUTATIONS:
        row=report['mutations'][name];arithmetic=name!='t2m3-removed'
        category='arithmetic_mismatch' if arithmetic else 'internal_bound_rejection'
        expected=['CRT27_MONT_ARITHMETIC_SIGN_MISMATCH'] if arithmetic else ['CRT27 t2_mod3 bound','noncanonical Montgomery27 input']
        strict(row['category'],category,'honest negative category');strict(row['omitted_constant_checker'],name=='cb-off-one','paired-only constant omission')
        mutant_sha=digest(derived['mutant-'+name+'.sv'].encode());control_sha=digest(derived['control-'+name+'.sv'].encode())
        strict(row['mutant_sha256'],mutant_sha,'mutant digest');strict(row['control_sha256'],control_sha,'fresh control digest')
        strict(manifest['required_mutations'][name],dict(omitted_constant_checker=name=='cb-off-one',category=category,expected=expected,
            control_sha256=control_sha,mutant_sha256=mutant_sha),'approved derivative contract')
        negative='reject-'+name;control='normal-control-'+name
        require(row['negative_step']==negative and row['control_step']==control,'negative/fresh-control pairing')
        strict(steps[negative]['command'],[REMOTE+'/V'+TOP+'-mutant-'+name,'--normal',vectors],'exact mutant normal command')
        rejection(steps[negative],(root/(negative+'.log')).read_text(),expected,arithmetic)
        executable=REMOTE+'/V'+TOP+'-control-'+name
        strict(steps['probe-control-'+name]['command'],[executable,'--runtime-probe'],'fresh control compiled probe')
        strict(steps[control]['command'],[executable,'--normal',vectors],'fresh same-stream million control')
        strict(probe((root/('probe-control-'+name+'.log')).read_text()),row['fresh_control_probe'],'fresh typed control probe')
        strict(check_footer((root/(control+'.log')).read_text(),coverage['counts']),row['fresh_control_counts'],'fresh full control counters')
        require(names.index(negative)<names.index('build-control-'+name)<names.index(control),'fresh build/run follows required typed failure')
        mutation_verdicts[name]=dict(category=category,returncode=steps[negative]['returncode'],fresh_control_matched=coverage['counts']['matched'])
    return dict(status='verified_G2_component_correctness_and_required_mutation_sensitivity',
        scope='Atomic27 standalone paired two-state CRT only',candidate_delay_edges=15,candidate_pipeline_stages=16,
        frozen_delay_edges=60,frozen_pipeline_stages=61,stage_delta=-45,random_accepted=1000000,
        counts=coverage['counts'],canonical_guard_rejections=30,reset_ages=list(range(61)),mutations=mutation_verdicts,
        source_members=len(sources),original_source_members=len(old_sources),artifacts=len(roles),builds=len(builds),generated_members=generated_total,
        report_sha256=sha(report_file),positive_report_sha256=POSITIVE_REPORT_SHA,manifest_sha256=MANIFEST_SHA,
        vector_sha256=VECTOR_SHA,verifier_sha256=sha(Path(__file__)),generic_audit_helper_sha256=COMMON_SHA,
        limitation='No archived binary executed. Fresh direct integer CRT and seeded input reconstruction plus recorded native transactions/guards/negative controls establish this finite G2 scope, not a formal proof. No G3 resources/clock/fit, whole-core integration or cycle reduction, board, PRP or new arithmetic-profile qualification. Native tool hashes and execution receipts are provenance, not independent remote attestation.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('negative_archive',type=Path);parser.add_argument('positive_archive',type=Path)
    parser.add_argument('--output',type=Path);args=parser.parse_args();result=verify(args.negative_archive,args.positive_archive)
    payload=json.dumps(result,indent=2)+'\n'
    if args.output:
        require(not args.output.exists(),'fresh verification output');args.output.write_text(payload)
    print(payload,end='')


if __name__=='__main__':main()
