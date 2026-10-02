"""AWS six-worker control successor of exact P8 warm sizing; no RTL change."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import types
from .stream27_shared_field_v1 import ROOT
from fpga.cloud.plain_fit_v2 import PARENT_SHA

PARENT='artifacts/stream27-s4-aw16-p8-warm-sizing-v1/project'
PIN='b4e2e4cd0e99ec57b2d0d915a15ea4a0f341d14ccafc49da9b1e89af4bac2578'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(destination):
    destination=Path(destination).resolve();parent=ROOT/PARENT
    if destination.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('S4_P8_AWS_CONTROL_FRESH_PAUSE')
    if sha(parent/'manifest.json')!=PIN:raise ValueError('S4_P8_AWS_PARENT_DRIFT')
    m=json.loads((parent/'manifest.json').read_text());project=destination/'project';(project/'rtl').mkdir(parents=True)
    for name,pin in m['source_sha256'].items():
        if sha(parent/'rtl'/name)!=pin:raise ValueError('S4_P8_AWS_RTL_DRIFT:'+name)
        shutil.copyfile(parent/'rtl'/name,project/'rtl'/name)
    for name,pin in m['control_sha256'].items():
        if sha(parent/name)!=pin:raise ValueError('S4_P8_AWS_CONTROL_DRIFT:'+name)
        value=(parent/name).read_text()
        if name=='probe.qsf':
            old='set_global_assignment -name NUM_PARALLEL_PROCESSORS 4'
            if value.count(old)!=1:raise ValueError('S4_P8_AWS_WORKER_ANCHOR')
            value=value.replace(old,'set_global_assignment -name NUM_PARALLEL_PROCESSORS 6')
        (project/name).write_text(value)
    m['compile_processors']=6;m['control_sha256']={name:sha(project/name) for name in m['control_sha256']}
    path='reference/stream27_shared_warm_physical_v5.py';m['preparation_source_sha256'][path]=sha(ROOT/path)
    m['sizing_control_adapter']=dict(parent_manifest_sha256=PIN,delta='NUM_PARALLEL_PROCESSORS4 to6 and compile_processors metadata only; same23RTL/part/P8/AW16/f0/CONTEXTS1/10ns/seed1/plainFULL_TCL/snapshotsON.')
    (project/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    raw=(ROOT/'cloud/aws_fit_v6.py').read_text()
    if hashlib.sha256(raw.encode()).hexdigest()!=PARENT_SHA:raise ValueError('S4_P8_AWS_VERIFY_PARENT_DRIFT')
    for old,new in (("manifest['compile_processors']==4","manifest['compile_processors']==6"),
                    ("assignment('NUM_PARALLEL_PROCESSORS')==['4']","assignment('NUM_PARALLEL_PROCESSORS')==['6']")):
        if raw.count(old)!=1:raise ValueError('S4_P8_AWS_VERIFY_WORKER_ANCHOR')
        raw=raw.replace(old,new)
    policy=types.ModuleType('source_only_approved_plain_sixworkers');policy.__file__=str(ROOT/'cloud/aws_fit_v6.py')
    exec(compile(raw,'aws_fit_v6.py[approved plain sixworker source verifier]','exec'),policy.__dict__)
    context=policy.verify_project(project) # Exact approved plain runner worker-verifier delta; no launch/limits RPC.
    if context['source_sha256']!=m['source_sha256']:raise ValueError('S4_P8_AWS_FINAL_RTL_DRIFT')
    result=dict(status='source_verified_sixworker_component_sizing_not_dispatched',project=context,
        project_manifest_sha256=sha(project/'manifest.json'),source_files=len(m['source_sha256']),parent_manifest_sha256=PIN,
        rtl_unchanged=True,clock_period_ns=10,seed=1,compile_processors=6,sizing_exemption=m['sizing_exemption'],promotion_allowed=False)
    (destination/'preparation.json').write_text(json.dumps(result,indent=2)+'\n')
    with tarfile.open(destination/'source.tar.gz','x:gz') as archive:
        for path in sorted(project.rglob('*')):
            if path.is_file():archive.add(path,arcname='project/'+str(path.relative_to(project)),recursive=False)
        archive.add(destination/'preparation.json',arcname='preparation.json',recursive=False)
    result['archive_sha256']=sha(destination/'source.tar.gz');return result


if __name__=='__main__':
    import sys
    if len(sys.argv)!=2:raise ValueError('S4_P8_AWS_CONTROL_USAGE')
    r=prepare(sys.argv[1]);print(json.dumps({k:r[k] for k in ('status','project_manifest_sha256','archive_sha256','source_files','rtl_unchanged')},indent=2))
