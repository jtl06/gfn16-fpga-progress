"""ONE matched F0 field trial, reusing the exact measured AWS6 parent."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from . import stream27_product_split as s

ROOT=s.ROOT
SELF='reference/stream27_product_split_field_probe.py'
PARENT='artifacts/s4-l3b-ct-composed-field-parent-f0-v1/project'
MEASURED='queue/standing-fit-state/terminal/s4-l3b-ct-composed-field-parent-f0-v1/evidence/project'
NORMAL='artifacts/s4-product-split-field-aw16-f0-normal-v1/input'
GATE='s4-product-split-field-aw16-f0-normal-q1-v1'

def read_json(path):return json.loads(Path(path).read_text())
def dump(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2);f.write('\n')

def prepare(output):
    output=Path(output).resolve();s.need(output.is_relative_to(ROOT) and not output.exists(),'FIELD_PROBE_FRESH')
    parent=ROOT/PARENT;measured=ROOT/MEASURED;m=read_json(parent/'manifest.json');captured=read_json(measured/'manifest.json')
    s.need(m['source_sha256']==captured['source_sha256'] and m['compile_processors']==6 and m['clock_period_ns']==10 and m['seed']==1,'ACTUAL_PARENT_CONTEXT')
    for name,pin in m['source_sha256'].items():
        s.need(s.sha((parent/'rtl'/name).read_bytes())==pin==s.sha((measured/'rtl'/name).read_bytes()),'PARENT_RTL_BYTES:'+name)
    for name,pin in m['control_sha256'].items():
        s.need(s.sha((parent/name).read_bytes())==pin,'PARENT_CONTROL:'+name)
        raw=(measured/name).read_bytes();suffix=b'set_global_assignment -name LAST_QUARTUS_VERSION "26.1.0 Pro Edition"\n'
        expected=(parent/name).read_bytes()
        if name=='probe.qsf':
            anchor=b'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON\n'
            s.need(expected.count(anchor)==1,'EXACT_STANDING_SNAPSHOT_CASE')
            expected=expected.replace(anchor,anchor.replace(b' ON\n',b' on\n'))
            s.need(raw==expected+suffix,'ACTUAL_PARENT_CONTROL:'+name)
        else:s.need(raw==expected,'ACTUAL_PARENT_CONTROL:'+name)
    normal=ROOT/NORMAL;role=read_json(normal/'manifest.json');meta=role['product_split_field'];source=normal/'source/fpga'
    s.need(not meta['mutant'] and meta['production_top']==m['top'] and meta['geometry']==m['geometry'],'PRODUCTION_GEOMETRY_JOIN')
    pins=meta['production_generated_sha256'];leaf=Path(s.RTL).name;changed=meta['binding']['changed_consumers']
    s.need(set(pins)==set(m['source_sha256'])|{leaf} and meta['binding']['lazy_only'],'ONLY_PRIVATE_LAZY_LEAF')
    original='genefer_stream27_montgomery28x27_factored_v1';replacement=s.NAMES[original]
    project=output/'project';(project/'rtl').mkdir(parents=True)
    for name,pin in pins.items():
        raw=(source/'rtl'/name).read_bytes();s.need(s.sha(raw)==pin,'CANDIDATE_RTL:'+name)
        if name in changed:s.need(raw.decode().replace(replacement,original)==(parent/'rtl'/name).read_text(),'LAZY_IDENTIFIER_REVERSE:'+name)
        elif name!=leaf:s.need(pin==m['source_sha256'][name],'UNTOUCHED_FIELD_RTL:'+name)
        with (project/'rtl'/name).open('xb') as f:f.write(raw)
    controls={name:(parent/name).read_bytes() for name in m['control_sha256']}
    controls['probe.qsf']=controls['probe.qsf'].replace(
        b'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON\n',
        b'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS on\n')
    controls['probe.qsf']+=f'set_global_assignment -name SYSTEMVERILOG_FILE rtl/{leaf}\n'.encode()
    for name,raw in controls.items():
        with (project/name).open('xb') as f:f.write(raw)
    m=deepcopy(m);m.update(schema='stream27-product-split-matched-field-v1',status='source_prepared_native_gate_required',
        source_sha256=pins,control_sha256={n:s.sha(raw) for n,raw in controls.items()},native_source_gate=GATE,
        source_preparation_sha256={SELF:s.sha((ROOT/SELF).read_bytes())},product_split=meta['binding'],
        matched_parent_manifest_sha256=s.sha((parent/'manifest.json').read_bytes()),
        matched_parent_measured_receipt='queue/standing-fit-state/terminal/s4-l3b-ct-composed-field-parent-f0-v1/receipt.json',
        comparison_contract=dict(host_shape='AWS6',workers=6,clock_period_ns=10,seed=1,
            parent_sources_and_controls_actual_match=True,canonical_root_square_consumers_unchanged=True,
            standing_control_normalization='exact ON->on snapshot-value case plus preserved native version suffix only',
            delta_only='lazy consumer module identifiers + isolated product split leaf + QSF file inclusion',
            raw_fields=['LAB','needed ALM','placed ALM','registers','MLAB','M20K','DSP','setup','hold']),
        scope='ONE lazy-only composed P16 F0 field trial vs exact measured parent. No field-times-three or whole clock/area credit.',promotion_allowed=False)
    dump(project/'manifest.json',m);return dict(project=str(project),status=m['status'],native_source_gate=GATE,changed_consumers=changed)

def submit(project):
    from fpga.tools import fit_submit
    project=Path(project).resolve();m=read_json(project/'manifest.json')
    s.need(m['native_source_gate']==GATE and m['compile_processors']==6 and m['comparison_contract']['parent_sources_and_controls_actual_match'],'FIELD_PROBE_ROLE')
    return fit_submit.submit(ROOT/'queue/standing-fits','s4-product-split-composed-field-f0-v1',project,'10',1,
        dict(aws6=['a','b']),'component_probe',dict(exemption='component_sizing_probe'),workers=6,priority=15,
        track='S',purpose='p16_diet',native_source_gate=GATE)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path);p.add_argument('--project',type=Path);p.add_argument('--submit',action='store_true')
    a=p.parse_args();print(json.dumps(submit(a.project) if a.submit else prepare(a.output),indent=2))
