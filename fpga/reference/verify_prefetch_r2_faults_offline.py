"""Read-only independent verifier of one directed AW16 R2-domain fault.

No simulator, simulation runner, or vector-generator imports. The positive
oracle is the closed-form ordinary-integer square of a single radix impulse.
This is evidence for one fault only, not a qualification matrix or fitted design.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import tarfile

SOURCE=Path('/home/jtl/gfn-fpga-lab/agent-work/core27-prefetch-r2/snapshot-v1/fpga')
PARENT=SOURCE.parent.parent
CONTROL=PARENT/'aw16-v1'
TOP='genefer_square_core27_stream_prefetch_r2'
ROM='rtl/kernel/genefer_root_profile27_r2_rom.sv'
ROM_SHA='cb851bec51f518a71d216d4a993ffa3aa937b8230474c38898b061e7ad42dea6'
MANIFEST_SHA='6404854a21554820b6d365fa6e653352cd5dbe50edc2a913ed99bb1458028c33'
CONTROL_SHA='c871241aeca6b8c0e592aa757a785887d495859ddc5381c5e7e0ec055e6d5487'
CONTROL_EXE_SHA='59cafad4e96704fd62f256aafa2c3d14e2d456e72a7b09973cbf96c81772989c'
HARNESS_SHA='eb24496e0ac262fb84f234b415e615440047075ef5106416c7db1e74142482de'
NORMAL_RUNNER_SHA='41a328dd0ac581c956c020d74478a5668e0032271c0656057c8de2d84907f50d'
MUTATIONS={
    'seed-domain':('factor=key==0 ? R2 : IN;','factor=key==0 ? R : IN;'),
    'step-domain':("if(offset==4*LANES)profile_word=cmul(cpow(alpha,32'(4*LANES)),R);",
        "if(offset==4*LANES)profile_word=cmul(cpow(alpha,32'(4*LANES)),key==0 ? R2 : R);")}
FIELDS=('cycles','conversion','roots','ntt','crt','carry','passes','base','profile_before',
        'profile_loads','profile_hits','profile_words','seed_setup','readback')
STEPS=('verilator-version','g++-version','control-probe','fresh-control','build-mutant','mutant-probe','targeted-mutant')
GiB=1<<30
MiB=1<<20


def require(value,message):
    if not value:raise ValueError(message)


def digest(data):return hashlib.sha256(data).hexdigest()


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def archive_members(path,expected):
    result={}
    with tarfile.open(path) as tar:
        entries=tar.getmembers()
        require(len(entries)==len(expected) and set(tar.getnames())==set(expected),'archive membership')
        for entry in entries:
            name=entry.name
            require(entry.isfile() and not Path(name).is_absolute() and '..' not in Path(name).parts,'unsafe archive member')
            data=tar.extractfile(entry).read()
            require(digest(data)==expected[name],'archive member hash: '+name)
            result[name]=data
    return result


def artifact_files(root,pins):
    for name,value in pins.items():
        path=root/name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and
                path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root),'artifact path')
        require(sha(path)==value,'artifact hash: '+name)


def directed_oracle(name,payload):
    require(name in MUTATIONS,'unsupported mutation')
    n=65536;base=10**9;index,digit=(0,1636) if name=='seed-domain' else (256,1)
    label='fusion-'+name+'-impulse'
    lines=payload.decode().splitlines()
    require(len(lines)==5 and lines[0]==str(n) and lines[1]==f'LOAD {label} {base}' and
            lines[3]==f'RUN {label} 0','directed command contract')
    words=list(map(int,lines[2].split()));expected=list(map(int,lines[4].split()))
    require(len(words)==len(expected)==n,'full input/output vector lengths')
    require([(i,x) for i,x in enumerate(words) if x]!=[],'missing impulse')
    require([(i,x) for i,x in enumerate(words) if x]==[(index,digit)],'input impulse')
    require([(i,x) for i,x in enumerate(expected) if x]==[(2*index,digit*digit)],'ordinary integer square')
    # (digit*base**index)**2 = digit**2*base**(2*index), with no
    # carry and no wrap modulo base**N+1. This oracle does not use RNS.
    require(0<digit*digit<base and 2*index<n,'ordinary square/no-wrap proof')
    canonical=(f'{n}\nLOAD {label} {base}\n'+' '.join(map(str,words))+
               f'\nRUN {label} 0\n'+' '.join(map(str,expected))+'\n').encode()
    require(payload==canonical,'noncanonical directed vector bytes')
    fields=((104857601,3),(69206017,5),(67239937,10));modulus=math.prod(p for p,_ in fields)
    residues=[];roots=[]
    for p,g in fields:
        r=pow(2,32,p);r2=r*r%p;psi=pow(g,(p-1)//(2*n),p)
        ratio=pow(r,-1,p) if name=='seed-domain' else r
        residues.append((digit*ratio)**2%p)
        correct=pow(psi,index,p)*r2%p
        changed=correct*ratio%p
        require(changed!=correct,'ineffective root mutation')
        roots.append(dict(p=p,index=index,correct=correct,mutant=changed))
    # Independently reconstruct the unique centered coefficient by CRT.
    wrong=sum(a*(modulus//p)*pow(modulus//p,-1,p) for a,(p,_) in zip(residues,fields))%modulus
    if wrong>modulus//2:wrong-=modulus
    require(0<wrong<1<<66 and 2*wrong<modulus and wrong<2*n*(base-1)**2,'coefficient/carry/CRT bounds')
    require(wrong%base!=digit*digit,'missing directed wrong-word witness')
    info=dict(n=n,base=base,bit=0,label=label,input_index=index,input_digit=digit,
        coefficient_index=2*index,wrong_centered_coefficient=wrong,wrong_first_digit=wrong%base,
        crt_modulus=modulus,sha256=digest(payload))
    return info,roots


def parse_metric(line):
    match=re.fullmatch(r'^(\S+) '+' '.join(key+r'=(\d+)' for key in FIELDS)+'$',line)
    require(match is not None,'metric syntax')
    return dict(zip(FIELDS,map(int,match.groups()[1:])),case=match[1],aw=16,n=65536)


def positive_log(text,info,archived):
    lines=text.splitlines()
    require(len(lines)==2 and lines[1]=='PASS n=65536 squares=1 readbacks=1 aborts=0','positive complete full readback')
    row=parse_metric(lines[0]);wanted=dict(archived,case=info['label'],base=info['base'])
    require(row==wanted,'positive control counters differ')
    require(tuple(row[k] for k in ('conversion','roots','ntt','crt','carry','passes','seed_setup'))==
            (4102,8743,20558,4158,4147,2,815),'independent phase expectation')
    require(row['cycles']==41708 and row['profile_before']==0 and row['readback']==1 and
            (row['profile_loads'],row['profile_hits'],row['profile_words'])==(1,0,8738),'cold profile/full-readback identity')
    return lines[0],row


def semantic_rejection(code,text,info,metric):
    if type(code) is not int or code!=1:return False
    expected=f"square mismatch {info['label']} index={info['coefficient_index']} got_low={info['wrong_first_digit']} expected={info['input_digit']**2}"
    return text.splitlines()==[metric,expected]


def exact_mutation(original,changed,name):
    require(name in MUTATIONS and digest(original)==ROM_SHA,'frozen ROM identity')
    old,new=MUTATIONS[name];text=original.decode()
    require(text.count(old)==1 and changed==text.replace(old,new).encode(),'not exact single-ROM mutation')


def report_contract(report,control):
    require(report.get('status')=='passed_targeted_semantic_rejection' and 'error' not in report,'incomplete/resource-failed receipt')
    require(report['mutation'] in MUTATIONS and report['scope']=='One AW16 phase0 fusion mutation, directed cold impulse square only','fault scope')
    require(report['control_root']==str(CONTROL) and report['control_report_sha256']==CONTROL_SHA and
            report['manifest_sha256']==MANIFEST_SHA and report['harness_sha256']==HARNESS_SHA,'provenance pins')
    require(report['sources']==control['sources'] and len(report['sources'])==37,'source closure')
    require(report['sources'][ROM]==ROM_SHA and report['sources']['reference/core27_prefetch_r2_regression.py']==NORMAL_RUNNER_SHA,'source identities')
    require(report['tool_executable_sha256']==control['tool_executable_sha256'],'toolchain identity')
    for key in ('tool_version','compiler_version'):require(report[key]==control[key],'tool version')
    scratch=Path(report['scratch'])
    require(scratch.parent==Path('/dev/shm') and scratch.name.startswith('gfn16-prefetch-r2-fault-') and
            '..' not in scratch.parts and report['compiler_temporary_directory']==str(scratch/'tmp'),'private scratch paths')
    limits=report['limits'];quota,period=map(int,limits['cpu_max'])
    require(0<limits['memory_max_bytes']<=6*GiB and 0<quota<=2*period and period>0,'aggregate resource limits')
    require(limits['affinity']==[0,2] and len(limits['physical_cores'])==2 and
            len({tuple(x) for x in limits['physical_cores']})==2,'physical-core allocation')
    for key,value in dict(durable_reservation_bytes=32*MiB,durable_free_floor_bytes=10*GiB,
        scratch_reservation_bytes=512*MiB,scratch_free_floor_bytes=2*GiB,host_memory_floor_bytes=4*GiB,
        command_timeout_seconds=1800).items():require(report[key]==value,'resource metadata: '+key)
    require([s['name'] for s in report['steps']]==list(STEPS),'step order/coverage')
    for step in report['steps']:
        require(step['error'] is None and type(step['returncode']) is int and
            step['returncode']==(1 if step['name']=='targeted-mutant' else 0),'step failure/termination')
        require(type(step['seconds']) in (int,float) and math.isfinite(step['seconds']) and 0<=step['seconds']<1802,'step duration')
    return {s['name']:s for s in report['steps']}


def command_contract(report,control,steps):
    argv=steps['fresh-control']['command'];require(len(argv)==3,'control argv')
    vector=Path(argv[1]);out=vector.parent
    require(out.parent==PARENT and '..' not in out.parts and out!=CONTROL and
            vector.name=='directed-cold-aw16.txt','durable task output path')
    exe='V'+TOP+'-'+report['mutation'];old=str(CONTROL/('V'+TOP));new=str(out/exe)
    commands={'verilator-version':['verilator','--version'],'g++-version':['g++','--version'],
        'control-probe':[old,'--runtime-probe'],'fresh-control':[old,str(vector),'profile'],
        'mutant-probe':[new,'--runtime-probe'],'targeted-mutant':[new,str(vector),'profile']}
    original=[s['command'] for s in control['steps'] if s['name']=='build']
    require(len(original)==1,'unique original compiler command')
    build=list(original[0]);require(build.count('--Mdir')==1 and build.count(str(SOURCE/ROM))==1,'original source/flag identity')
    build[build.index('--Mdir')+1]=str(Path(report['scratch'])/'build')
    build[build.index(str(SOURCE/ROM))]=str(out/'mutant-root-profile27-r2.sv')
    require(build[:13]==['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',TOP,'-GAW=16','-GNTT_LANES=64','--Mdir'],'compiler flags')
    require(sum(x.endswith('.sv') for x in build)==16,'compiled RTL count')
    commands['build-mutant']=build
    for name,command in commands.items():require(steps[name]['command']==command,'command identity/delta: '+name)
    return exe


def verify(root,control_root):
    root=root.resolve();control_root=control_root.resolve()
    require(sha(control_root/'report.json')==CONTROL_SHA,'original control report identity')
    control=json.loads((control_root/'report.json').read_text());report=json.loads((root/'report.json').read_text())
    require(control['status']=='passed' and (control['aw'],control['n'],control['ntt_lanes'],control['model_threads'])==(16,65536,64,1),'qualified control')
    artifact_files(control_root,control['artifacts']);archive_members(control_root/'sources.tar.gz',control['sources'])
    steps=report_contract(report,control);exe=command_contract(report,control,steps)
    wanted={'control-report.json','approved-manifest.json','directed-cold-aw16.txt','mutant-root-profile27-r2.sv',
        'sources.tar.gz','generated-sources.tar.gz',exe}|{name+'.log' for name in STEPS}
    artifacts=report['artifacts'];require(set(artifacts)==wanted,'durable evidence completeness')
    artifact_files(root,artifacts)
    require(sha(root/'control-report.json')==CONTROL_SHA and sha(root/'approved-manifest.json')==MANIFEST_SHA,'copied provenance pins')
    manifest=json.loads((root/'approved-manifest.json').read_text())
    require(manifest['sources']==control['sources'],'pre-import manifest closure')
    for name,step in steps.items():require(step['log']==name+'.log' and step['sha256']==artifacts[step['log']],'step log provenance')
    source_pins=dict(control['sources']);source_pins.update({'tools/run_prefetch_r2_faults.py':HARNESS_SHA,
        'mutant-root-profile27-r2.sv':artifacts['mutant-root-profile27-r2.sv']})
    members=archive_members(root/'sources.tar.gz',source_pins)
    changed=(root/'mutant-root-profile27-r2.sv').read_bytes()
    require(changed==members['mutant-root-profile27-r2.sv'],'compiled/archived mutant equality')
    exact_mutation(members[ROM],changed,report['mutation'])
    old,new=MUTATIONS[report['mutation']]
    require(report['mutation_delta']==dict(ancestor_sha256=ROM_SHA,mutant_sha256=digest(changed),old=old,new=new),'delta metadata')
    info,roots=directed_oracle(report['mutation'],(root/'directed-cold-aw16.txt').read_bytes())
    require(report['case']==info and report['root_witnesses']==roots,'independent oracle metadata')
    metric,row=positive_log((root/'fresh-control.log').read_text(),info,control['metrics'][0])
    require(report['fresh_control_metric']==row,'fresh positive counters')
    require(report['control_executable_sha256']==control['executable_sha256']==CONTROL_EXE_SHA==
            sha(control_root/('V'+TOP)),'control executable identity')
    require(report['mutant_executable_sha256']==sha(root/exe)!=CONTROL_EXE_SHA,'mutant executable identity')
    for kind in ('control','mutant'):
        probe=json.loads((root/(kind+'-probe.log')).read_text())
        require(probe=={'context_threads':1,'model_threads':1,'expected_threads':1} and
                all(type(v) is int for v in probe.values()),'thread probe')
    for name,key in (('verilator-version','tool_version'),('g++-version','compiler_version')):
        require((root/(name+'.log')).read_text().strip()==control[key],'tool version log')
    generated=report['generated_source_sha256']
    require(generated and all(Path(n).name==n and Path(n).suffix in ('.cpp','.h','.mk','.dat') for n in generated),'generated member paths')
    compiled=archive_members(root/'generated-sources.tar.gz',generated)
    top='V'+TOP
    require(all(top+suffix in compiled for suffix in ('.cpp','.h','.mk')),'generated top evidence')
    require(f'unsigned {top}::threads() const {{ return 1; }}' in compiled[top+'.cpp'].decode(),'generated thread identity')
    require(semantic_rejection(steps['targeted-mutant']['returncode'],(root/'targeted-mutant.log').read_text(),info,metric),'exact semantic mismatch required')
    return dict(status='verified',scope='One directed cold AW16 '+report['mutation']+' mutation only',
        report_sha256=sha(root/'report.json'),control_report_sha256=CONTROL_SHA,harness_sha256=HARNESS_SHA,
        verifier_sha256=sha(__file__),durable_artifacts=len(artifacts),source_archive_members=len(members),
        generated_archive_members=len(compiled),positive_operations=1,positive_readbacks=1,readback_words=65536,
        wrong_centered_coefficient=info['wrong_centered_coefficient'],observed_wrong_word=info['wrong_first_digit'],
        expected_word=info['input_digit']**2,mutant_returncode=1,
        limitation='One targeted fault only; no complete mutation/profile matrix, board, fit/clock, or full PRP qualification. Offline verification executes no RTL.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',type=Path)
    parser.add_argument('--control',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(verify(args.root,args.control),indent=2))
