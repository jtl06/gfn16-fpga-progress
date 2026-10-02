"""Independent read-only evidence audit for a paired host-memory profile.

Imports only the separately pinned pure expected-counter oracle, never the
simulation runner. Does not execute archived binaries. Counter/trace values
from the oracle describe the EXPECTED schedule, not a hardware trace capture.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shlex
import tarfile

ORACLE_SHA='4b819c0a8ac0bb4e5ad3b1202a24ac5f04c1d9b8d639c6f8a24116552485d2ff'
PLAN='synthesis/host_broadcast_memory_pair_plan.json'
PLAN_SHA='2815d1602fbb99cf2964ea5a16fe991851cf272d7bf54862eb0b6b3b977d6332'
PROOF='reference/core27_prefetch_r2_host_broadcast_structure.py'
PROOF_SHA='daab10e0e5b4d5976ec4f36beef2e1d8dc926b16af54a021d67212b3f8a55d8a'
ORACLE='reference/host_broadcast_memory_oracle.py'
RUNNER='reference/host_broadcast_memory_pair_regression.py'
RUNNER_SHA='2bcf6db450d523f00ce60c53c599785060e08c73a5db9e5bd29be49d0ea149e2'
COVERAGE_NOTE=('Historical source plan retained unchanged. Later local runner review also permits AW16/P1 '
               'preparation explicitly with --aw 16. First invocation remains AW8/P1; full-width execution '
               'requires its own approved manifest after smoke completion and resource review. No autonomous launch.')
TOP='host_broadcast_memory_pair'
SOURCE=Path('/home/jtl/gfn-fpga-lab/agent-work/host-broadcast-memory/snapshot-v1/fpga')
CHILD='genefer_ntt_banked27_prefetch_r2_engine'
FIELDS={1:(104857601,4190109697),2:(69206017,4225761281),3:(67239937,4227727361)}
PROFILES={(1,1),(5,1),(8,1),(8,2),(8,3),(16,1)}
GiB=1<<30
MiB=1<<20


def require(value,message):
    if not value:raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def valid_hash(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def expected(aw,field):
    # Verify before executing the sole project import.
    path=Path(__file__).with_name('host_broadcast_memory_oracle.py')
    require(sha(path)==ORACLE_SHA,'independent oracle identity')
    if __package__:
        from . import host_broadcast_memory_oracle as oracle
    else:
        import host_broadcast_memory_oracle as oracle
    require(Path(oracle.__file__).resolve()==path.resolve(),'oracle import path')
    result=oracle.expected_result(aw,field)
    return result,oracle.canonical_footer(result)


def config_of(profile):
    aw,field=profile['aw'],profile['field']
    require(type(aw) is int and type(field) is int and (aw,field) in PROFILES,'reviewed AW/field')
    p,q=FIELDS[field]
    require(profile==dict(aw=aw,field=field,p=p,q=q),'exact parameter profile')
    return aw,field


def case_matrix(aw):
    require(aw in (1,5,8,16),'assertion geometry')
    quarters=min(4,((1<<aw)+15)//16)
    return [(who,kind,payload,quarter) for who in ('baseline','candidate') for kind in ('scalar','vector')
            for payload in ('p','highbit','u32max') for quarter in ((0,) if kind=='scalar' else range(quarters))]


def rejection(code,text,case):
    if type(code) is not int or code not in (1,-6,134):return False
    if len(case)!=4:return False
    who,kind,payload,quarter=case
    if who not in ('baseline','candidate') or kind not in ('scalar','vector') or payload not in ('p','highbit','u32max') or type(quarter) is not int or not 0<=quarter<4:return False
    lines=[line for line in text.splitlines() if line]
    marker=f'EXPECT_CANONICAL_ASSERT instance={who} kind={kind} payload={payload} quarter={quarter}'
    if not lines or lines.pop(0)!=marker:return False
    location=r'(?:'+re.escape(str(SOURCE/'rtl/kernel'))+r'/)?'+CHILD+r'\.sv:395'
    hierarchy=f'TOP.{TOP}.instances[{0 if who=="baseline" else 1}].{who}.dut.child.memories[{quarter*16}]'
    fatal=r'\[\d+\] %(?:Error|Fatal): '+location+r': Assertion failed in '+re.escape(hierarchy)+r': noncanonical NTT27 data write'
    if not lines or re.fullmatch(fatal,lines.pop(0)) is None:return False
    if lines and re.fullmatch(r'%Error: '+location+r': Verilog \$stop',lines[0]):lines.pop(0)
    if lines and lines[0]=='Aborting...':lines.pop(0)
    return not lines


def archive_members(path,pins):
    data={}
    with tarfile.open(path) as archive:
        entries=archive.getmembers()
        require(len(entries)==len(pins) and set(archive.getnames())==set(pins),'archive member coverage')
        for entry in entries:
            name=entry.name
            require(entry.isfile() and not Path(name).is_absolute() and '..' not in Path(name).parts,'unsafe archive member')
            contents=archive.extractfile(entry).read()
            require(valid_hash(pins[name]) and hashlib.sha256(contents).hexdigest()==pins[name],'archive member SHA: '+name)
            data[name]=contents
    return data


def artifact_files(root,pins):
    for name,digest in pins.items():
        path=root/name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and
                path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root),'artifact path')
        require(valid_hash(digest) and sha(path)==digest,'artifact hash: '+name)


def approved_sources(plan):
    require(valid_hash(RUNNER_SHA),'reviewed runner hash not finalized')
    pins=dict(plan['source_sha256']);order=plan['compile_contract']['source_order']
    require(plan['top']==TOP and len(pins)==len(order)==10 and len(set(order))==10 and set(pins)==set(order),'compiled ten-source closure')
    pins.update({PLAN:PLAN_SHA,PROOF:PROOF_SHA,ORACLE:ORACLE_SHA,RUNNER:RUNNER_SHA})
    require(len(pins)==14 and all(valid_hash(x) for x in pins.values()),'complete fourteen-source closure')
    return pins,order


def report_contract(report,manifest,pins,order,oracle_result):
    require(report.get('status')=='passed_host_memory_pair' and 'error' not in report,'incomplete/resource-failed report')
    require(report['scope']=='Standalone paired host-memory equivalence; no completed NTT operation','scope')
    aw,field=config_of(report['profile']);counts=oracle_result['counts']
    require(report['sources']==pins and report['compiled_source_order']==order and report['plan_sha256']==PLAN_SHA,'report source closure')
    require(report['runner_coverage_annotation']==manifest['runner_coverage_annotation']==COVERAGE_NOTE,'explicit later-profile coverage annotation')
    require(manifest['status']=='prepared_not_executed' and manifest['source_root']==str(SOURCE) and
            manifest['sources']==pins and manifest['compiled_source_order']==order and manifest['plan_sha256']==PLAN_SHA and
            manifest['profile']==report['profile'] and manifest['expected_counts']==counts and valid_hash(manifest['archive_sha256']),'prepared manifest contract')
    require(report['expected_counts']==report['normal_counts']==counts and
            all(type(x) is int for x in report['normal_counts'].values()),'independent expected/observed counters')
    cases=case_matrix(aw)
    require(report['illegal_cases']==[list(c) for c in cases],'complete unique assertion matrix')
    names=['verilator-version','g++-version','build','probe','normal']+['reject-'+'-'.join(map(str,c)) for c in cases]
    require([s['name'] for s in report['steps']]==names,'exact command-role order/coverage')
    for step in report['steps']:
        name=step['name'];case=cases[names.index(name)-5] if name.startswith('reject-') else None
        require(step['error'] is None and type(step['returncode']) is int and
                (step['returncode'] in (1,-6,134) if case else step['returncode']==0),'failed/incomplete command')
        require(step['assertion_case']==(list(case) if case else None),'command assertion role')
        require(type(step['seconds']) in (int,float) and math.isfinite(step['seconds']) and 0<=step['seconds']<1802,'bounded command duration')
    scratch=Path(report['scratch'])
    require(scratch.parent==Path('/dev/shm') and scratch.name.startswith('gfn16-host-broadcast-memory-') and
            report['compiler_temporary_directory']==str(scratch/'tmp') and '..' not in scratch.parts,'private tmpfs path')
    limits=report['limits'];quota,period=map(int,limits['cpu_max'])
    require(0<limits['memory_max_bytes']<=6*GiB and period>0 and 0<quota<=2*period and
            limits['affinity']==[0,2] and len(limits['physical_cores'])==2 and len(set(map(tuple,limits['physical_cores'])))==2,'bounded physical-core allocation')
    for key,value in dict(compile_workers=2,model_threads=1,scratch_reservation_bytes=768*MiB,scratch_free_floor_bytes=2*GiB,
        durable_reservation_bytes=64*MiB,durable_free_floor_bytes=10*GiB,host_memory_floor_bytes=4*GiB,
        command_timeout_seconds=1800,lock_wait_timeout_seconds=1800).items():require(type(report[key]) is int and report[key]==value,'resource contract: '+key)
    tools=report['tool_executable_sha256']
    require(len(tools)==3 and all(Path(p).is_absolute() and '..' not in Path(p).parts and valid_hash(h) for p,h in tools.items()),'recorded tool hash identities')
    require(type(report['python_version']) is str and bool(report['python_version']),'recorded Python version')
    return {s['name']:s for s in report['steps']}


def commands(report,steps,order):
    profile=report['profile'];aw,p,q=profile['aw'],profile['p'],profile['q']
    exe=Path(report['executable']);out=exe.parent
    require(out.parent==SOURCE.parent.parent and '..' not in out.parts and exe.name=='V'+TOP,'durable executable path')
    flags=f'-std=c++17 -DHOST_BROADCAST_AW={aw} -DHOST_BROADCAST_P={p}u -DHOST_BROADCAST_Q={q}u'
    build=['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',TOP,
           f'-GAW={aw}',f'-GP={p}',f'-GQ={q}','-CFLAGS',flags,'--Mdir',str(Path(report['scratch'])/'build'),
           *[str(SOURCE/name) for name in order]]
    expected={'verilator-version':['verilator','--version'],'g++-version':['g++','--version'],
              'build':build,'probe':[str(exe),'--runtime-probe'],'normal':[str(exe)]}
    for case in case_matrix(aw):expected['reject-'+'-'.join(map(str,case))]=[str(exe),'--illegal',*map(str,case)]
    for name,argv in expected.items():require(steps[name]['command']==argv,'exact command identity: '+name)
    return flags


def generated_contract(members,build_log,flags):
    top='V'+TOP
    require(all(top+suffix in members for suffix in ('.cpp','.h','.mk')),'generated top closure')
    require(f'unsigned {top}::threads() const {{ return 1; }}' in members[top+'.cpp'].decode(),'generated model thread count')
    make=members[top+'.mk'].decode()
    match=re.search(r'^VM_USER_CFLAGS = \\\n(.*?)(?=\n#|\Z)',make,re.M|re.S)
    require(match is not None and shlex.split(match[1].replace('\\\n',' '))==shlex.split(flags),'generated actual C++ flags')
    source=str(SOURCE/'rtl/tb/host_broadcast_memory_pair.cpp');lines=[]
    for line in build_log.splitlines():
        if source not in line or ' -c ' not in line:continue
        tokens=shlex.split(line)
        if source in tokens:lines.append(tokens)
    require(len(lines)==1,'unique actual bench compilation evidence')
    actual=lines[0]
    for flag in shlex.split(flags):require(actual.count(flag)==1,'actual compiler parameter flag: '+flag)
    for name in ('HOST_BROADCAST_AW','HOST_BROADCAST_P','HOST_BROADCAST_Q'):
        require(sum(t.startswith('-D'+name+'=') for t in actual)==1 and not any(t=='-U'+name for t in actual),'conflicting compiler parameter')


def verify(root,approved_manifest_sha):
    root=Path(root).resolve()
    require(valid_hash(approved_manifest_sha) and sha(root/'approved-manifest.json')==approved_manifest_sha,'externally approved manifest SHA')
    require(sha(root/'source-plan.json')==PLAN_SHA,'approved plan bytes')
    manifest=json.loads((root/'approved-manifest.json').read_text());plan=json.loads((root/'source-plan.json').read_text())
    report=json.loads((root/'report.json').read_text());aw,field=config_of(report['profile'])
    require(report['manifest_sha256']==approved_manifest_sha,'report manifest pin')
    result,footer=expected(aw,field);pins,order=approved_sources(plan)
    steps=report_contract(report,manifest,pins,order,result);flags=commands(report,steps,order)
    artifacts=report['artifacts'];wanted={'approved-manifest.json','source-plan.json','sources.tar.gz','generated-sources.tar.gz','V'+TOP}|{name+'.log' for name in steps}
    require(set(artifacts)==wanted,'exact artifact role coverage')
    artifact_files(root,artifacts)
    for name,step in steps.items():require(step['log']==name+'.log' and step['sha256']==artifacts[step['log']],'step log hash binding')
    source=archive_members(root/'sources.tar.gz',pins)
    require(source[PLAN]==(root/'source-plan.json').read_bytes(),'source plan archive binding')
    child=source['rtl/kernel/'+CHILD+'.sv'].decode().splitlines()
    require('$fatal(1,"noncanonical NTT27 data write");' in child[394],'pinned assertion location')
    require(report['executable_sha256']==artifacts['V'+TOP]==sha(root/('V'+TOP)),'executed binary hash')
    for name in ('verilator','g++'):
        require((root/(name+'-version.log')).read_text()==report[name+'_version'],'version log binding')
    probe=json.loads((root/'probe.log').read_text())
    require(probe==dict(context_threads=1,model_threads=1,aw=aw,p=report['profile']['p'],q=report['profile']['q']) and
            all(type(x) is int for x in probe.values()),'compiled SV/C++ parameter and thread probe')
    normal=(root/'normal.log').read_text()
    require(normal in (footer,footer+'\n'),'normal footer differs from independent complete schedule')
    generated=report['generated_source_sha256']
    require(generated and all(Path(n).name==n and Path(n).suffix in ('.cpp','.h','.mk','.dat') for n in generated),'generated member contract')
    compiled=archive_members(root/'generated-sources.tar.gz',generated)
    generated_contract(compiled,(root/'build.log').read_text(),flags)
    for case in case_matrix(aw):
        name='reject-'+'-'.join(map(str,case))
        require(rejection(steps[name]['returncode'],(root/(name+'.log')).read_text(),case),'exact instance/bank/line assertion: '+name)
    return dict(status='verified',scope='One standalone paired host-memory AW/field profile only',profile=report['profile'],
        report_sha256=sha(root/'report.json'),manifest_sha256=approved_manifest_sha,runner_sha256=RUNNER_SHA,
        verifier_sha256=sha(__file__),oracle_sha256=ORACLE_SHA,normal_counts=result['counts'],
        expected_schedule_trace_sha256=result['trace_sha256'],expected_final_memory_sha256=result['final_memory_sha256'],
        oracle_hashes_are_expected_not_observed=True,assertion_cases=len(case_matrix(aw)),
        artifacts=len(artifacts),source_members=len(source),generated_members=len(compiled),
        limitation='No saved binary executed. Host-memory only; no completed NTT/full-core arithmetic, board, physical fit/clock or PRP claim. Tool hashes are recorded provenance, not independently rehashed remote binaries; prepared-tar hash is manifest provenance, while archived source bytes are verified individually.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',type=Path)
    parser.add_argument('--manifest-sha',required=True);args=parser.parse_args()
    print(json.dumps(verify(args.root,args.manifest_sha),indent=2))
