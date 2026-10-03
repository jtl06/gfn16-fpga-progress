"""Private R14 physical-source handoff; no launch or inherited qualification."""
import copy
import json
import re
from pathlib import Path
from . import stream27_host_offload_chip_v1 as chip

ROOT=chip.ROOT
PARENT=ROOT/'results/throughput-20260929/trackS-c2-protected-relay13-physical-v1/physical-11500-v1'
PIN='d40c8bf31af7261a4efec1af50debf682beb92c6046bb77c37dc7ca34d7fce03'
def encoded(x):return (json.dumps(x,indent=2)+'\n').encode()


def build(*,period=12.0,seed=1):
    chip.need(period in (11.5,12.0) and type(seed) is int and 1<=seed<=3,'BOUNDED_PHYSICAL_SETTINGS')
    chip.need(chip.sha((ROOT/chip.SELF).read_bytes())==PIN,'FROZEN_PRIVATE_CHIP')
    b=chip.prepare(65536,host_offload=1)
    parent=json.loads((PARENT/'project/manifest.json').read_text())
    controls={name:(PARENT/'project'/name).read_bytes() for name in parent['control_sha256']}
    chip.need(all(chip.sha(raw)==parent['control_sha256'][name] for name,raw in controls.items()),'PARENT_CONTROLS')
    params=dict(b['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42)
    qsf='\n'.join(line for line in controls['probe.qsf'].decode().splitlines()
        if not line.startswith(('set_global_assignment -name SYSTEMVERILOG_FILE ','set_parameter -name ')))+'\n'
    qsf=qsf.replace(parent['top'],b['top'])
    qsf=re.sub(r'(?m)^set_global_assignment -name SEED \d+$',f'set_global_assignment -name SEED {seed}',qsf)
    scalars=('off_begin','off_write','off_commit','off_context','off_raw_ready','off_boundary_ready',
        'off_error','off_raw_valid','off_raw_context','off_boundary_valid','off_boundary_context')
    vectors=('off_index','off_word','off_base','off_generation','off_reciprocal','off_limit','off_epoch',
        'off_loaded','off_done','off_raw_owner','off_boundary_owner','off_raw_row','off_raw_data','off_c0','off_c1')
    for port in scalars+tuple(x+'[*]' for x in vectors):
        qsf+=f'set_instance_assignment -name VIRTUAL_PIN ON -to {{{port}}}\n'
    qsf+=''.join(f'set_parameter -name {k} {v}\n' for k,v in params.items())
    qsf+=''.join(f'set_global_assignment -name SYSTEMVERILOG_FILE rtl/{name}\n' for name in b['files'])
    controls['probe.qsf']=qsf.encode()
    chip.need(controls['probe.sdc'].decode().count('-period 11.500')==1,'PARENT_CLOCK')
    controls['probe.sdc']=controls['probe.sdc'].replace(b'-period 11.500',f'-period {period:.3f}'.encode())
    manifest=copy.deepcopy(parent)
    for key in ('context_protected_relay13','native_normal_id','native_role_manifest_sha256'):
        manifest.pop(key,None)
    manifest.update(status='R14_source_only_NOT_fit_released',label='protected R13 plus private HOST_OFFLOAD',
        top=b['top'],core_parameters=params,seed=seed,clock_period_ns=period,
        source_sha256=b['generated_sha256'],generator_source_sha256=b['source_sha256'],
        control_sha256={k:chip.sha(v) for k,v in controls.items()},
        host_offload=dict(parent_bundle_sha256=b['host_offload']['parent_bundle_sha256'],
            compiler_sha256=PIN,enabled=True,matched_equivalence_REQUIRED=True,
            host_time_excluded=True,full_protected_warm_graph=True,setup_retained=True,
            shared_warm_reducers_retained=True,final_canonical_materialization_offchip=True,
            exact_off_parent_preserved=True,cold_residue_storage_bits=3*2*65536*27,
            raw_RAM_bits_are_not_M20K_or_net_savings=True),
        notes=['PRIVATE R14 on exact frozen R13; no R13 job or shared source edit.',
            'Cold canonical staging adds three residue planes; no setup/reducer removal credit.',
            'Raw final receiver is fixed cadence: stalled transfer faults, no completion.',
            'No parent canonical-publication calendar, end-to-end timing, area or clock inherited.',
            'Own AW8/full equivalence must close by 04:30UTC before own fit admission.'])
    spec=json.loads((PARENT/'structural-inventory.json').read_text())
    rename={name[:-3]:row['new_file'][:-3] for name,row in b['host_offload']['source_edits'].items()}
    def remap(x):
        if isinstance(x,dict):return {k:remap(v) for k,v in x.items()}
        if isinstance(x,list):return [remap(v) for v in x]
        if isinstance(x,str):
            for old,new in rename.items():x=re.sub(r'\b'+re.escape(old)+r'\b',new,x)
        return x
    spec=remap(spec)
    removed={'cold_registered_row_to_source','final_capture_to_shadows','shadows_to_canonical_scratch',
        'canonical_read_to_copy','copy_to_shadow_publication','published_readback_to_host','coherent_profile_to_canonical'}
    spec['transfers']=[t for t in spec['transfers'] if t['id'] not in removed]
    host='rtl/'+rename[chip.capture(65536)['top']]+'.sv'
    leaf='rtl/'+Path(chip.LEAF).name
    for t in spec['transfers']:
        if t['id']=='source_to_warm':
            t['signals']+=['off_source_planes','off_lows','off_highs']
            t['exception']['reason']+=' R14 cold canonical residue payload substitutes zero placeholder reducer data at matched k+3/k+5; all warm paths stay literal.'
        if t['id']=='prospective_fault_to_sticky_origin':
            for a in t['exception']['contract_anchors']:
                a['text']=a['text'].replace('assign safety_error=local_error || child_error_barrier || canon_error;',
                    'assign safety_error=local_error || child_error_barrier || canon_error || off_ingress_error;')
                a['text']=a['text'].replace('assign error=local_error || child_error || canon_error;',
                    'assign error=local_error || child_error || canon_error || off_ingress_error;')
    def transfer(identity,producer,consumer,signals,anchors,reason):
        return dict(id=identity,producer=producer,consumer=consumer,signals=signals,
            registered_stages=[],control_reconvergence=[],exception=dict(kind='phase_local_control',reason=reason,
                contract_anchors=[dict(source=source,text=text) for source,text in anchors]))
    spec['transfers'] += [
        transfer('B_cold_registered_packet','cold_packet','host_control',
            ['row_data','row_valid','row_response_owner','off_source_planes','source_valid'],
            [(leaf,'row_valid<=row_request && !stop && row_owned;'),
             (leaf,'if(row_request)begin row_response_context<=row_context;row_response_owner<=row_owner;end'),
             (host,'off_source_planes<=off_row_data;')],
            'Cold packet completes exact indexed canonical-word validation before use. RAM row and actual request full56 owner are registered; host captures next edge and checks live owner. No trimming or combinational invented response owner.'),
        transfer('B_profile_binding','cold_packet','setup_profile_banks',
            ['off_saved_reciprocal','off_saved_limit','off_profile_good'],
            [(host,'|| !off_profile_good)local_error<=1;')],
            'Retained setup independently computes reciprocal/limit; exact host constants compared before cold launch. Body loaded is not profile-qualified. No setup hardware-saving claim.'),
        transfer('B_final_packet','warm_control','raw_host_packet',
            ['digit_data','final_owner','digit_row','off_raw_ready','off_boundary_seen','done_q'],
            [(host,'wire capture_fire=final_valid && off_raw_ready && !capture_bad && !safety_error;'),
             (host,"if(raw_rows[c]!=(ROW_W+1)'(ROWS) || !off_boundary_seen[c])local_error<=1;")],
            'Registered carry output goes to fixed-cadence host boundary. External ready must remain high on every occupied row/boundary or sticky fault suppresses completion. Full56 owner/order/row count and final boundary gate one completion fence; finalizer publishes only complete valid raw packet. This is not backpressure or canonical image publication.')]
    spec['blocks']=sorted({t[k] for t in spec['transfers'] for k in ('producer','consumer')})
    spec['exclusions']=[e for e in spec['exclusions'] if 'Lean owner mismatch' not in e.get('reason','')]
    spec['identity'].update(top=b['top'],parameters=params,clock_period_ns=period,seed=seed)
    spec['sources']={'rtl/'+n:p for n,p in b['generated_sha256'].items()}
    spec['settings']=dict(manifest['control_sha256'],**{'manifest.json':chip.sha(encoded(manifest))})
    spec['limitations']+=['R14 input canonical validity and final packet fence replace the old canonical shadow contract; own equivalence not inherited.']
    files={'rtl/'+n:t.encode() for n,t in b['files'].items()};files.update(controls)
    for t in spec['transfers']:
        for a in t.get('exception',{}).get('contract_anchors',[]):
            chip.need(files[a['source']].decode().count(a['text'])==1,'PHYSICAL_ANCHOR:'+t['id'])
        for stage in t['registered_stages']:
            for a in stage['anchors']:chip.need(files[stage['source']].decode().count(a)==1,'PHYSICAL_STAGE:'+t['id'])
    return manifest,files,spec
