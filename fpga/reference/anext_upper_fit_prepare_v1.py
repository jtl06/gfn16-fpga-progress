"""Plain matched upper-prereg whole fit alternatives, conditional on ownAW16."""
import json
from pathlib import Path
from fpga.reference import anext_upper_source_v1 as source
from fpga.reference import anext_point_aws6_prepare_v1 as six
from fpga.cloud.aws_fit_v6 import verify_project as verify_four
from fpga.tools.prefit_structural_guard_v1 import source_inventory
ROOT=source.ROOT
PARENTS={
 4:('artifacts/anext-point-9668ps-f16-plain-v1','40fbad182ecb6f05e847cad459a51d388a057732f8545cf298200ab5cc3b5bff','37012c7a376782e7804736c0887553c904cda7427b687c7f345b71d6cbe0119c'),
 6:('artifacts/anext-point-9668ps-aws6-plain-v1','3f2ba54d86b39afe482484b2afb9aee03b3f8c4b84306600d6daf616354ac84f','a59fbf5a767955070d119ec2b70e0c9aa6160e357f1c2ab98d9544a0f291359d')}
ROLE='artifacts/anext-upper-representative-aw16-role-v1'
ROLE_SHA='734b33e574f38d227bfbadff0c0beaeecc9891c078672ff69024ba76d32aeae4'
REQUIRED='anext-upper-representative-aw16-q1-v1'
def rename(v):
    if isinstance(v,dict):return {rename(k):rename(x) for k,x in v.items()}
    if isinstance(v,list):return [rename(x) for x in v]
    if isinstance(v,str):return source.renames(v).replace('genefer_a10_canonical_butterfly_v1.sv','genefer_a10_canonical_butterfly_sumlaunch_v2.sv')
    return v
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def prepare(output,workers):
    output=Path(output).resolve()
    if type(workers) is not int or workers not in PARENTS or output.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('finite fresh upperfit source')
    base,pin,inv=PARENTS[workers];old=ROOT/base/'project'
    for p,h in ((old/'manifest.json',pin),(ROOT/base/'inventory.json',inv),(ROOT/ROLE/'manifest.json',ROLE_SHA)):
        if source.point.sha(p)!=h:raise ValueError('upperfit exact ancestor/role pin')
    source.verify();m=json.loads((old/'manifest.json').read_text());spec=json.loads((ROOT/base/'inventory.json').read_text());source_inventory(old,spec)
    role=json.loads((ROOT/ROLE/'manifest.json').read_text());project=output/'project';(project/'rtl').mkdir(parents=True);sources={}
    for name in role['build']['sv_sources']:
        p=ROOT/ROLE/'source/fpga'/name
        if source.point.sha(p)!=role['sources'][name]:raise ValueError('upperfit compiled source drift')
        (project/'rtl'/Path(name).name).write_bytes(p.read_bytes());sources[Path(name).name]=role['sources'][name]
    if len(sources)!=30:raise ValueError('upperfit30SV')
    for name,h in m['control_sha256'].items():
        if source.point.sha(old/name)!=h:raise ValueError('upperfit parent control drift')
        text=(old/name).read_text();(project/name).write_text(rename(text) if name=='probe.qsf' else text)
    m.update(status='upper_prereg_source_prepared_own_AW16_gate_required',top='genefer_anext_upper_core_v1',
        source_sha256=sources,parent_manifest_sha256=pin,native_source_manifest_sha256=ROLE_SHA,required_native_gate=REQUIRED,
        note='Upper canonical sum/rhs prereg replaces one alignmentFF; exact point-only cycle calendar. No inherited clock/1000/adoption.')
    m['control_sha256']={n:source.point.sha(project/n) for n in m['control_sha256']};save(project/'manifest.json',m)
    spec=rename(spec);spec['sources']={'rtl/'+n:h for n,h in sources.items()};spec['settings']={**m['control_sha256'],'manifest.json':source.point.sha(project/'manifest.json')}
    structural=source_inventory(project,spec)
    if structural['findings']:raise ValueError('upperfit structural findings')
    context=(verify_four if workers==4 else six.verify_project)(project)
    save(output/'inventory.json',spec);save(output/'project-context.json',context)
    result=dict(status='PASS_source_preparation_own_native_gate_required',manifest_sha256=source.point.sha(project/'manifest.json'),
        inventory_sha256=source.point.sha(output/'inventory.json'),context_sha256=source.point.sha(output/'project-context.json'),
        compiled_sv=30,compile_processors=workers,period_ns=9.668,seed=1,required_native_gate=REQUIRED,
        structural_result=structural,fit_launched=False,promotion_allowed=False)
    save(output/'source-preparation.json',result);return result
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,required=True);a=p.parse_args();print(json.dumps(prepare(a.output,a.workers),indent=2))
