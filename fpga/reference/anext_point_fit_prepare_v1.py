"""Matched plain whole-core point successor, source preparation not dispatch."""
import copy
import json
from pathlib import Path
from fpga.reference import anext_point_source_v1 as point
from fpga.tools.prefit_structural_guard_v1 import source_inventory,identities

ROOT=point.ROOT
PARENT='artifacts/anext-9668ps-f16-plain-v2'
PARENT_SHA='41b2fe9d4eb5648f4728ff89cd2ce5a0c43242d6ef6bc0b6b8818f38b9c37742'
INVENTORY_SHA='07b158b5ce8cbe8d108f7008be4887bf68b58d1618e46f0a5a56bc259bb28f3d'
ROLE='artifacts/anext-point-representative-aw16-role-v1'
ROLE_SHA='98ae80e62e95f70d08acf1d03af9bb9fdf84003852d900afaecce769d358c84a'
REQUIRED='anext-point-representative-aw16-q1-v1'

def rename(value):
    if isinstance(value,dict):return {rename(k):rename(v) for k,v in value.items()}
    if isinstance(value,list):return [rename(x) for x in value]
    if isinstance(value,str):
        for old,new in point.NAMES.items():value=value.replace(old,new)
    return value

def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')

def prepare(output):
    output=Path(output).resolve();old=ROOT/PARENT/'project'
    if output.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('fresh output/no PAUSE')
    for path,pin in ((old/'manifest.json',PARENT_SHA),(ROOT/PARENT/'inventory.json',INVENTORY_SHA),(ROOT/ROLE/'manifest.json',ROLE_SHA)):
        if point.sha(path)!=pin:raise ValueError('point physical parent/role pin')
    point.verify();m=json.loads((old/'manifest.json').read_text());role=json.loads((ROOT/ROLE/'manifest.json').read_text())
    for name,pin in m['source_sha256'].items():
        if point.sha(old/'rtl'/name)!=pin:raise ValueError('parent RTL drift')
    for name,pin in m['control_sha256'].items():
        if point.sha(old/name)!=pin:raise ValueError('parent setting drift')
    sources={};p=output/'project';(p/'rtl').mkdir(parents=True)
    for name in role['build']['sv_sources']:
        source=ROOT/ROLE/'source/fpga'/name
        if point.sha(source)!=role['sources'][name]:raise ValueError('native role drift')
        (p/'rtl'/Path(name).name).write_bytes(source.read_bytes());sources[Path(name).name]=role['sources'][name]
    if len(sources)!=30:raise ValueError('point30 RTL closure')
    for name in m['control_sha256']:
        text=(old/name).read_text()
        if name=='probe.qsf':text=rename(text)
        (p/name).write_text(text)
    m=copy.deepcopy(m);m.update(status='point_source_prepared_AW16_gate_required_not_dispatched',top='genefer_anext_point_core_v1',
        source_sha256=sources,parent_manifest_sha256=PARENT_SHA,native_source_manifest_sha256=ROLE_SHA,
        required_native_gate=REQUIRED,note='Point-only eight-site launch/tag delta; same command ABI and macro interfaces. No inherited clock, no upper-sum prereg, no promotion.')
    m['parent_native_report_sha256']=m.pop('native_report_sha256')
    m['control_sha256']={name:point.sha(p/name) for name in ('probe.qpf','probe.sdc','run.tcl','probe.qsf')}
    save(p/'manifest.json',m)
    spec=rename(json.loads((ROOT/PARENT/'inventory.json').read_text()))
    spec['sources']={'rtl/'+name:pin for name,pin in sources.items()}
    spec['settings']={**m['control_sha256'],'manifest.json':point.sha(p/'manifest.json')}
    structural=source_inventory(p,spec)
    if structural['findings']:raise ValueError('point structural findings')
    save(output/'inventory.json',spec)
    context=dict(manifest_sha256=point.sha(p/'manifest.json'),source_sha256=sources,control_sha256=spec['settings'],qsf_parameters={'AW':16})
    save(output/'project-context.json',context)
    result=dict(status='PASS_declared_source_inventory_only_native_dependency_pending',**identities(spec),
        manifest_sha256=point.sha(p/'manifest.json'),inventory_sha256=point.sha(output/'inventory.json'),context_sha256=point.sha(output/'project-context.json'),
        compiled_sv=30,structural_result=structural,required_native_gate=REQUIRED,
        clock_period_ns=9.668,seed=1,compile_processors=4,fit_launched=False,promotion_allowed=False,
        scope='Exact point-only whole successor. Source structural inventory is not routed timing or exhaustive netlist proof.')
    save(output/'source-preparation.json',result);return result

if __name__=='__main__':
    import argparse
    q=argparse.ArgumentParser();q.add_argument('--output',type=Path,required=True);a=q.parse_args();print(json.dumps(prepare(a.output),indent=2))
