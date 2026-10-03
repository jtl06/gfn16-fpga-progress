"""Source-bound protected R13 whole request; FIELD100 job/sources stay frozen."""
import argparse
import copy
import importlib.util
import json
import re
from pathlib import Path
from .stream27_context_storage_combo_physical import ROOT,sha,need,read,encoded
from . import stream27_protected_relay13_bind as source

PARENT=ROOT/'results/throughput-20260929/trackS-c2-protected-field100-physical-v1/physical-12000-v3'
GENERATOR=ROOT/'reference/stream27_protected_relay13_bind.py'
PIN='cbb914bbf82f28a008bd7097910e0719d9d4d51d77b258a7e7a60ebae457e21a'
KWARGS=dict(p=16,contexts=2,enabled=1,inverse_ingress_reg=1,term_join_transport_reg=1,forward_ingress_reg=1)


def build(role,gate):
    role=Path(role).resolve();need(sha(GENERATOR.read_bytes())==PIN,'frozen R13 recipe')
    native=read(role/'manifest.json');small=read(role/'production-bundle.json')
    need(read(role/'global-ticket.json')['id']==gate,'own actual gate ID')
    fullpath=role.parent/'full-normal/production-bundle.json'
    full=read(fullpath) if fullpath.exists() else source.prepare(65536,**KWARGS)
    for b,n in ((small,256),(full,65536)):
        need(b['geometry']['n']==n and len(b['files'])==58,'source58/geometry')
        need(b['source_sha256']['reference/stream27_protected_relay13_bind.py']==PIN,'own recipe lineage')
        need(b['generated_sha256']=={k:sha(v.encode()) for k,v in b['files'].items()},'complete captured map')
        need(not b.get('lean_production') and 'LEAN_PRODUCTION' not in b['parameters'],'protected only')
        need(b['parameters']['CRT_TRANSPORT_REG']==0,'CRT transport OFF')
        need(b['context_protected_relay13']['flags']==source.PRIMARY_FLAGS,'exact relay batch')
    need(all(native['sources']['rtl/'+k]==v for k,v in small['generated_sha256'].items()),'own native source join')
    params=dict(native['build']['parameters'],AW=16)
    need(params==dict(full['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),'compiled parameter join')
    parent=read(PARENT/'project/manifest.json');controls={}
    for name,pin in parent['control_sha256'].items():
        raw=(PARENT/'project'/name).read_bytes();need(sha(raw)==pin,'parent controls '+name);controls[name]=raw
    qsf='\n'.join(x for x in controls['probe.qsf'].decode().splitlines()
        if not x.startswith(('set_global_assignment -name SYSTEMVERILOG_FILE ','set_parameter -name ')))+'\n'
    qsf=qsf.replace(parent['top'],full['top'])
    qsf=re.sub(r'(?m)^set_global_assignment -name SEED \d+$','set_global_assignment -name SEED 1',qsf)
    qsf+=''.join(f'set_parameter -name {k} {v}\n' for k,v in params.items())
    qsf+=''.join('set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+k+'\n' for k in full['files'])
    controls['probe.qsf']=qsf.encode();need(controls['probe.sdc'].decode().count('-period 12.000')==1,'parent period12')
    controls['probe.sdc']=controls['probe.sdc'].replace(b'-period 12.000',b'-period 11.500')
    metadata=copy.deepcopy(full['context_protected_relay13']);metadata.pop('source_edits')
    manifest={k:copy.deepcopy(parent[k]) for k in ('scope','edition','device','compile_processors','address_width',
        'bitstream_generation','allowed_stages','raw_multiplier_parameters','field_parameters','intermediate_snapshots')}
    manifest.update(status='prepared_R13_protected_own_AW8_provisional',label='protected R13; own qualification required',
        seed=1,clock_period_ns=11.5,top=full['top'],geometry=full['geometry'],core_parameters=params,
        source_sha256=full['generated_sha256'],generator_source_sha256=full['source_sha256'],
        control_sha256={k:sha(v) for k,v in controls.items()},native_normal_id=gate,
        native_role_manifest_sha256=sha((role/'manifest.json').read_bytes()),context_protected_relay13=metadata,
        notes=['Own protected58 on immutable FIELD100, three complete field ingress tuples; CRT0/noLEAN/no arithmetic profile change.',
          'Full I8464/F8462/C12561/PW4208/SINK8420; AW8 I218/F198/C217/PW80/SINK156. Cache78/term E4 seeds71..74 and FIFO0/18+q1 literal.',
          'FAST origin0/field report1/arithmetic report2/host1; full56 publication fence/copyN+4, cold acceptance retirement, carry quarantine and fold VALUE tuple retained.',
          '11.5ns Balanced seed1 raw experiment, no clock/area/logic-level promise; field100 and R12 numerical/physical results not inherited.'])
    spec=read(PARENT/'structural-inventory.json');renames={parent['top']:full['top']}
    for old in parent['source_sha256']:
        if old.startswith(('genefer_stream27_shared_warm_aw','genefer_stream27_threefield_carry_aw','genefer_stream27_warm_contexts_aw')):
            new=old[:-3]+'_relay13_v1.sv';need(new in full['files'],'actual graph rename '+old);renames[old[:-3]]=new[:-3]
    def remap(x):
        if isinstance(x,dict):return {k:remap(v) for k,v in x.items()}
        if isinstance(x,list):return [remap(v) for v in x]
        if isinstance(x,str):
            for a,b in renames.items():x=re.sub(r'\b'+re.escape(a)+r'\b',b,x)
        return x
    spec=remap(spec)
    for t in spec['transfers']:
        if t['id']=='carry_boundary_to_fields':
            t['exception']['reason']='Complete automatic correction and feedback q remain literal; three new field ingress tuples add3 to field-relative F/C/I, no CRT edge. FullI8464/F8462/C12561/PW4208/SINK8420/cache78; smallI218. Cold/cache/E4 source and publication fence remain own source-qualified.'
    for f in range(3):
        field='rtl/'+next(n for n in full['files'] if n.startswith('genefer_stream27_shared_warm_aw') and f'_f{f}_' in n)
        for kind,producer,consumer,slot,payload,meta,body,port in (
          ('forward_ingress','digit_frontend','forward','forward_slot_q',['forward_data_q'],['forward_start_q','forward_generation_q'],
            source.FORWARD_DECL,'.in_slot_valid(forward_slot_q && !stop),.frame_start(forward_start_q),.quarantine(transform_quarantine[0]),'),
          ('term_pair','term_join','addB','pair_slot_q',['pair_lhs_q','pair_rhs_q'],['pair_start_q','pair_generation_q'],
            source.relay.PAIR_DECL,'.generation_in(pair_generation_q),.lhs(pair_lhs_q),.rhs(pair_rhs_q),'),
          ('inverse_ingress','square','inverse','inverse_slot_q',['inverse_data_q'],['inverse_start_q','inverse_generation_q'],
            source.relay.INVERSE_DECL,'.generation_in(inverse_generation_q),.live_generation(')):
            a=f'field{f}_{producer}';b=f'field{f}_{consumer}';spec['blocks'] += [a,b]
            spec['transfers'].append(dict(id=f'field{f}_{kind}_transport',producer=a,consumer=b,
                signals=[slot]+payload+meta,registered_stages=[dict(id=f'field{f}_{kind}_q',owner=f'field{f}',edge=0,kind='flop',source=field,
                    payload=payload,valid=slot,metadata=meta,anchors=[body.strip()],alignment='same_accepted_edge')],
                control_reconvergence=[],exception=dict(kind='phase_local_control',reason='One coherent data/full25owner/start/occupied tuple register at this field boundary; FAST masks origin and consumer. Reset clears valid/start, payload eligibility never inferred from invalid contents. Original raw joins, fullowner checks, accepted protocol FAST and lease retirement remain origin-local. No CRT or inner-BF stage and no fault report authority added.',
                    contract_anchors=[dict(source=field,text=port)])))
    for e in spec['exclusions']:
        if e.get('reason','').startswith('No R11 transport boundary exists'):
            e['reason']='R13 explicitly adds three ingress boundaries per field, not the R11 graph/watchdog/CRT stage. FinalGS7, termE4, full protected checks and field100 FAST/fold/carry policies remain literal. No netlist completeness or logic-level cap proof.'
    spec['identity'].update(top=full['top'],parameters=params,clock_period_ns=11.5,seed=1)
    spec['sources']={'rtl/'+n:p for n,p in full['generated_sha256'].items()}
    spec['settings']=dict(manifest['control_sha256'],**{'manifest.json':sha(encoded(manifest))})
    files={'rtl/'+n:t.encode() for n,t in full['files'].items()};files.update(controls)
    proof=dict(schema='fit-provisional-aw8-geometry-v1',generator=dict(path=str(GENERATOR),sha256=PIN),kwargs=KWARGS,native_n=256,fit_n=65536)
    return manifest,files,spec,proof


def prepare(output,role,gate):
    out=Path(output).resolve();need(out.is_relative_to(ROOT) and not out.exists(),'fresh R13 output')
    m,files,spec,proof=build(role,gate)
    for t in spec['transfers']:
        for a in t.get('exception',{}).get('contract_anchors',[]):
            need(a['source'] in files and files[a['source']].decode().count(a['text'])==1,'R13 anchor '+t['id']+repr(a))
        for stage in t['registered_stages']:
            for a in stage['anchors']:need(files[stage['source']].decode().count(a)==1,'R13 stage anchor '+t['id'])
    for name,raw in files.items():
        p=out/'project'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    (out/'project/manifest.json').write_bytes(encoded(m))
    for name,obj in [('structural-inventory.json',spec),('provisional-geometry.json',proof)]: (out/name).write_bytes(encoded(obj))
    loader=importlib.util.spec_from_file_location('r13_guard',ROOT/'tools/prefit_structural_guard_v1.py')
    guard=importlib.util.module_from_spec(loader);loader.loader.exec_module(guard)
    result=guard.source_inventory(out/'project',spec);need(not result['findings'],'R13 structural findings '+str(result['findings']))
    return dict(project=str(out/'project'),source_count=58,crossings=len(spec['transfers']),structural_sha256=sha(encoded(spec)),provisional_sha256=sha(encoded(proof)),source_findings=result['findings'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--native-role',required=True,type=Path);p.add_argument('--native-gate',required=True);a=p.parse_args()
    print(json.dumps(prepare(a.output,a.native_role,a.native_gate),indent=2))
