"""Matched whole-field CT-fusion resource probe, not a whole-core fit.

Parent and candidate use the same captured composed25-file donor, same
10ns/seed1/6worker AWS shape, and their actual source-matched native gates.
Only candidate CT identifiers and the new private leaf differ in RTL.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from . import stream27_l3b_ct_field_native as native

ROOT=native.ROOT
SELF='reference/stream27_l3b_ct_field_probe.py'
PARENT='artifacts/s4-diet-warm-p16-f0-v1/project'
PARENT_PIN='cd4904e989817a0d15c90eb7dde704a7e25ad1a36f9d9187749c6d08ca481689'
NORMAL='artifacts/s4-l3b-ct-field-aw16-f0-normal-v1/input'
PARENT_GATE='s4-diet-field-aw16-p16-f0-normal-q1-v1'
CT_GATE='s4-l3b-ct-field-ct-aw16-p16-f0-q1-v1'


def need(ok,label):
    if not ok:raise ValueError('L3B_PROBE_'+label)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,value):
    with Path(path).open('x') as out:json.dump(value,out,indent=2);out.write('\n')


def prepare(destination,*,enabled=1):
    need(type(enabled) is int and enabled in (0,1),'ENABLE')
    destination=Path(destination).resolve();parent=ROOT/PARENT
    need(destination.is_relative_to(ROOT) and not destination.exists() and
         not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE','queue/PAUSE')),'FRESH_PAUSE')
    need(sha(parent/'manifest.json')==PARENT_PIN,'CAPTURED_COMPOSED_PARENT')
    m=json.loads((parent/'manifest.json').read_text())
    for group,subdir in (('source_sha256','rtl/'),('control_sha256','')):
        for name,pin in m[group].items():need(sha(parent/(subdir+name))==pin,'PARENT_BYTES:'+name)
    normal=ROOT/NORMAL;role=json.loads((normal/'manifest.json').read_text())
    meta=role['l3b_field'];source=normal/'source/fpga'
    need(not meta['mutant'] and meta['enabled']==1 and meta['production_top']==m['top']
         and meta['geometry']==m['geometry'],'CANDIDATE_PRODUCTION_JOIN')
    pins=meta['production_generated_sha256'] if enabled else m['source_sha256']
    sources={}
    for name,pin in pins.items():
        path=(source/'rtl'/name) if enabled else (parent/'rtl'/name)
        need(Path(name).name==name and not path.is_symlink() and sha(path)==pin,'IMMUTABLE_RTL:'+name)
        sources[name]=path.read_bytes()
    if enabled:
        change=meta['binding'];ct=change['forward_module'];leaf=Path(native.binding.NEW).name
        need(set(pins)==set(m['source_sha256'])|{leaf},'ONLY_NEW_LEAF')
        need(all(pins[name]==pin for name,pin in m['source_sha256'].items() if name!=ct),'ALL_NON_CT_SOURCE_MATCH')
        need(sources[ct].decode().replace(native.binding.TOP,native.binding.OLD)==(parent/'rtl'/ct).read_text(),'CT_REVERSE')
    project=destination/'project';(project/'rtl').mkdir(parents=True)
    for name,raw in sources.items():
        with (project/'rtl'/name).open('xb') as out:out.write(raw)
    qsf=(parent/'probe.qsf').read_text()
    anchor='NUM_PARALLEL_PROCESSORS 4';need(qsf.count(anchor)==1,'PARENT_WORKERS')
    qsf=qsf.replace(anchor,'NUM_PARALLEL_PROCESSORS 6')
    if enabled:qsf+='set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+leaf+'\n'
    controls={name:(qsf if name=='probe.qsf' else (parent/name).read_text()) for name in m['control_sha256']}
    for name,text in controls.items():
        with (project/name).open('x') as out:out.write(text)
    m=deepcopy(m);m.pop('qualified_native_manifest')
    m.update(schema='s4-l3b-matched-composed-field-sizing-v1',status='source_prepared_actual_native_gate_required',
        compile_processors=6,source_sha256=pins,control_sha256={name:sha(project/name) for name in controls},
        native_source_gate=CT_GATE if enabled else PARENT_GATE,
        l3b_ct_enabled=enabled,source_preparation_sha256={SELF:sha(ROOT/SELF)},
        matched_parent_manifest_sha256=PARENT_PIN,
        comparison_contract=dict(host_shape='AWS6 only',workers=6,clock_period_ns=10,seed=1,
            optimization_mode='unchanged parent default',baseline_qualified_file_count=25,
            scalar_area_not_field_credit=True,LAB_occupancy_gate=True,
            raw_fields=['LABs','needed_ALMs','placed_ALMs','registers','MLAB','M20K','DSP','setup','hold'],
            whole_chip_projection='Three actual field LABs plus measured shared logic and placement uncertainty; no automatic whole GO.'),
        scope='Matched composed P16 F0 single-field CT-only experiment; GS/final/point/correction/root/reset/calendar unchanged. No whole fit or promoted clock.',
        full_N_numeric_locally_performed=False,promotion_allowed=False)
    dump(project/'manifest.json',m)
    dump(destination/'preparation.json',dict(status=m['status'],project=str(project),
        native_source_gate=m['native_source_gate'],matched_parent_manifest_sha256=PARENT_PIN,
        RTL_members=len(pins),whole_GO=False))
    return dict(project=str(project),manifest_sha256=sha(project/'manifest.json'),native_source_gate=m['native_source_gate'])


def submit(project,*,enabled=1):
    from fpga.tools import fit_submit
    project=Path(project).resolve();m=json.loads((project/'manifest.json').read_text())
    need(m['l3b_ct_enabled']==enabled and m['compile_processors']==6,'EXACT_PREPARED_ROLE')
    expected=CT_GATE if enabled else PARENT_GATE
    need(m['native_source_gate']==expected,'ACTUAL_SOURCE_GATE_ID')
    identifier='s4-l3b-ct-composed-field-candidate-f0-v1' if enabled else 's4-l3b-ct-composed-field-parent-f0-v1'
    # The existing fit intake waits for actual normal PASS and compares all
    # report.sources['rtl/'+name] with this immutable physical source map.
    return fit_submit.submit(ROOT/'queue/standing-fits',identifier,project,'10',1,
        dict(aws6=['a','b']),'component_probe',dict(exemption='component_sizing_probe'),
        workers=6,priority=15,track='S',purpose='p16_diet',native_source_gate=expected)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path)
    p.add_argument('--project',type=Path);p.add_argument('--parent',action='store_true');p.add_argument('--submit',action='store_true')
    a=p.parse_args();print(json.dumps(submit(a.project,enabled=0 if a.parent else 1) if a.submit else
        prepare(a.output,enabled=0 if a.parent else 1),indent=2))
