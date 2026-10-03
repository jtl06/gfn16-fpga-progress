"""One queued R12 whole experiment; no running R11 or shared-source mutation."""
import argparse
import copy
import importlib.util
import json
import re
from pathlib import Path
from .stream27_context_storage_combo_physical import ROOT,sha,need,read,encoded
from . import stream27_context_feedback12_bind as source

PARENT=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-transport11-physical-v1/physical-12000-v1'
GENERATOR=ROOT/'reference/stream27_context_feedback12_bind.py'
PIN='52deb26ebc48c6538ff2f20b85b76897c68e3c4c6c3f7bdf45af55daa09be92b'
LABEL='lean build; host GL assumed (unimplemented)'
KWARGS=dict(p=16,contexts=2,enabled=1,lean_production=1,feedback_ingress_reg=1,
            auto_correction_ingress_reg=1,c0_admission_direct=1)


def build(role,gate,*,lean_production=1):
    need(lean_production in (0,1),'literal lean selector')
    kwargs=dict(KWARGS,lean_production=lean_production)
    label=LABEL if lean_production else 'protected build; own qualification required'
    role=Path(role).resolve();need(sha(GENERATOR.read_bytes())==PIN,'frozen R12 recipe')
    native=read(role/'manifest.json');small=read(role/'production-bundle.json')
    need(read(role/'global-ticket.json')['id']==gate,'actual own logical gate ID')
    fullpath=role.parent/'full-normal/production-bundle.json'
    full=read(fullpath) if fullpath.exists() else source.prepare(65536,**kwargs)
    for b,n in ((small,256),(full,65536)):
        need(b['geometry']['n']==n and len(b['files'])==58,'own source58/geometry')
        need(b['source_sha256']['reference/stream27_context_feedback12_bind.py']==PIN,'entrypoint pin')
        need(b['generated_sha256']=={k:sha(v.encode()) for k,v in b['files'].items()},'complete map')
        if lean_production:
            need(b['lean_production']['label']==LABEL,'lean scope')
        else:
            need(not b.get('lean_production') and 'LEAN_PRODUCTION' not in b['parameters'],
                 'protected source excludes lean override')
            need(b['parameters']['LEAN_PROGRESS_WATCHDOG']==0,'protected watchdog disabled')
        need(all(b['parameters'][k]==1 for k in ('CRT_TRANSPORT_REG','INVERSE_INGRESS_REG','TERM_JOIN_TRANSPORT_REG')),
             'baseline retains three R11 transports')
    need(all(native['sources']['rtl/'+k]==v for k,v in small['generated_sha256'].items()),'own native source')
    params=dict(native['build']['parameters'],AW=16)
    need(params==dict(full['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),'own compiled parameters')
    parent=read(PARENT/'project/manifest.json');controls={}
    for name,pin in parent['control_sha256'].items():
        raw=(PARENT/'project'/name).read_bytes();need(sha(raw)==pin,'immutable R11 control '+name);controls[name]=raw
    qsf='\n'.join(line for line in controls['probe.qsf'].decode().splitlines()
         if not line.startswith(('set_global_assignment -name SYSTEMVERILOG_FILE ','set_parameter -name ')))+'\n'
    qsf=qsf.replace(parent['top'],full['top'])
    qsf+=''.join(f'set_parameter -name {k} {v}\n' for k,v in params.items())
    qsf+=''.join('set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+k+'\n' for k in full['files'])
    controls['probe.qsf']=qsf.encode()
    metadata=copy.deepcopy(full['context_feedback12']);metadata.pop('source_edits');metadata.pop('host_calendar_edits')
    manifest={k:copy.deepcopy(parent[k]) for k in ('scope','edition','device','compile_processors','seed',
        'address_width','bitstream_generation','allowed_stages','raw_multiplier_parameters','field_parameters','intermediate_snapshots')}
    manifest.update(status='prepared_R12_'+('lean' if lean_production else 'protected')+'_feedback_own_AW8_provisional',label=label,top=full['top'],
        clock_period_ns=12.0,geometry=full['geometry'],core_parameters=params,
        source_sha256=full['generated_sha256'],generator_source_sha256=full['source_sha256'],
        control_sha256={k:sha(v) for k,v in controls.items()},native_normal_id=gate,
        native_role_manifest_sha256=sha((role/'manifest.json').read_bytes()),context_feedback12=metadata,
        notes=[label,'Fresh R12 source58 and own quicknormal; no other branch qualification or clock inherited.',
          'Paired feedback and auto-correction q add1 to recurrence interval, not field acceptance-relative F/C/PW/cache. FullI8464/AW8I218, fullFIFO0+q1/smallFIFO18+q1.',
          'Raw command/collision origin checks retained; descriptor ordinal/generation is rechecked before actual delayed accept. Cold R6 oneshot/publication unchanged.',
          'Field C0 direct predicate preserves unsigned(base-1) underflow atbase0; unlike canonical signed bound, base0 allows every signed32 magnitude here.',
          'ONE12ns Balanced seed1 full4h; actual allocation belongs to the accepted request. No declaredFF-to-density or clock benefit claim.'])
    spec=read(PARENT/'structural-inventory.json');renames={parent['top']:full['top']}
    if not lean_production:
        renames['genefer_stream27_host_image_rowwrite_lean_v1']='genefer_stream27_host_image_rowwrite_v1'
        renames['genefer_stream27_mdc_commutator_shared_packed_lean_v1']='genefer_stream27_mdc_commutator_shared_packed_faultlocal_v1'
    for old in parent['source_sha256']:
        if old.startswith(('genefer_stream27_shared_warm_aw','genefer_stream27_threefield_carry_aw','genefer_stream27_warm_contexts_aw')):
            new=old[:-3]+'_feedback12_v1.sv';need(new in full['files'],'actual graph rename '+old);renames[old[:-3]]=new[:-3]
    def remap(x):
        if isinstance(x,dict):return {k:remap(v) for k,v in x.items()}
        if isinstance(x,list):return [remap(v) for v in x]
        if isinstance(x,str):
            for a,b in renames.items():x=re.sub(r'\b'+re.escape(a)+r'\b',b,x)
            return x
        return x
    spec=remap(spec);warm='rtl/'+next(n for n in full['files'] if n.startswith('genefer_stream27_warm_contexts_aw'))
    if not lean_production:
        replacements={
          "wire response_bad=1'b0; // Lean: no full56 response verification.":
            'wire response_bad=shadow_row_valid && (shadow_response_context!=row_context_d ||',
          "wire capture_bad=1'b0; // Lean: no full56/row capture verification.":
            'wire capture_bad=final_valid && (phase[final_context]!=RUN ||',
          'assign safety_error=local_error || child_error_barrier || canon_error || lean_watchdog_error;':
            'assign safety_error=local_error || child_error_barrier || canon_error;',
          'assign error=local_error || lean_watchdog_error;':'assign error=local_error || child_error || canon_error;',
          "wire base_ok=1'b1; // Lean trusted-profile assumption, not admission.":
            "wire base_ok=base>=32'(BASE_MIN) && base<=32'd1000000000;",
          'load_bad=0;correction_bad=0;direct_base_c0=0;input_c0=0;input_c1=0;':
            "if(input_c0>=direct_base_c0 || input_c0<= -direct_base_c0 ||\n               input_c1>33'(K) || input_c1< -33'(K))correction_bad=1;",
        }
        for t in spec['transfers']:
            for a in t.get('exception',{}).get('contract_anchors',[]):
                a['text']=replacements.get(a['text'],a['text'])
            if t['id']=='cold_registered_row_to_source':
                t['exception']['reason']='Registered RAM/source context route plus full56 response verification remain protected; only own source qualification applies.'
            if t['id']=='shadows_to_canonical_scratch':
                t['exception']['reason']='Phase-exclusive row load, base/digit/correction range checks, full56 response checks and load/copy counters retained. Accepted BEGIN thresholds and separate coherent profile allocation remain; speculative base payload creates no eligibility.'
            if t['id']=='prospective_fault_to_sticky_origin':
                t['exception']['reason']='Raw prospective faults enter local sticky origin registers. Registered field/local errors feed global out_error one edge later; early registered-source safety barrier blocks eligibility and publication. Protected host public error includes child and canonical errors. No raw-pending source register or extra fault immunity is invented.'
        for e in spec['exclusions']:
            if 'lean build;' in e.get('reason',''):
                e['reason']='Protected source retains full25 final inverse alignment6->7, canonical profile/threshold/term/carry timing and zero-edge ENA split. Source inventory is not netlist completeness or timing proof.'
            if 'Lean watchdog' in e.get('reason',''):
                e['reason']='Six internal field transport transfers refine field scope; three field-to-CRT tuples refine existing crossings without double counting. Protected branch has no lean watchdog override.'
                e['endpoints']=[x for x in e.get('endpoints',[]) if x!='host lean_completed_seen']
    for t in spec['transfers']:
        if t['id']=='descriptors_to_warm_control':
            t['signals']+=['feedback_index_q','feedback_command_generation_q','feedback_double_q','feedback_feed_q','raw_command_bad','queued_command_bad']
            t['registered_stages']=[dict(id='feedback_descriptor_capture',owner='warm_control',edge=0,kind='flop',source=warm,
             payload=['feedback_index_q','feedback_double_q','feedback_feed_q'],valid='feedback_start_q',
             metadata=['feedback_command_generation_q','feedback_owner_q'],anchors=[
              'feedback_double_q<=raw_selected_double;feedback_feed_q<=latched_feed[raw_feedback_context];',
              'feedback_base_q<=chain_base[raw_feedback_context];feedback_index_q<=launched[raw_feedback_context];',
              'feedback_command_generation_q<=chain_generation[raw_feedback_context];'],alignment='same_accepted_edge')]
            t['exception']=dict(kind='phase_local_control',reason='Raw descriptor faults still occur at proposal edge; complete descriptor/base/owner proposal captured with feedback tuple. FIFO is not popped until actual delayed frame acceptance. Ordinal/generation/live chain are rechecked on acceptance; no prior-cycle permission reuse.',
              contract_anchors=[dict(source=warm,text=x) for x in (
               'wire raw_command_bad=raw_command_needed && (!command_valid[raw_feedback_context] ||',
               'wire queued_command_bad=command_needed && (!command_valid[feedback_context] ||',
               'wire command_bad=raw_command_bad || queued_command_bad;',
               'assign internal_frame_accept=delayed_feedback_slot && feedback_start_q && child_frame_accept;',
               'assign command_accept[0]=internal_frame_accept && latched_feed[0] && !feedback_context && !command_bad;')])
        if t['id']=='carry_feedback_to_warm':
            t['signals']+=['feedback_slot_q','feedback_start_q','feedback_data_q','feedback_owner_q','feedback_base_q']
            t['registered_stages']=[dict(id='complete_feedback_ingress',owner='warm_control',edge=0,kind='flop',source=warm,
             payload=['feedback_data_q','feedback_base_q'],valid='feedback_slot_q',metadata=['feedback_start_q','feedback_owner_q','feedback_double_q'],
             anchors=['feedback_slot_q<=feedback_slot;feedback_start_q<=feedback_slot && feedback_start;',
                      'feedback_data_q<=feedback_data;feedback_owner_q<=feedback_owner;'],alignment='same_accepted_edge')]
            t['exception']['reason']='Existing feedback FIFO remains full0/small18 rows, followed by exactly1 complete q tuple. Data/full25owner/first/base/double remain coherent; error barrier kills eligibility, raw and queued command checks govern acceptance. Interval increases1; do not call modeled total1/19 another physical FIFO allocation.'
            t['exception']['contract_anchors'] += [dict(source=warm,text=x) for x in (
                'wire delayed_feedback_slot=feedback_slot_q && !error_barrier;',
                '.base_in(delayed_feedback_slot ? feedback_base_q : base_in)',
                '.generation_in(delayed_feedback_slot ? feedback_owner_q[7:0] : generation_in)',
                '.epoch_in(delayed_feedback_slot ? feedback_owner_q[23:8] : epoch_in)')]
        if t['id']=='carry_boundary_to_fields':
            t['signals']+=['auto_correction_q','auto_c0_q','auto_c1_q','auto_context_q','auto_epoch_q','auto_generation_q']
            t['registered_stages']=[dict(id='complete_automatic_correction_ingress',owner='warm_control',edge=0,kind='flop',source=warm,
             payload=['auto_c0_q','auto_c1_q'],valid='auto_correction_q',metadata=['auto_context_q','auto_epoch_q','auto_generation_q'],
             anchors=['auto_correction_q<=auto_correction;',
                      'auto_c0_q<=next_c0;auto_c1_q<=next_c1;auto_context_q<=boundary_context;',
                      'auto_epoch_q<=next_epoch;auto_generation_q<=next_generation;'],alignment='same_accepted_edge')]
            t['exception']['reason']='Automatic correction only gains coherent c0/c1/context/epoch/generation q; cold correction path/retirement is literal. Paired feedback+correction delay prevents AW8 correction-before-frame. Field F/C/PW/SINK/cache78 unchanged relative to accepted frame; fullI8464/AW8I218.'
            t['exception']['contract_anchors'] += [dict(source=warm,text=x) for x in (
                'wire delayed_auto_correction=auto_correction_q && !error_barrier;',
                'assign internal_correction_accept=delayed_auto_correction && child_correction_accept;',
                '.correction_context(delayed_auto_correction ? auto_context_q : correction_context)',
                '.correction_valid((cold_correction || delayed_auto_correction) && !local_error)')]
    spec['exclusions'].append(dict(kind='inside_single_macroblock',
        reason='R12 field C0 direct magnitude predicate exactly preserves uint32(base-1), including base0 underflow. Numeric profile widths and checks outside this identity unchanged; source1663 new register bits are not mapped cost. Raw fault origin and delayed descriptor recheck both remain.',
        endpoints=['three field correction_c0_ok','warm feedback/automatic correction tuple transport']))
    # Explicit source evidence for field numeric identity; not a clock exception.
    t=next(t for t in spec['transfers'] if t['id']=='arithmetic_to_field0')
    t['exception']['contract_anchors'] += [dict(source='rtl/'+name,text=source.C0_FUNCTION.strip())
        for name in full['files'] if name.startswith('genefer_stream27_shared_warm_aw')]
    spec['identity'].update(top=full['top'],parameters=params,clock_period_ns=12.0)
    spec['sources']={'rtl/'+n:pin for n,pin in full['generated_sha256'].items()}
    spec['settings']=dict(manifest['control_sha256'],**{'manifest.json':sha(encoded(manifest))})
    files={'rtl/'+n:t.encode() for n,t in full['files'].items()};files.update(controls)
    proof=dict(schema='fit-provisional-aw8-geometry-v1',generator=dict(path=str(GENERATOR),sha256=PIN),
               kwargs=kwargs,native_n=256,fit_n=65536)
    return manifest,files,spec,proof


def prepare(output,role,gate,*,lean_production=1):
    out=Path(output).resolve();need(out.is_relative_to(ROOT) and not out.exists(),'fresh R12 output')
    manifest,files,spec,proof=build(role,gate,lean_production=lean_production)
    for name,raw in files.items():
        p=out/'project'/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    (out/'project/manifest.json').write_bytes(encoded(manifest))
    for name,obj in [('structural-inventory.json',spec),('provisional-geometry.json',proof)]:
        (out/name).write_bytes(encoded(obj))
    for t in spec['transfers']:
        for a in t.get('exception',{}).get('contract_anchors',[]):
            need(a['source'] in files and files[a['source']].decode().count(a['text'])==1,'R12 anchor '+t['id']+': '+repr(a))
    loader=importlib.util.spec_from_file_location('r12_guard',ROOT/'tools/prefit_structural_guard_v1.py')
    guard=importlib.util.module_from_spec(loader);loader.loader.exec_module(guard)
    result=guard.source_inventory(out/'project',spec);need(not result['findings'],'R12 structural findings')
    return dict(project=str(out/'project'),source_count=58,crossings=len(spec['transfers']),
       structural_sha256=sha(encoded(spec)),provisional_sha256=sha(encoded(proof)),source_findings=result['findings'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path)
    p.add_argument('--native-role',required=True,type=Path);p.add_argument('--native-gate',required=True);a=p.parse_args()
    print(json.dumps(prepare(a.output,a.native_role,a.native_gate),indent=2))
