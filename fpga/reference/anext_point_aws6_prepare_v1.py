"""One source-identical six-worker placement alternative; no execution authority."""
import json
import shutil
import types
from pathlib import Path
from fpga.reference import anext_point_fit_prepare_v1 as parent
from fpga.cloud import plain_fit_v1 as plain

ROOT=parent.ROOT
BASE='artifacts/anext-point-9668ps-f16-plain-v1'
PIN='40fbad182ecb6f05e847cad459a51d388a057732f8545cf298200ab5cc3b5bff'
INV='37012c7a376782e7804736c0887553c904cda7427b687c7f345b71d6cbe0119c'

def verify_project(project):
    # Reuse the frozen verifier with precisely the same two worker substitutions
    # as shared plain_fit_v1.runner(workers=6). No native command is invoked.
    path=ROOT/'cloud/aws_fit_v6.py'
    if parent.point.sha(path)!=plain.PARENT_SHA:raise ValueError('frozen fit verifier pin')
    text=path.read_text()
    for old,new in (("manifest['compile_processors']==4","manifest['compile_processors']==6"),
                    ("assignment('NUM_PARALLEL_PROCESSORS')==['4']","assignment('NUM_PARALLEL_PROCESSORS')==['6']")):
        if text.count(old)!=1:raise ValueError('plain worker verifier anchors')
        text=text.replace(old,new)
    module=types.ModuleType('_source_only_six_worker_verifier');module.__file__=str(path)
    exec(compile(text,str(path)+'[shared-six-worker-substitutions]','exec'),module.__dict__)
    return module.verify_project(project)

def prepare(output):
    output=Path(output).resolve();base=ROOT/BASE;p=output/'project'
    if output.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('fresh/no PAUSE')
    if parent.point.sha(base/'project/manifest.json')!=PIN or parent.point.sha(base/'inventory.json')!=INV:
        raise ValueError('frozen fourworker project')
    m=json.loads((base/'project/manifest.json').read_text());spec=json.loads((base/'inventory.json').read_text())
    parent.source_inventory(base/'project',spec)
    shutil.copytree(base/'project',p)
    qsf=(p/'probe.qsf').read_text()
    old='set_global_assignment -name NUM_PARALLEL_PROCESSORS 4'
    if qsf.count(old)!=1:raise ValueError('single worker control')
    (p/'probe.qsf').write_text(qsf.replace(old,'set_global_assignment -name NUM_PARALLEL_PROCESSORS 6'))
    m['compile_processors']=6;m['placement_parent_manifest_sha256']=PIN
    m['control_sha256']['probe.qsf']=parent.point.sha(p/'probe.qsf')
    parent.save(p/'manifest.json',m)
    spec['settings']={**m['control_sha256'],'manifest.json':parent.point.sha(p/'manifest.json')}
    structural=parent.source_inventory(p,spec)
    if structural['findings']:raise ValueError('source inventory findings')
    context=verify_project(p)
    if (p/'run.tcl').read_text()!=plain.FULL_TCL:raise ValueError('plain full flow')
    parent.save(output/'inventory.json',spec);parent.save(output/'project-context.json',context)
    result=dict(status='PASS_source_identical_six_worker_alternative_native_dependency_pending',
        manifest_sha256=parent.point.sha(p/'manifest.json'),inventory_sha256=parent.point.sha(output/'inventory.json'),
        context_sha256=parent.point.sha(output/'project-context.json'),required_native_gate=parent.REQUIRED,
        rtl_changed=False,period_changed=False,seed_changed=False,compile_processors=6,
        source_structural=structural,established_plain_verifier=True,fit_launched=False,promotion_allowed=False)
    parent.save(output/'source-preparation.json',result);return result

if __name__=='__main__':
    import argparse
    q=argparse.ArgumentParser();q.add_argument('--output',type=Path,required=True);a=q.parse_args();print(json.dumps(prepare(a.output),indent=2))
