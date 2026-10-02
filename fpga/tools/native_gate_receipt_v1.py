"""Read-only automatic dependency gates for source-pinned native outcomes.

No role imports, GMP, HDL execution or full-N arithmetic on the coordinator.
Typed validators are trusted only as receipts from the pinned completed worker;
their exact source/config/assets and raw outputs remain bound and replayable.
This gate admits dependency progress, never independent promotion.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile


def need(ok,why):
    if not ok:raise ValueError(why)


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def pin(value):
    need(type(value) is str and re.fullmatch('[0-9a-f]{64}',value),'exact SHA256')
    return value
def relative(value):
    need(type(value) is str and value not in ('','.') and str(PurePosixPath(value))==value
         and not PurePosixPath(value).is_absolute() and '..' not in PurePosixPath(value).parts,'safe artifact/source path')
    return value
def regular(path):
    need(path.is_absolute() and path.resolve()==path and path.is_file() and not path.is_symlink(),'canonical regular evidence file')


def make_contract(candidate_id,manifest_path):
    path=Path(manifest_path);regular(path);raw=path.read_bytes();manifest=json.loads(raw)
    manifest_pin=hashlib.sha256(raw).hexdigest()
    need(type(candidate_id) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,127}',candidate_id),'candidate identity')
    need(manifest['schema']=='native-source-gate-v1' and manifest['phase']=='run','native run manifest, not lint-only observation')
    sources=manifest['sources'];need(type(sources) is dict and sources,'closed source identity')
    for name,value in sources.items():relative(name);pin(value)
    build=manifest['build']
    need(type(build['sv_sources']) is list and build['sv_sources'] and all(name in sources for name in build['sv_sources'])
         and build['cpp_source'] in sources,'ordered compiled source closure')
    steps=manifest['steps'];need(type(steps) is list and 1<=len(steps)<=64,'finite expected outcomes')
    names=[]
    for step in steps:
        name=step['name'];need(type(name) is str and re.fullmatch('[a-zA-Z0-9_-]+',name),'safe step identity')
        need(name not in ('verilator-version','compiler-version','lint','build','probe'),'no reserved step name')
        names.append(name)
        need(type(step.get('expected_returncode',0)) is int,'typed expected exit code')
        need(type(step['argv']) is list and step['argv'] and step['argv'][0]=='{exe}'
             and all(type(arg) is str for arg in step['argv']),'exact executable argv contract')
        need('validator' in step or all(type(step.get(k)) is str for k in ('expected_stdout','expected_stderr')),'typed or exact output contract')
        if 'validator' in step:
            spec=step['validator'];need(type(spec) is dict and set(spec)=={'source','function','config','assets'},'typed validator descriptor')
            for name in [spec['source'],*spec['assets'].values()]:need(name in sources,'validator and assets in source closure')
    need(len(names)==len(set(names)),'unique expected step names')
    role_sources=manifest.get('budget_source_members',sources)
    need(type(role_sources) is dict and role_sources and all(sources.get(k)==v for k,v in role_sources.items()),'original role source subset')
    candidate=dict(sources=role_sources,build=manifest['build'],probe=manifest['probe'],steps=steps)
    need(sha(path)==manifest_pin,'manifest stable during contract capture')
    contract=dict(schema='native-gate-contract-v1',candidate_id=candidate_id,manifest_sha256=manifest_pin,
        candidate_source_sha256=digest(candidate),manifest=manifest,promotion_allowed=False)
    contract['contract_sha256']=digest(contract)
    return contract


def validate_result(contract,report_path,*,id):
    """Produce an all-outcomes receipt, including intentionally nonzero mutants.

    Caller anchors this contract to the selected immutable package/global ticket.
    A genuine completed worker report is required; rc0 alone never passes.
    """
    expected=dict(contract);claimed=expected.pop('contract_sha256')
    need(claimed==digest(expected),'contract identity')
    need(contract['schema']=='native-gate-contract-v1' and contract['promotion_allowed'] is False,'nonpromotion gate contract')
    need(type(id) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,127}',id),'logical gate id')
    path=Path(report_path);regular(path);root=path.parent;raw=path.read_bytes();report=json.loads(raw);manifest=contract['manifest']
    report_pin=hashlib.sha256(raw).hexdigest()
    need(report['status']=='completed_native_commands_unreviewed','all native commands must have completed expected contracts')
    need(report['manifest_sha256']==contract['manifest_sha256'] and report['sources']==manifest['sources'],'report source/manifest identity')
    need(report['host']==manifest['host'] and report['source_root']==manifest['source_root'],'report host/source placement')
    artifacts=report['artifacts'];need(type(artifacts) is dict and artifacts,'complete artifact inventory')
    for name,value in artifacts.items():
        target=root/relative(name);regular(target);need(sha(target)==pin(value),'raw artifact identity: '+name)
    approved=root/'approved-manifest.json';need('approved-manifest.json' in artifacts and sha(approved)==contract['manifest_sha256'],'approved manifest artifact')
    need(json.loads(approved.read_text())==manifest,'exact source/build/probe/steps contract')
    need('sources.tar.gz' in artifacts,'preserved closed source archive')
    archived={}
    with tarfile.open(root/'sources.tar.gz','r:gz') as archive:
        for member in archive:
            name=relative(member.name)
            need(member.isfile() and not member.issparse() and name not in archived and name in manifest['sources'],'exact regular source archive members')
            with archive.extractfile(member) as stream:archived[name]=hashlib.file_digest(stream,'sha256').hexdigest()
    need(archived==manifest['sources'],'archived source closure')
    need(report['probe']==manifest['probe']['expected_json'] and all(type(v) is int for v in report['probe'].values()),'actual typed model/context probe')
    observed=report['steps'];steps=manifest['steps'];prefix=['verilator-version','compiler-version','lint','build','probe']
    need([row['name'] for row in observed]==prefix+[row['name'] for row in steps],'exact completed command sequence')
    for row in observed[:5]:need(type(row['returncode']) is int and row['returncode']==0 and row.get('error') is None,'successful infrastructure command')
    probe=observed[4]
    need(type(probe['command']) is list and len(probe['command'])>=4,'recorded probe command')
    command_prefix=probe['command'][:3];exe=probe['command'][3]
    need(Path(exe).name=='V'+manifest['build']['top'],'expected built top executable')
    outcomes=[]
    for step,row in zip(steps,observed[5:]):
        code=step.get('expected_returncode',0)
        need(type(row['returncode']) is int and row['returncode']==code and row.get('error') is None,'expected typed exit, not raw zero')
        argv=[arg.replace('{exe}',exe).replace('{root}',manifest['source_root']) for arg in step['argv']]
        need(row['command']==command_prefix+argv,'exact executed case/selector argv')
        logs=[]
        for field,hash_field in [('log','sha256'),('stderr_log','stderr_sha256')]:
            name=relative(row[field]);need(artifacts.get(name)==row[hash_field],'step log belongs to replayed artifacts')
            need((root/name).stat().st_size<=256*(1<<20),'bounded native outcome log')
            logs.append((root/name).read_text())
        for field,text in zip(('expected_stdout','expected_stderr'),logs):
            if field in step:need(text==step[field],'exact '+field+' contract')
        validation=None;validator_sha=None
        if 'validator' in step:
            need(type(report.get('validations')) is dict and type(report['validations'].get(step['name'])) is dict,'completed source-pinned typed validation receipt')
            validation=report['validations'][step['name']];canonical(validation)
            spec=step['validator'];validator_sha=digest(dict(descriptor=spec,source_pins={name:manifest['sources'][name] for name in [spec['source'],*spec['assets'].values()]}))
        outcomes.append(dict(name=step['name'],expected_returncode=code,actual_returncode=row['returncode'],
            stdout_sha256=row['sha256'],stderr_sha256=row['stderr_sha256'],typed_validator_sha256=validator_sha,validation=validation))
    need(sha(path)==report_pin and all(sha(root/name)==value for name,value in artifacts.items()),'report/artifacts stable through outcome replay')
    return dict(schema='gfn16-native-gate-receipt-v1',status='PASS_expected_contracts',id=id,candidate_id=contract['candidate_id'],
        manifest_sha256=contract['manifest_sha256'],candidate_source_sha256=contract['candidate_source_sha256'],contract_sha256=claimed,
        report_sha256=report_pin,artifact_inventory_sha256=digest(artifacts),steps=outcomes,promotion_allowed=False,
        validation_scope='Dependency progress only: trusted pinned worker typed receipts plus full raw artifact/source archive replay; no role imports or coordinator numerical rerun')
