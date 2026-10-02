"""Unchanged-source full-flow counterpart of the measured P16 SYN screen.

This constructor does not launch vendor tools. It creates a new immutable
whole project plus a checked declared transfer inventory, never edits the
synthesis snapshot or imports a field/component exemption.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from . import stream27_p16_diet_whole_physical as screen
from fpga.cloud.plain_fit_v5 import FULL_TCL
from fpga.tools.prefit_structural_guard_v1 import source_inventory

ROOT=screen.ROOT
SELF='reference/stream27_p16_diet_whole_fit.py'
BASE=ROOT/'artifacts/s4-p8-canonical-pipe-whole-aw16-f164-v2/inventory.json'
BASE_PIN='2638b73a36a52ba104f384cf0c6c8e683f765054a17f8b3d1d383456d994e794'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(project,m):
    screen.need(sha(BASE)==BASE_PIN,'STRUCTURAL_TEMPLATE_PIN')
    spec=json.loads(BASE.read_text())
    sources={
        'genefer_stream27_host_chain_aw16_p8_canonreg_v1.sv':m['top']+'.sv',
        'genefer_stream27_threefield_carry_aw16_p8_param_v1_signed.sv':'genefer_stream27_threefield_carry_aw16_p16_v1_host_v1.sv',
        'genefer_stream27_warm_chain_aw16_p8_param_v1.sv':'genefer_stream27_warm_chain_aw16_p16_v1.sv',
        'genefer_stream27_chain_canonical_aw16_p8_canonreg_v1.sv':'genefer_stream27_chain_canonical_aw16_p16_v1.sv',
        'genefer_stream27_blockcarry_setup_param_v1.sv':'genefer_track_a4_setup_v1.sv',
        'genefer_stream27_blockcarry_lane_param_v1.sv':'genefer_track_a4_blockcarry_lane_v1.sv',
        'genefer_stream27_merged_final_gs_pair_v1.sv':'genefer_stream27_merged_final_gs_pair_v1_p16_diet_v1.sv',
        'genefer_ntt_banked27_engine.sv':'genefer_ntt_banked27_engine_p16_diet_v1.sv'}
    for field,root in enumerate(m['diet_binding']['new_roots']):
        sources[f'genefer_stream27_shared_warm_aw16_p8_f{field}_v1_signed_host_v3_valid_start_v4.sv']=root+'.sv'
        sources[f'genefer_stream28_merged_gs_aw16_p8_f{field}_v1.sv']=f'genefer_stream28_merged_gs_aw16_p16_f{field}_v1_shared_comm_mlab_v1.sv'
    def change(value):
        if isinstance(value,dict):return {key:change(child) for key,child in value.items()}
        if isinstance(value,list):return [change(child) for child in value]
        if isinstance(value,str):
            if value.startswith('rtl/') and value[4:] in sources:return 'rtl/'+sources[value[4:]]
            return value.replace('genefer_ntt_difdit_butterfly27.y1','genefer_ntt_difdit_butterfly27_p16_diet_v1.y1')
        return value
    spec=change(spec)
    spec['identity']=dict(top=m['top'],device=m['device'],parameters=m['core_parameters'],clock_period_ns=10,seed=1)
    spec['sources']={'rtl/'+name:pin for name,pin in m['source_sha256'].items()}
    spec['settings']={**m['control_sha256'],'manifest.json':sha(project/'manifest.json')}
    spec['source_binding_note']='P16 actual whole source, not inherited P8 physical/native qualification. Every sequential/companion anchor is checked against this exact58RTL project.'
    for item in spec['exclusions']:
        if item['kind']=='inside_single_macroblock' and 'field' in item['reason']:
            item['reason']='Real fullN P16 three fields with serialized correction2/shared temporal commutator MLAB1/factored Montgomery1; internal placement/STA remains vendor work, not source inventory inference.'
    companions=0
    for transfer in spec['transfers']:
        for anchor in transfer.get('companion_source_anchors',[]):
            screen.need(anchor['source'] in spec['sources'],'COMPANION_CLOSURE')
            text=(project/anchor['source']).read_text()
            if 'scope_marker' in anchor:
                screen.need(text.count(anchor['scope_marker'])==1,'COMPANION_SCOPE')
                text=text.split(anchor['scope_marker'],1)[1]
            screen.need(text.count(anchor['text'])==1,'COMPANION_ANCHOR:'+anchor['text']);companions+=1
    result=source_inventory(project,spec)
    screen.need(not result['findings'],'STRUCTURAL_FINDINGS:'+repr(result['findings']))
    return spec,result,companions


def prepare(manifest,source,destination,screen_project):
    destination=Path(destination).resolve();screen_project=Path(screen_project).resolve()
    screen.need(screen_project.is_relative_to(ROOT),'SCREEN_PATH')
    observed=json.loads((screen_project/'manifest.json').read_text())
    result=screen.prepare(manifest,source,destination,workers=6)
    project=destination/'project';m=json.loads((project/'manifest.json').read_text())
    screen.need(m['source_sha256']==observed['source_sha256'] and m['core_parameters']==observed['core_parameters'],
        'UNCHANGED_MEASURED_WHOLE_SOURCE')
    (project/'run.tcl').write_text(FULL_TCL)
    m.update(status='unchanged_source_full_flow_candidate_NOT_physical_GO',allowed_stages=['syn','fit','sta'],
        fit_allowed=True,whole_resource_go=False,whole_resource_measurement_required=False,
        screen_project_manifest_sha256=sha(screen_project/'manifest.json'),
        runtime_profile='whole-p16-full-four-hour-v1',
        resource_screen_scope='Actual unplaced synthesis estimates; conditional placement experiment only, not needed/placed or timing proof.')
    m['control_sha256']['run.tcl']=sha(project/'run.tcl')
    m['preparation_source_sha256'][SELF]=sha(ROOT/SELF)
    m['notes']=['Exact58RTL, public ABI/config and signed host/CRT/carry are unchanged from actual whole SYN screen and full9 normal.',
        'Full synthesis/fit/four-corner STA; no assembler, no field exemption, no P8 runtime-profile relabel.',
        'Four-hour native execution cap is conservative from measured source screen/prior related fits, not a completion prediction.',
        'Normal and unplaced resource-screen typed prerequisites plus runtime source/physical/RAM/deadline guards remain required.']
    (project/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    spec,structure,companions=inventory(project,m)
    (destination/'inventory.json').write_text(json.dumps(spec,indent=2)+'\n')
    result=dict(status='PASS_declared_source_only_full_flow_prepared',project=str(project),
        manifest_sha256=sha(project/'manifest.json'),inventory_sha256=sha(destination/'inventory.json'),
        source_screen_manifest_sha256=sha(screen_project/'manifest.json'),rtl_members=58,
        declared_transfers=len(spec['transfers']),companion_anchors=companions,
        source_findings=structure['findings'],physical_GO=False,promotion_allowed=False)
    (destination/'preparation.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('manifest','source','output','screen-project'):parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.manifest,args.source,args.output,args.screen_project),indent=2))
