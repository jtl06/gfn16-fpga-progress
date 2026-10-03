"""R11 own-source physical inventory for three complete transport boundaries."""
import argparse
import copy
import importlib.util
import json
import re
from pathlib import Path
from .stream27_context_storage_combo_physical import ROOT,sha,need,read,encoded
from . import stream27_context_storage_combo_transport11_bind as source

PARENT=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-timing10-physical-v1/physical-13000-v1'
GENERATOR=ROOT/'reference/stream27_context_storage_combo_transport11_source_v2.py'
PIN='792851152b0a637a83885a72fb33a972601547470ae377723228411a188c2262'
LABEL='lean build; host GL assumed (unimplemented)'
KWARGS=dict(p=16,contexts=2,enabled=1,lean_production=1,crt_transport_reg=1,
            inverse_ingress_reg=1,term_join_transport_reg=1,lean_progress_watchdog=1)


def build(role,gate):
    role=Path(role).resolve();need(sha(GENERATOR.read_bytes())==PIN,'frozen R11 closure recipe')
    native=read(role/'manifest.json');small=read(role/'production-bundle.json')
    full=read(role.parent/'full-normal-v2/production-bundle.json')
    for b,n in ((small,256),(full,65536)):
        need(b['geometry']['n']==n and len(b['files'])==58,'own source58/geometry')
        need(b['source_sha256']['reference/stream27_context_storage_combo_transport11_source_v2.py']==PIN,'entrypoint pin')
        need(b['generated_sha256']=={k:sha(v.encode()) for k,v in b['files'].items()},'complete map')
        need(b['lean_production']['label']==LABEL and b['context_transport11']['ntt_compare_reg']==0,'lean/three-only scope')
    need(all(native['sources']['rtl/'+k]==v for k,v in small['generated_sha256'].items()),'own native source')
    params=dict(native['build']['parameters'],AW=16)
    need(params==dict(full['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),'own compiled parameters')
    parent=read(PARENT/'project/manifest.json');controls={}
    for name,pin in parent['control_sha256'].items():
        raw=(PARENT/'project'/name).read_bytes();need(sha(raw)==pin,'immutable R10 control '+name);controls[name]=raw
    qsf='\n'.join(line for line in controls['probe.qsf'].decode().splitlines()
         if not line.startswith(('set_global_assignment -name SYSTEMVERILOG_FILE ','set_parameter -name ')))+'\n'
    qsf=qsf.replace(parent['top'],full['top'])
    qsf+=''.join(f'set_parameter -name {k} {v}\n' for k,v in params.items())
    qsf+=''.join('set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+k+'\n' for k in full['files'])
    controls['probe.qsf']=qsf.encode()
    sdc=controls['probe.sdc'].decode();need(sdc.count('-period 13.000')==1,'parent period')
    controls['probe.sdc']=sdc.replace('-period 13.000','-period 12.000').encode()
    metadata=copy.deepcopy(full['context_transport11']);metadata.pop('source_edits');metadata.pop('host_calendar_edits')
    manifest={k:copy.deepcopy(parent[k]) for k in ('scope','edition','device','compile_processors','seed',
        'address_width','bitstream_generation','allowed_stages','raw_multiplier_parameters','field_parameters','intermediate_snapshots')}
    manifest.update(status='prepared_R11_lean_transport_own_AW8_provisional',label=LABEL,top=full['top'],
        clock_period_ns=12.0,geometry=full['geometry'],core_parameters=params,
        source_sha256=full['generated_sha256'],generator_source_sha256=full['source_sha256'],
        control_sha256={k:sha(v) for k,v in controls.items()},native_normal_id=gate,
        native_role_manifest_sha256=sha((role/'manifest.json').read_bytes()),context_transport11=metadata,
        lean_watchdog_warm_progress=full['lean_watchdog_warm_progress'],
        notes=[LABEL,'Fresh R11 source58 and own quicknormal; protected/twin error immunity and old clocks not inherited.',
          'Three coherent boundaries: paired term/addB and square/GS add2field edges, joined CRT/profile adds1; fullI8463/AW8I217.',
          'Raw join checks/retirement remain origin-local; raw carry BEGIN checks busy plus queued reservation. WholeN+4 publication fence retained.',
          '12ns raw experiment, not clock or density GO. Declared transport FF bits are not mapped area or paid for by tag estimates.',
          'Optional NTT compare not implemented/enabled; watchdog counts real child_completed progress, not BUSY/timer. GL/rollback unimplemented.'])
    spec=read(PARENT/'structural-inventory.json')
    old_names=parent['source_sha256'];new_names=full['files']
    renames={parent['top']:full['top']}
    for old in old_names:
        if old.startswith(('genefer_stream27_shared_warm_aw','genefer_stream27_threefield_carry_aw','genefer_stream27_warm_contexts_aw')):
            new=old[:-3]+'_transport11_v1.sv';need(new in new_names,'actual graph rename '+old);renames[old[:-3]]=new[:-3]
    replacements={
       '.base(profile_base[field_context[0]]),.reciprocal(profile_reciprocal[field_context[0]]),.coefficient_limit(profile_limit[field_context[0]]),':
         '.base(crt_transport_base),.reciprocal(crt_transport_reciprocal),.coefficient_limit(crt_transport_limit),',
       'if(joined)begin crt_tag[0]<={field_context[0],field_epoch[0],field_generation[0],field_row[0]};crt_double[0]<=bank_double[bank];end':
         'if(crt_transport_slot)begin crt_tag[0]<=crt_transport_tag;crt_double[0]<=crt_transport_double;end'}
    def remap(x):
        if isinstance(x,dict):return {k:remap(v) for k,v in x.items()}
        if isinstance(x,list):return [remap(v) for v in x]
        if isinstance(x,str):
            for a,b in renames.items():x=re.sub(r'\b'+re.escape(a)+r'\b',b,x)
            return replacements.get(x,x)
        return x
    spec=remap(spec)
    arith='rtl/'+next(n for n in new_names if n.startswith('genefer_stream27_threefield_carry_aw'))
    for t in spec['transfers']:
        if re.fullmatch(r'field[012]_to_CRT',t['id']):
            f=int(t['id'][5]);t['signals']+=['crt_transport_slot','crt_transport_start','crt_transport_tag','crt_transport_double']
            t['registered_stages']=[dict(id=f'joined_CRT_transport_f{f}',owner='arithmetic_control',edge=0,
              kind='flop',source=arith,payload=[f'crt_transport_data[{f}]'],valid='crt_transport_slot',
              metadata=['crt_transport_start','crt_transport_tag','crt_transport_double'],
              anchors=['crt_transport_slot<=joined && !error_barrier;',
               'for(int f=0;f<3;f=f+1)crt_transport_data[f]<=field_data[f];',
               'crt_transport_tag<={field_context[0],field_epoch[0],field_generation[0],field_row[0]};',
               'crt_transport_double<=bank_double[bank];'],alignment='same_accepted_edge')]
            t['exception']['reason']='Original raw three-field join/owner/lease retirement remains at origin. Complete residues+context/epoch/generation/row/start/double captured atE0, CRT consumesE1. Physical lane order explicit. Tag pipeline advances same transport token; no data-only delay.'
            t['exception']['contract_anchors'] += [dict(source=arith,text=source.CRT_DECL.strip()),
                dict(source=arith,text='.in_valid(crt_transport_slot && !error_barrier),')]
        if t['id']=='profiles_to_carry':
            t['signals']+=['crt_transport_base','crt_transport_reciprocal','crt_transport_limit','crt_transport_start','raw_begin_carry']
            t['registered_stages']=[dict(id='joined_carry_profile_transport',owner='arithmetic_control',edge=0,
                kind='flop',source=arith,payload=['crt_transport_base','crt_transport_reciprocal','crt_transport_limit'],
                valid='crt_transport_start',metadata=['crt_transport_tag'],anchors=[
                 'crt_transport_base<=profile_base[field_context[0]];',
                 'crt_transport_reciprocal<=profile_reciprocal[field_context[0]];',
                 'crt_transport_limit<=profile_limit[field_context[0]];'],alignment='same_accepted_edge')]
            t['exception']['reason']='Qualified context profile is captured with joined FIRST, held for carry BEGIN nextedge. Raw BEGIN still checks busy including queued BEGIN reservation; original accepted setup/profile domain unchanged.'
            t['exception']['contract_anchors'] += [dict(source=arith,text=x) for x in (
                'if(raw_begin_carry && ((|lane_busy) || (crt_transport_slot && crt_transport_start)))carry_bad=1;',
                'if(begin_carry && (|lane_busy))carry_bad=1;',
                'wire begin_carry=crt_transport_slot && crt_transport_start && !error_barrier;')]
        if t['id']=='carry_boundary_to_fields':
            t['exception']['reason']='Boundary/cache78 stays exact. Added pair-term and inverse ingress add2 to field SINK; CRT transport adds1 to carry/digit/fullI. FullI8463/AW8I217, F8462/C12561; no silent old-calendar inheritance.'
    for f in range(3):
        field='rtl/'+next(n for n in new_names if n.startswith('genefer_stream27_shared_warm_aw') and f'_f{f}_' in n)
        for kind,producer,consumer,slot,payload,meta,body,port in (
          ('term_pair','term_join','addB','pair_slot_q',['pair_lhs_q','pair_rhs_q'],['pair_start_q','pair_generation_q'],
           source.PAIR_DECL,'.generation_in(pair_generation_q),.lhs(pair_lhs_q),.rhs(pair_rhs_q),'),
          ('inverse_ingress','square','inverse','inverse_slot_q',['inverse_data_q'],['inverse_start_q','inverse_generation_q'],
           source.INVERSE_DECL,'.generation_in(inverse_generation_q),.live_generation(')):
            a=f'field{f}_{producer}';b=f'field{f}_{consumer}';spec['blocks'] += [a,b]
            spec['transfers'].append(dict(id=f'field{f}_{kind}_transport',producer=a,consumer=b,
              signals=[slot]+payload+meta,registered_stages=[dict(id=f'field{f}_{kind}_q',owner=f'field{f}',edge=0,
               kind='flop',source=field,payload=payload,valid=slot,metadata=meta,anchors=[body.strip()],alignment='same_accepted_edge')],
              control_reconvergence=[],exception=dict(kind='phase_local_control',
               reason='Explicit narrow field subblock boundary, not another whole-field macroblock delay. Payload/full25tag/start/valid captured together; stop masks sampling. Original raw join/cadence/fault authority and four-edge term recurrence unchanged. Consumer takes tuple nextedge.',
               contract_anchors=[dict(source=field,text=port)])))
    spec['exclusions'].append(dict(kind='inside_single_macroblock',
       reason='Six explicit internal-field transport transfers refine prior opaque field scope; three field→CRT tuples refine existing crossings. Their registers are not counted twice. Source-declared inventory, not netlist completeness or density/clock proof. Lean watchdog observes real completion counters, not per-context fault immunity.',
       endpoints=['pairterm/addB','square/GS','joinedCRT/profile','host lean_completed_seen']))
    spec['identity'].update(top=full['top'],parameters=params,clock_period_ns=12.0)
    spec['sources']={'rtl/'+n:pin for n,pin in full['generated_sha256'].items()}
    spec['settings']=dict(manifest['control_sha256'],**{'manifest.json':sha(encoded(manifest))})
    files={'rtl/'+n:t.encode() for n,t in full['files'].items()};files.update(controls)
    proof=dict(schema='fit-provisional-aw8-geometry-v1',generator=dict(path=str(GENERATOR),sha256=PIN),
       kwargs=KWARGS,native_n=256,fit_n=65536)
    return manifest,files,spec,proof


def prepare(output,role,gate):
    out=Path(output).resolve();need(out.is_relative_to(ROOT) and not out.exists(),'fresh R11 output')
    manifest,files,spec,proof=build(role,gate)
    for name,raw in files.items():
        p=out/'project'/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    (out/'project/manifest.json').write_bytes(encoded(manifest))
    for name,obj in [('structural-inventory.json',spec),('provisional-geometry.json',proof)]:
        (out/name).write_bytes(encoded(obj))
    for t in spec['transfers']:
        for a in t.get('exception',{}).get('contract_anchors',[]):
            need(a['source'] in files and files[a['source']].decode().count(a['text'])==1,'R11 anchor '+t['id']+': '+repr(a))
    loader=importlib.util.spec_from_file_location('r11_guard',ROOT/'tools/prefit_structural_guard_v1.py')
    guard=importlib.util.module_from_spec(loader);loader.loader.exec_module(guard)
    result=guard.source_inventory(out/'project',spec);need(not result['findings'],'R11 structural findings')
    return dict(project=str(out/'project'),source_count=58,crossings=len(spec['transfers']),
       structural_sha256=sha(encoded(spec)),provisional_sha256=sha(encoded(proof)),source_findings=result['findings'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path)
    p.add_argument('--native-role',required=True,type=Path);p.add_argument('--native-gate',required=True);a=p.parse_args()
    print(json.dumps(prepare(a.output,a.native_role,a.native_gate),indent=2))
