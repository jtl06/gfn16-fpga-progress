"""R10 lean source-bound physical preparation; host GL unimplemented."""
import argparse
import copy
import importlib.util
import json
import re
from pathlib import Path
from .stream27_context_storage_combo_physical import ROOT,sha,need,read,encoded
from . import stream27_context_storage_combo_timing10_bind as candidate

PARENT=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-registerederror-physical-v1/physical-v2'
GENERATOR=ROOT/'reference/stream27_context_storage_combo_timing10_bind.py'
PIN='8404e36c688c040f47433b7aff2b5fbee34e438968f41898fe8fee6818f51491'
LABEL='lean build; host GL assumed (unimplemented)'


def build(role,gate):
    role=Path(role).resolve()
    need(sha(GENERATOR.read_bytes())==PIN,'frozen timing10 recipe')
    native=read(role/'manifest.json')
    small=read(role/'production-bundle.json')
    full_path=role.parent/'full-normal/production-bundle.json'
    full=read(full_path) if full_path.exists() else candidate.prepare(65536,p=16,contexts=2,enabled=1,lean_production=1)
    for b,n in ((small,256),(full,65536)):
        need(b['geometry']['n']==n and len(b['files'])==58,'own geometry/source58')
        need(b['source_sha256']['reference/stream27_context_storage_combo_timing10_bind.py']==PIN,'captured generator')
        need(b['generated_sha256']=={k:sha(v.encode()) for k,v in b['files'].items()},'complete captured map')
        need(b['context_timing10']['lean_production'] and b['lean_production']['label']==LABEL,'explicit lean branch')
    need(all(native['sources']['rtl/'+k]==v for k,v in small['generated_sha256'].items()),'actual own native source association')
    params=dict(native['build']['parameters'],AW=16)
    need(params==dict(full['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),'own compiled epoch/flags')
    parent=read(PARENT/'project/manifest.json')
    controls={}
    for name,pin in parent['control_sha256'].items():
        raw=(PARENT/'project'/name).read_bytes();need(sha(raw)==pin,'immutable R9 control '+name);controls[name]=raw
    qsf='\n'.join(line for line in controls['probe.qsf'].decode().splitlines()
          if not line.startswith(('set_global_assignment -name SYSTEMVERILOG_FILE ','set_parameter -name ')))+'\n'
    qsf=qsf.replace(parent['top'],full['top'])
    qsf+=''.join(f'set_parameter -name {k} {v}\n' for k,v in params.items())
    qsf+=''.join('set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+n+'\n' for n in full['files'])
    controls['probe.qsf']=qsf.encode()
    sdc=controls['probe.sdc'].decode();need(sdc.count('-period 16.000')==1,'parent clock')
    controls['probe.sdc']=sdc.replace('-period 16.000','-period 13.000').encode()
    metadata=copy.deepcopy(full['context_timing10']);metadata.pop('reversal_records')
    lean=copy.deepcopy(full['lean_production']);lean.pop('modified')
    manifest={k:copy.deepcopy(parent[k]) for k in ('scope','edition','device','compile_processors','seed',
        'address_width','bitstream_generation','allowed_stages','raw_multiplier_parameters','field_parameters','intermediate_snapshots')}
    manifest.update(status='prepared_R10_lean_own_AW8_provisional',label=LABEL,top=full['top'],
        clock_period_ns=13.0,geometry=full['geometry'],core_parameters=params,
        source_sha256=full['generated_sha256'],generator_source_sha256=full['source_sha256'],
        control_sha256={k:sha(v) for k,v in controls.items()},native_normal_id=gate,
        native_role_manifest_sha256=sha((role/'manifest.json').read_bytes()),context_timing10=metadata,lean_production=lean,
        notes=[LABEL,'Fresh R10 healthy numerical source gate; removed lean checking is not twin fault immunity.',
               'Final GS/full25 metadata6->7; full I8460/AW8I214. Coherent base/full56 profile snapshot at existing allocation edge.',
               'R9 full56 publication proposal/drain retained; copyN+4. No old clock/cycles or hardware benefit inheritance.',
               'ONE13ns Balanced seed1 AWS12/40GiB full4h under actual operator guards; host GL/rollback/deployment unimplemented.'])
    spec=read(PARENT/'structural-inventory.json')
    mappings={}
    for name,row in full['lean_production']['modified'].items():
        if name!=row['parent']:mappings[row['parent'][:-3]]=name[:-3]
    for name,row in full['context_timing10']['reversal_records'].items():
        if name!=row['parent']:mappings[row['parent'][:-3]]=name[:-3]
    replacements={
      'wire response_bad=shadow_row_valid && (shadow_response_context!=row_context_d ||':
        "wire response_bad=1'b0; // Lean: no full56 response verification.",
      'wire capture_bad=final_valid && (phase[final_context]!=RUN ||':
        "wire capture_bad=1'b0; // Lean: no full56/row capture verification.",
      'assign error=local_error || child_error || canon_error;':'assign error=local_error || lean_watchdog_error;',
      'assign safety_error=local_error || child_error_barrier || canon_error;':
        'assign safety_error=local_error || child_error_barrier || canon_error || lean_watchdog_error;',
      '(capture_req_d && !shadow_capture_ack) || (|child_cancelled))local_error<=1;':
        'if(ingress_bad || copy_bad || (capture_req_d && !shadow_capture_ack))local_error<=1;',
    }
    def remap(v):
        if isinstance(v,dict):return {k:remap(x) for k,x in v.items()}
        if isinstance(v,list):return [remap(x) for x in v]
        if isinstance(v,str):
            for _ in range(4):
                old=v
                for a,b in mappings.items():v=re.sub(r'\b'+re.escape(a)+r'\b',b,v)
                if old==v:break
            return replacements.get(v,v)
        return v
    spec=remap(spec)
    host='rtl/'+full['top']+'.sv';canon='rtl/genefer_stream27_canonical_image_timing10_v1.sv'
    for t in spec['transfers']:
        if t['id']=='source_to_warm':
            # Actual new-job config-valid clear extends the retained reset block.
            for a in t['exception']['contract_anchors']:
                if 'jobs<=start_contexts;cycles<=0;' in a['text']:
                    a['text']=a['text'].replace('publish_owner<=0;\n','publish_owner<=0;canonical_config_valid<=0;\n')
        if t['id']=='cold_registered_row_to_source':
            t['exception']['reason']='Registered RAM/source data/context route retained; lean disables full56 response verification on trusted healthy inputs. No fault-immunity inheritance.'
        if t['id']=='carry_boundary_to_fields':
            t['exception']['reason']='Boundary coherent input FF/cache78 retained. R10 final GS adds one edge with full25 metadata, so PW remains but SINK/carry/digit/I increase1; AW8I214/fullI8460. Carry frame-base terms are accepted-profile registers; no raw constant substitution.'
        if t['id']=='shadows_to_canonical_scratch':
            t['exception']=dict(kind='phase_local_control',reason='Phase-exclusive row load and complete load/copy counters retained. Lean range checking and full56 row-response checks are disabled; no protected fault claim. Canonical thresholds capture accepted BEGIN base; speculative existing base register cannot create eligibility. Distinct coherent host profile transfer is declared separately.',
              contract_anchors=[dict(source=host,text='wire canonical_load=shadow_row_valid && !row_kind_d && !response_bad && !safety_error;'),
               dict(source=host,text="if(canonical_load && row_address_d==ROW_W'(ROWS-1))phase[canonical_owner]<=CANON_WAIT;"),
               dict(source=canon,text="wire base_ok=1'b1; // Lean trusted-profile assumption, not admission."),
               dict(source=canon,text='load_bad=0;correction_bad=0;direct_base_c0=0;input_c0=0;input_c1=0;'),
               dict(source=canon,text='if(state==IDLE && !error && begin_canonical)base_reg<=base;')])
        if t['id']=='prospective_fault_to_sticky_origin':
            t['exception']['reason']+=' Lean public error reports local framing/watchdog only; registered-source safety_error and R9 publication fence remain. Removed lean owner/range detectors are not present or credited.'
    spec['transfers'].append(dict(id='coherent_profile_to_canonical',producer='host_control',consumer='canonical_scratch',
      signals=['canonical_owner','canonical_config_base','canonical_config_owner','canonical_config_valid','canonical_config_bad'],
      registered_stages=[dict(id='scratch_profile_allocation',owner='host_control',edge=0,kind='flop',source=host,
       payload=['canonical_config_base'],valid='canonical_config_valid',metadata=['canonical_owner','canonical_config_owner'],
       anchors=['canonical_owner<=phase[0]!=RAW_READY;canonical_owned<=1;load_row<=0;load_requested<=0;',
                'canonical_config_valid<=1;canonical_config_base<=job_base[phase[0]!=RAW_READY];',
                'canonical_config_owner<=live_owner[(phase[0]!=RAW_READY)*56+:56];'],alignment='same_accepted_edge')],
      control_reconvergence=[],exception=dict(kind='operation_latched_configuration',
       reason='Existing RAW_READY allocation edge atomically selects context,32base,full56owner. Later load/begin/read/publication validate snapshot; reset/newjob/abort invalidates. Job profile immutable while scratch owned; no stale prior-cycle live-component base assumption or new scheduling edge.',
       contract_anchors=[dict(source=host,text=x) for x in (
        '.begin_canonical(canonical_begin),.base(canonical_config_base),',
        'wire canonical_config_bad=(canonical_load || canonical_begin || canonical_read || publish_pending) &&',
        '(!canonical_config_valid || canonical_config_owner!=live_owner[canonical_owner*56+:56]);',
        'if(canonical_config_bad)local_error<=1;', 'if(safety_error)canonical_config_valid<=0;')])) )
    for x in spec['exclusions']:
        if 'R7 packed-stage full tag mismatch' in x['reason']:
            x['reason']='Lean owner mismatch verification removed; full generation routing/eligibility and frame data timing retained. No detector coverage claim.'
    spec['exclusions'].append(dict(kind='inside_single_macroblock',reason=LABEL+'. Final inverse full25 slot/start/generation alignment6->7 is explicit in generated GS source; all field endpoints now use new SINK. Canonical/term/carry timing edits and private ENA split are source-own, not a netlist or physical benefit proof.',
       endpoints=['three final inverse GS paths/full25 metadata','canonical accepted-base terms','term payload selector','carry accepted-profile terms']))
    spec['identity'].update(top=full['top'],parameters=params,clock_period_ns=13.0)
    spec['sources']={'rtl/'+n:pin for n,pin in full['generated_sha256'].items()}
    spec['settings']=dict(manifest['control_sha256'],**{'manifest.json':sha(encoded(manifest))})
    files={'rtl/'+n:t.encode() for n,t in full['files'].items()};files.update(controls)
    proof=dict(schema='fit-provisional-aw8-geometry-v1',generator=dict(path=str(GENERATOR),sha256=PIN),
       kwargs=dict(p=16,contexts=2,enabled=1,lean_production=1),native_n=256,fit_n=65536)
    return manifest,files,spec,proof


def prepare(output,role,gate):
    out=Path(output).resolve();need(out.is_relative_to(ROOT) and not out.exists(),'fresh R10 output')
    manifest,files,spec,proof=build(role,gate)
    for name,raw in files.items():
        p=out/'project'/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    (out/'project/manifest.json').write_bytes(encoded(manifest))
    for name,obj in [('structural-inventory.json',spec),('provisional-geometry.json',proof)]:
        (out/name).write_bytes(encoded(obj))
    for t in spec['transfers']:
        for a in t.get('exception',{}).get('contract_anchors',[]):
            need(a['source'] in files and files[a['source']].decode().count(a['text'])==1,
                 'R10 exact anchor '+t['id']+': '+repr(a))
    loader=importlib.util.spec_from_file_location('r10_guard',ROOT/'tools/prefit_structural_guard_v1.py')
    guard=importlib.util.module_from_spec(loader);loader.loader.exec_module(guard)
    result=guard.source_inventory(out/'project',spec);need(not result['findings'],'R10 structural findings')
    return dict(project=str(out/'project'),source_count=58,crossings=len(spec['transfers']),
       structural_sha256=sha(encoded(spec)),provisional_sha256=sha(encoded(proof)),source_findings=result['findings'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path)
    p.add_argument('--native-role',required=True,type=Path);p.add_argument('--native-gate',required=True);a=p.parse_args()
    print(json.dumps(prepare(a.output,a.native_role,a.native_gate),indent=2))
