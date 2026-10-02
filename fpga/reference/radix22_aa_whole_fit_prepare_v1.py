"""Source-only ONE whole point+RAM27 area experiment; no fit/host authority.

Reuse the actual frozen point AWS6 project and shared source verifier. The
whole caller ABI/control/math is unchanged; no F3/upper/cancel composition.
All native dependencies and normal whole-fit budgets still apply.
"""
import copy
import json
from pathlib import Path
from fpga.reference import radix22_aa_whole_source_v1 as s
from fpga.reference import radix22_aa_whole_prepare_v1 as native
from fpga.reference import anext_point_aws6_prepare_v1 as parent
from fpga.tools.prefit_structural_guard_v1 import source_inventory, identities

ROOT=s.ROOT
BASE='artifacts/anext-point-9668ps-aws6-plain-v1'
MANIFEST='3f2ba54d86b39afe482484b2afb9aee03b3f8c4b84306600d6daf616354ac84f'
CONTEXT='4d4980a0b08c57529901f13abad6834c823a700532fb7dfd94860f4ce1f804f3'
INVENTORY='a59fbf5a767955070d119ec2b70e0c9aa6160e357f1c2ab98d9544a0f291359d'
REQUIRED=['aa-pointdata27-block-aw5-f0-q1-v1','aa-pointdata27-whole-aw5-q1-v1',
          'aa-pointdata27-whole-aw8-q1-v1','aa-pointdata27-representative-aw16-q1-v1']


def rename(value):
    if isinstance(value,dict):return {rename(k):rename(v) for k,v in value.items()}
    if isinstance(value,list):return [rename(x) for x in value]
    return s.rename(value) if isinstance(value,str) else value


