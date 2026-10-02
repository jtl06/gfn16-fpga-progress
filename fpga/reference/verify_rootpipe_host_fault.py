"""Independent, read-only verifier for one AW7 host-quarter mutation receipt.

No simulator or simulation-runner imports. The positive control is checked with
the separate ordinary-integer offline verifier. This is one fault's evidence,
not a complete integration mutation, fit, clock, board or PRP qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile

if __package__:
    from . import verify_square_core27_rootpipe_offline as normal
else:
    import verify_square_core27_rootpipe_offline as normal

CONTROL_SHA='cc0a83f3b698923b8f9a1e2c966cee1fe73d8405f67930530248e422dcc36525'
RUNNER_SHA='c1f64e9d094a504adcdb4661083b36d105cf9cfa3e57f7e0ec6d31de275aaee2'
NORMAL_VERIFIER_SHA='785100ed9ae507e04c086a893fd401db189a847cdbc9e428e6ee6f9ed5de9920'
SOURCE=Path('/home/jtl/gfn-fpga-lab/agent-work/square-core27-rootpipe/profiles/small-v1/fpga')
CONTROL=SOURCE/'artifacts/aw7-v1'
OUTPUT=Path('/home/jtl/gfn-fpga-lab/agent-work/square-core27-rootpipe/faults/host-quarter-v1')
TOP='genefer_square_core27_stream_rootpipe'
HOST='rtl/kernel/genefer_ntt_banked27_host_rootpipe_engine.sv'
EXE='V'+TOP+'-host-quarter-mutant'
STEPS=('verilator-version','compiler-version','control-probe','control','build-mutant','mutant-probe','reject-host-quarter')
GiB=1<<30
MiB=1<<20

def require(value,message):
    if not value:raise ValueError(message)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def semantic_rejection(code,output):
    fatal=re.compile(r'^\[\d+\] %Fatal: (?:[^\n:]+/)?genefer_square_core27_stream_rootpipe\.sv:288: '
        r'Assertion failed in TOP\.genefer_square_core27_stream_rootpipe\.unnamedblk3: residue mask skew$',re.M)
    return type(code) is int and code in (1,-6,134) and len(fatal.findall(output))==1 and 'PASS n=' not in output

def exact_mutation(original,changed):
    require(original.count('read_group<=host_group;')==1,'mutation anchor not unique')
    require(changed==original.replace('read_group<=host_group;','read_group<=0;'),'mutation is not exact single assignment delta')

def archive_members(path,expected):
    data={}
    with tarfile.open(path) as tar:
        members=tar.getmembers()
        require(len(members)==len(expected) and set(tar.getnames())==set(expected),'archive membership')
        for member in members:
            name=member.name
            require(member.isfile() and not Path(name).is_absolute() and '..' not in Path(name).parts,'unsafe archive member')
            content=tar.extractfile(member).read()
            require(hashlib.sha256(content).hexdigest()==expected[name],'archive member hash: '+name)
            data[name]=content
    return data

def report_contract(report,control):
    require(report.get('status')=='passed' and 'error' not in report,'incomplete/resource-failed report')
    require(report['scope']=='AW7 host-quarter integration mutant only','scope')
    require(report['control_report_sha256']==CONTROL_SHA and report['tool_sha256']==RUNNER_SHA,'report/runner pin')
    require(report['source_sha256']==control['sources'] and len(report['source_sha256'])==29,'source closure')
    require(report['tool_executable_sha256']==control['tool_executable_sha256'],'tool provenance')
    for key in ('tool_version','compiler_version','python_version'):
        require(report[key]==control[key],'tool version: '+key)
    require(report['durable_output']==str(OUTPUT),'durable output identity')
    scratch=Path(report['scratch'])
    require(scratch.is_absolute() and scratch.parent==Path('/dev/shm') and
        scratch.name.startswith('gfn16-rootpipe-host-fault-') and '..' not in scratch.parts,'private tmpfs identity')
    require(report['compiler_temporary_directory']==str(scratch/'tmp'),'compiler temporary path')
    limits=report['limits'];quota,period=map(int,limits['cpu_max'])
    require(0<limits['memory_max_bytes']<=6*GiB and 0<quota<=2*period and period>0,'aggregate limits')
    require(limits['affinity']==[0,2] and len(limits['physical_cores'])==2 and
        len({tuple(core) for core in limits['physical_cores']})==2,'physical-core affinity')
    for key,expected in {'scratch_reservation_bytes':512*MiB,'scratch_free_floor_bytes':2*GiB,
        'durable_reservation_bytes':32*MiB,'durable_free_floor_bytes':10*GiB,'host_memory_floor_bytes':4*GiB}.items():
        require(report[key]==expected,'resource contract: '+key)
    rows=report['steps'];require([row['name'] for row in rows]==list(STEPS),'command-stage coverage/order')
    for row in rows:
        reject=row['name']=='reject-host-quarter'
        require(row['failure'] is None and row['expected_rejection'] is reject,'step failed/incomplete')
        require(type(row['returncode']) is int,'non-integer termination')
        require(row['returncode'] in (1,-6,134) if reject else row['returncode']==0,'unexpected termination')
        require(row['seconds']>=0 and row['seconds']<901,'bounded command duration')
    return {row['name']:row for row in rows}

def command_contract(report,control,steps):
    old_exe=str(CONTROL/'build-aw7'/('V'+TOP));new_exe=str(OUTPUT/EXE);vector=str(OUTPUT/'vectors-aw7.txt')
    commands={'verilator-version':['verilator','--version'],'compiler-version':['g++','--version'],
        'control-probe':[old_exe,'--runtime-probe'],'control':[old_exe,vector,'cache'],
        'mutant-probe':[new_exe,'--runtime-probe'],'reject-host-quarter':[new_exe,vector,'cache']}
    old_build=next(step['command'] for step in control['steps'] if step['name']=='build-aw7')
    require(old_build.count(str(SOURCE/HOST))==1,'host source occurrence')
    expected=list(old_build)
    require(expected.count('--Mdir')==1,'original build directory flag')
    expected[expected.index('--Mdir')+1]=str(Path(report['scratch'])/'build')
    expected[expected.index(str(SOURCE/HOST))]=str(OUTPUT/'mutant-host-quarter.sv')
    commands['build-mutant']=expected
    for name,argv in commands.items():require(steps[name]['command']==argv,'command delta/identity: '+name)
    require(sum(x.endswith('.sv') for x in expected)==15,'compiled RTL closure count')

def verify(root,control_root):
    root=root.resolve();control_root=control_root.resolve()
    require(sha(control_root/'report.json')==CONTROL_SHA,'original AW7 report pin')
    require(sha(normal.__file__)==NORMAL_VERIFIER_SHA,'independent normal verifier pin')
    positive_original=normal.verify(control_root)
    control=json.loads((control_root/'report.json').read_text())
    report=json.loads((root/'report.json').read_text())
    steps=report_contract(report,control);command_contract(report,control,steps)
    artifacts=report['artifacts']
    wanted={'vectors-aw7.txt','mutant-host-quarter.sv','sources.tar.gz','generated-sources.tar.gz',EXE}|{name+'.log' for name in STEPS}
    require(set(artifacts)==wanted,'durable artifact coverage')
    for relative,digest in artifacts.items():
        path=root/relative
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root),'artifact path')
        require(sha(path)==digest,'artifact hash: '+relative)
    for name,step in steps.items():
        require(step['log']==name+'.log' and step['sha256']==artifacts[step['log']],'step log provenance')
    expected_source=dict(control['sources'])
    expected_source['tools/run_rootpipe_host_fault.py']=RUNNER_SHA
    expected_source['mutant-host-quarter.sv']=artifacts['mutant-host-quarter.sv']
    members=archive_members(root/'sources.tar.gz',expected_source)
    original=members[HOST].decode();changed=members['mutant-host-quarter.sv'].decode()
    exact_mutation(original,changed)
    require((root/'mutant-host-quarter.sv').read_text()==changed,'compiled mutant versus archived mutant')
    require(report['mutation']=={'ancestor':Path(HOST).name,'ancestor_sha256':control['sources'][HOST],
        'mutant_sha256':artifacts['mutant-host-quarter.sv'],'old':'read_group<=host_group;',
        'new':'read_group<=0;','expected':'residue mask skew'},'mutation receipt')
    require((root/'vectors-aw7.txt').read_bytes()==(control_root/'aw7-segment0.txt').read_bytes(),'control vector bytes')
    old_exe=control_root/'build-aw7'/('V'+TOP)
    require(report['control_executable_sha256']==sha(old_exe)==control['builds'][0]['sha256'],'control executable identity')
    require(report['mutant_executable_sha256']==sha(root/EXE)!=sha(old_exe),'mutant executable identity')
    for kind in ('control','mutant'):
        probe=json.loads((root/(kind+'-probe.log')).read_text())
        require(probe=={'context_threads':1,'model_threads':1,'expected_threads':1} and
            all(type(value) is int for value in probe.values()),'executable thread probe')
    for step,key in (('verilator-version','tool_version'),('compiler-version','compiler_version')):
        require((root/(step+'.log')).read_text().strip()==control[key],'tool version log')
    rows,summary=normal.audit_vectors((root/'vectors-aw7.txt').read_text(),(root/'control.log').read_text(),7)
    require(rows==report['control_metrics']==control['metrics'],'fresh positive-control counters/oracle')
    generated=report['generated_source_sha256']
    require(generated and all(Path(name).name==name and Path(name).suffix in ('.cpp','.h','.mk','.dat') for name in generated),'generated source member contract')
    compiled=archive_members(root/'generated-sources.tar.gz',generated)
    top='V'+TOP
    require(top+'.cpp' in compiled and top+'.h' in compiled and top+'.mk' in compiled,'generated top evidence')
    require(f'unsigned {top}::threads() const {{ return 1; }}' in compiled[top+'.cpp'].decode(),'generated model thread identity')
    log=(root/'reject-host-quarter.log').read_text()
    require(semantic_rejection(steps['reject-host-quarter']['returncode'],log),'not the exact qualified semantic rejection')
    return {'status':'verified','scope':'One AW7 host-quarter mutation only',
        'report_sha256':sha(root/'report.json'),'control_report_sha256':CONTROL_SHA,'runner_sha256':RUNNER_SHA,
        'verifier_sha256':sha(__file__),'normal_verifier_sha256':NORMAL_VERIFIER_SHA,
        'durable_artifacts':len(artifacts),'source_archive_members':len(members),'generated_archive_members':len(compiled),
        'fresh_positive_control_operations':summary['operations'],'fresh_positive_control_readbacks':summary['readbacks'],
        'original_control_offline_status':positive_original['status'],'mutant_expected_assertion':'residue mask skew',
        'mutant_returncode':steps['reject-host-quarter']['returncode'],
        'limitation':'One targeted fault sensitivity check, not full integration mutation qualification, timing/fit, board execution or full PRP. Offline verification does not execute RTL.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',type=Path)
    parser.add_argument('--control',required=True,type=Path);args=parser.parse_args()
    print(json.dumps(verify(args.root,args.control),indent=2))