def save(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')


def input_context():
    base=ROOT/BASE;project=base/'project'
    s.need(s.sha(project/'manifest.json')==MANIFEST and s.sha(base/'project-context.json')==CONTEXT,
           'exact retained actual whole point source/context')
    s.need(s.sha(base/'inventory.json')==INVENTORY
           and s.sha(parent.__file__)=='71898fb3ce92649405d86ceeb8d5cc58f9602da0f9b1a47f51add907e23f1f35'
           and s.sha(ROOT/'tools/prefit_structural_guard_v1.py')=='9494570410b0cfb083ae0d383164cf773bf7f8e8298e2b81dca7580914383979',
           'retained inventory/shared source verifier pins')
    spec=json.loads((base/'inventory.json').read_text())
    s.need(spec['settings']['manifest.json']==MANIFEST,'retained parent inventory manifest')
    result=source_inventory(project,spec);s.need(not result['findings'],'retained declared source structure')
    s.need(parent.verify_project(project)==json.loads((base/'project-context.json').read_text()),'retained six-worker context')
    s.verify();m,files=native.role('representative-aw16')
    s.need(len(m['build']['sv_sources'])==31,'exact whole31RTL')
    old=json.loads((project/'manifest.json').read_text())
    for name in m['build']['sv_sources']:
        text=files[name].decode();oldname=s.reverse(Path(name).name)
        if name==s.field.RAM:
            s.need(s.sha(ROOT/name)==m['sources'][name],'verified RAM27 primitive');continue
        s.need(s.reverse(text).replace(s.field.NEW,s.field.OLD)==(project/'rtl'/oldname).read_text(),
               'every compiled source reverses to retained point '+name)
    return old,spec,m,files


def prepare(output):
    output=Path(output).resolve();base=ROOT/BASE;oldp=base/'project'
    s.need(not output.exists() and output.parent.is_dir() and not any((ROOT/x).exists() for x in ('docs/briefs/PAUSE','queue/PAUSE')),'fresh/no PAUSE')
    old,spec,role,files=input_context();p=output/'project';(p/'rtl').mkdir(parents=True)
    sources={}
    for name in role['build']['sv_sources']:
        target=p/'rtl'/Path(name).name
        with target.open('xb') as stream:stream.write(files[name])
        sources[target.name]=s.sha(target)
    for name in old['control_sha256']:
        text=(oldp/name).read_text()
        if name=='probe.qsf':
            text=s.rename(text)
            text+='set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+Path(s.field.RAM).name+'\n'
        with (p/name).open('x') as stream:stream.write(text)
    m=copy.deepcopy(old);m.update(status='AA_whole_source_prepared_native_dependencies_required_NOT_dispatched',
        top=s.CORE,source_sha256=sources,parent_manifest_sha256=MANIFEST,placement_parent_manifest_sha256=MANIFEST,
        native_source_manifest_sha256=s.sha(ROOT/'artifacts/aa-pointdata27-whole-v1/representative-aw16/manifest.json'),
        required_native_gate=REQUIRED[-1],required_native_gates=REQUIRED,
        arithmetic_profile_changed=False,external_ABI_changed=False,whole_range_contract=s.range_contract(),
        no_F3_upper_cancel_merge=True,area_or_clock_saving_claim=False,promotion_allowed=False,
        note='ONE point+RAM27 whole area experiment. Names plus ONE field data-RAM leaf only; full32 hardware admission retained. No field-times-three savings prediction; no inherited component clock or production adoption.')
    # Old native/source receipts are ancestry only, never the new whole gate.
    m['retained_point_parent_native_report_sha256']=m.pop('parent_native_report_sha256')
    m['retained_point_parent_native_source_manifest_sha256']=old['native_source_manifest_sha256']
    m['retained_point_parent_source_ticket_sha256']=m.pop('parent_source_ticket_sha256')
    m['control_sha256']={name:s.sha(p/name) for name in old['control_sha256']}
    save(p/'manifest.json',m)
    spec=rename(spec);spec['sources']={'rtl/'+name:pin for name,pin in sources.items()}
    spec['settings']={**m['control_sha256'],'manifest.json':s.sha(p/'manifest.json')}
    spec['unresolved_native_coverage']=[
        'r53 supersedes inherited r47 DA/early-placement launch gates: diagnostics remain post-fit; no exhaustive graph or timing closure is inferred.',
        'All inherited explicit immediate protocol/status/control exceptions retained unchanged under namespace substitution.']
    structural=source_inventory(p,spec);s.need(not structural['findings'],'new whole declared source findings')
    context=parent.verify_project(p)
    for name in ('probe.qpf','probe.sdc','run.tcl'):s.need((p/name).read_bytes()==(oldp/name).read_bytes(),'unchanged '+name)
    restored=s.reverse((p/'probe.qsf').read_text()).replace('set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+Path(s.field.RAM).name+'\n','')
    s.need(restored==(oldp/'probe.qsf').read_text(),'QSF namespace and ONE additional RAM leaf only')
    save(output/'inventory.json',spec);save(output/'project-context.json',context)
    result=dict(status='PASS_declared_whole_source_inventory_ONLY_native_dependency_pending_no_fit',**identities(spec),
        manifest_sha256=s.sha(p/'manifest.json'),inventory_sha256=s.sha(output/'inventory.json'),context_sha256=s.sha(output/'project-context.json'),
        parent_manifest_sha256=MANIFEST,parent_context_sha256=CONTEXT,compiled_sv=31,clock_period_ns=9.668,
        seed=1,compile_processors=6,intermediate_snapshots=True,required_native_gates=REQUIRED,
        source_structural=structural,structural_checker_sha256=s.sha(ROOT/'tools/prefit_structural_guard_v1.py'),
        whole_fit_budget_required=True,field_probe_exemption_NOT_used=True,normal_whole_runtime_seconds=21600,
        fit_launched=False,source_only_no_host_slot_claim=True,promotion_allowed=False,
        measured_field_savings_NOT_scaled=True,expected_point_parent_cycle_delta=0)
    save(output/'source-preparation.json',result);return result


if __name__=='__main__':
    import argparse
    q=argparse.ArgumentParser(description=__doc__);q.add_argument('--output',type=Path,required=True)
    a=q.parse_args();print(json.dumps(prepare(a.output),indent=2))
