"""Own protected FIELD100 whole source inventory; no shared-source edits."""
import argparse
import copy
import importlib.util
import json
import re
from pathlib import Path
from .stream27_context_storage_combo_physical import ROOT,sha,need,read,encoded
from . import stream27_protected_field100_bind as source

PARENT=ROOT/'results/throughput-20260929/trackS-c2-feedback12-protected-physical-v1/physical-12000-v1'
PRE_TRANSPORT=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-timing10-physical-v1/physical-13000-v1'
GENERATOR=ROOT/'reference/stream27_protected_field100_bind.py'
PIN='84b14c2ce04d37aec04d7eadb42eec04a9e34c0d1412ed927b8e1a0f60757ebd'
KWARGS=dict(p=16,contexts=2,enabled=1,**{k.lower():1 for k in source.FLAGS})


def build(role,gate):
    role=Path(role).resolve();need(sha(GENERATOR.read_bytes())==PIN,'frozen FIELD100 recipe')
    native=read(role/'manifest.json');small=read(role/'production-bundle.json')
    need(read(role/'global-ticket.json')['id']==gate,'actual own gate ID')
    fullpath=role.parent/'full-normal-v2/production-bundle.json'
    full=read(fullpath) if fullpath.exists() else source.prepare(65536,**KWARGS)
    for b,n in ((small,256),(full,65536)):
        need(b['geometry']['n']==n and len(b['files'])==58,'source58/geometry')
        need(b['source_sha256']['reference/stream27_protected_field100_bind.py']==PIN,'recipe lineage')
        need(b['generated_sha256']=={k:sha(v.encode()) for k,v in b['files'].items()},'complete exact map')
        need(not b.get('lean_production') and 'LEAN_PRODUCTION' not in b['parameters'],'protected only')
        need(not any(k in b['parameters'] for k in ('CRT_TRANSPORT_REG','INVERSE_INGRESS_REG','TERM_JOIN_TRANSPORT_REG')),'no R11 transports')
        need(b['context_protected_field100']['flags']==source.FLAGS,'complete selected batch')
    need(all(native['sources']['rtl/'+k]==v for k,v in small['generated_sha256'].items()),'own native source join')
    params=dict(native['build']['parameters'],AW=16)
    need(params==dict(full['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),'compiled parameter join')
    parent=read(PARENT/'project/manifest.json');controls={}
    for name,pin in parent['control_sha256'].items():
        raw=(PARENT/'project'/name).read_bytes();need(sha(raw)==pin,'parent control '+name);controls[name]=raw
    qsf='\n'.join(x for x in controls['probe.qsf'].decode().splitlines()
        if not x.startswith(('set_global_assignment -name SYSTEMVERILOG_FILE ','set_parameter -name ')))+'\n'
    qsf=qsf.replace(parent['top'],full['top'])
    qsf=re.sub(r'(?m)^set_global_assignment -name SEED \d+$','set_global_assignment -name SEED 2',qsf)
    qsf+=''.join(f'set_parameter -name {k} {v}\n' for k,v in params.items())
    qsf+=''.join('set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+k+'\n' for k in full['files'])
    controls['probe.qsf']=qsf.encode()
    metadata=copy.deepcopy(full['context_protected_field100']);metadata.pop('source_edits')
    manifest={k:copy.deepcopy(parent[k]) for k in ('scope','edition','device','compile_processors','address_width',
        'bitstream_generation','allowed_stages','raw_multiplier_parameters','field_parameters','intermediate_snapshots')}
    manifest.update(status='prepared_FIELD100_protected_own_AW8_provisional',label='protected FIELD100; own qualification required',
        seed=2,clock_period_ns=12.0,top=full['top'],geometry=full['geometry'],core_parameters=params,
        source_sha256=full['generated_sha256'],generator_source_sha256=full['source_sha256'],
        control_sha256={k:sha(v) for k,v in controls.items()},native_normal_id=gate,
        native_role_manifest_sha256=sha((role/'manifest.json').read_bytes()),context_protected_field100=metadata,
        notes=['Own protected58; R11 three transports absent, not a settings-only R12 baseline.',
        'Protocol original accepted sticky is immediate FAST. Report/copies lag1; arithmetic report lag2, host1. Same-NBA public masks retained.',
        'Sixteen carry receiving quarantine registers allow private processing1edge; numeric pipeline tails may be longer. No public faulted eligibility/publication permitted.',
        'Canonical fold tuple captures on existing VALUE edge; no added healthy external edge. FullI8461/F8459/C12558/cache78; copyN+4/PUB1.',
        '12ns Balanced seed2 experiment under actual native/source/resource guards; no logic-level cap, clock, density or promotion claim.'])
    spec=read(PARENT/'structural-inventory.json');oldspec=read(PRE_TRANSPORT/'structural-inventory.json')
    restore={t['id']:t for t in oldspec['transfers'] if t['id']=='profiles_to_carry' or re.fullmatch(r'field[012]_to_CRT',t['id'])}
    spec['transfers']=[copy.deepcopy(restore.get(t['id'],t)) for t in spec['transfers']
        if not re.fullmatch(r'field[012]_(term_pair|inverse_ingress)_transport',t['id'])]
    spec['blocks']=[x for x in spec['blocks'] if not re.fullmatch(r'field[012]_(term_join|addB|square|inverse)',x)]
    renames={parent['top']:full['top']}
    for names in (parent['source_sha256'],read(PRE_TRANSPORT/'project/manifest.json')['source_sha256']):
        for old in names:
            for prefix in ('genefer_stream27_shared_warm_aw16_p16_f0_','genefer_stream27_shared_warm_aw16_p16_f1_',
                'genefer_stream27_shared_warm_aw16_p16_f2_','genefer_stream27_threefield_carry_aw','genefer_stream27_warm_contexts_aw'):
                if old.startswith(prefix):
                    new=next(n for n in full['files'] if n.startswith(prefix));renames[old[:-3]]=new[:-3]
    renames[source.fold.OLD]=source.fold.NEW
    replacements={
        'if(crt_transport_slot)begin crt_tag[0]<=crt_transport_tag;crt_double[0]<=crt_transport_double;end':
          'if(joined)begin crt_tag[0]<={field_context[0],field_epoch[0],field_generation[0],field_row[0]};crt_double[0]<=bank_double[bank];end',
        'if(fault_pending)out_error<=1;':'if((|field_error) || local_fault_q)out_error<=1;',
        'assign error_barrier=out_error || (|field_error) || local_fault_q;':'assign error_barrier=out_error || (|field_fast) || local_fault_q;',
        'if('+source.SETTER+')\n    controller_error<=1;':'controller_error<=out_error_fast;',
    }
    def remap(x):
        if isinstance(x,dict):return {k:remap(v) for k,v in x.items()}
        if isinstance(x,list):return [remap(v) for v in x]
        if isinstance(x,str):
            for a,b in renames.items():x=re.sub(r'\b'+re.escape(a)+r'\b',b,x)
            for a,b in replacements.items():x=x.replace(a,b)
        return x
    spec=remap(spec)
    arith='rtl/'+next(n for n in full['files'] if n.startswith('genefer_stream27_threefield_carry_aw'))
    protocol='rtl/'+source.NEW_PROTOCOL+'.sv'
    for t in spec['transfers']:
        if t['id']=='carry_boundary_to_fields':
            t['exception']['reason']='Complete automatic c0/c1/context/epoch/generation q and paired feedback q add1 to interval on protected timing10 (no R11 transports). Cold correction unchanged; fullI8461/F8459/C12558/SINK8417/cache78; copyN+4/PUB1.'
        if t['id']=='prospective_fault_to_sticky_origin':
            t['signals']+=['field_fast','out_error_fast','transform_quarantine']
            t['exception']['reason']='Protocol original accepted sticky is FAST on origin edge; field report/copies sample it nextedge, arithmetic registered field report is two edges after FAST, host report one further. Local arithmetic raw-fault capture remains distinct. Public masks use FAST-derived error_barrier/safety_error in same NBA; delayed private quarantine is never public authority. Binary induction assumes self-quarantine and delayed-copy implication; no arbitrary FF/XZ immunity.'
        if t['id']=='shadows_to_canonical_scratch':
            canon='rtl/'+source.fold.NEW+'.sv'
            t['exception']['reason']+=' Fold/range/remainder payload captured coherently on existing VALUE edge, PROCESS consumes it; range/priority and public edge unchanged.'
            t['exception']['contract_anchors'] += [dict(source=canon,text=x) for x in (
                'fold_q_payload<=fold_q_pre;fold_remainder_payload<=fold_remainder_pre;',
                'fold_range_payload<=fold_range_pre;', 'else if(fold_range_payload ||')]
    for f in range(3):
        field='rtl/'+next(n for n in full['files'] if n.startswith('genefer_stream27_shared_warm_aw') and f'_f{f}_' in n)
        spec['blocks'] += [f'field{f}_protocol_origin',f'field{f}_report_quarantine']
        spec['transfers'].append(dict(id=f'field{f}_FAST_to_report_and_quarantine',producer=f'field{f}_protocol_origin',consumer=f'field{f}_report_quarantine',
            signals=['protocol_error','out_error_fast','controller_error','transform_quarantine'],
            registered_stages=[dict(id=f'field{f}_accepted_protocol_FAST',owner=f'field{f}',edge=0,kind='flop',source=protocol,
                payload=['out_error'],valid='out_error',metadata=[],anchors=['out_error<=out_error || (|fault_report_copies) || bad || external_fault_pending;'],alignment='same_accepted_edge'),
                dict(id=f'field{f}_delayed_report',owner=f'field{f}',edge=1,kind='flop',source=field,
                payload=['controller_error'],valid='controller_error',metadata=[],anchors=['controller_error<=out_error_fast;'],alignment='same_accepted_edge')],
            control_reconvergence=[],exception=dict(kind='phase_local_control',
                reason='Report and CT/GS quarantine copies are parallel E1 branches of accepted FAST E0, not new origin authority. Protocol self-quarantine equality and delayed-copy implication are asserted; tables/leases/eligibility use immediate stop. Private canceled tails may run; no public faulted result allowed.',
                contract_anchors=[dict(source=field,text=x) for x in ('wire stop=out_error_fast;','assign out_error_fast=protocol_error;',
                    '.fault_set(out_error_fast),','.quarantine(stop),.fault_report_copies(transform_quarantine),.external_fault_pending(')])))
    spec['transfers'].append(dict(id='FAST_barrier_to_sixteen_carry_receivers',producer='arithmetic_control',consumer='carry',
        signals=['error_barrier','carry_quarantine_q','joined','join_start','doubled_valid'],
        registered_stages=[dict(id='per_carry_quarantine_receive',owner='carry',edge=0,kind='flop',source=arith,
            payload=['carry_quarantine_q'],valid='carry_quarantine_q',metadata=[],
            anchors=['else carry_quarantine_q<=carry_quarantine_q || error_barrier;'],alignment='same_accepted_edge')],
        control_reconvergence=[],exception=dict(kind='phase_local_control',
            reason='Sixteen generated local sticky receiver flops sample the same accepted FAST-derived barrier. Raw tuple/join/busy/lease retirement checks remain origin-local. Private carry may accept/process one later edge; public valid/eligible/accept/publication remains immediately masked. Pipeline tail length is not claimed bounded by one edge.',
            contract_anchors=[dict(source=arith,text=x) for x in ('for(genvar b=0;b<P;b=b+1)begin: arithmetic',
                '.begin_block(joined && join_start && !carry_quarantine_q),', '.in_valid(doubled_valid && !carry_quarantine_q),',
                'assign error_barrier=out_error || (|field_fast) || local_fault_q;')])))
    spec['exclusions']=[e for e in spec['exclusions'] if not any(x in e.get('reason','') for x in ('Six explicit','Six internal','R12 field C0'))]
    spec['exclusions'].append(dict(kind='inside_single_macroblock',reason='No R11 transport boundary exists in this source. Final GS7, raw term join, exact uint32 field-C0 direct identity and healthy feedback/correction q retain source own calendar. FAST/report semantic changes explicitly inventoried; no netlist completeness or <=6-level proof.',endpoints=['field CT/GS','raw term/addB','raw square/inverse','field C0 admission']))
    spec['identity'].update(top=full['top'],parameters=params,clock_period_ns=12.0,seed=2)
    spec['sources']={'rtl/'+n:p for n,p in full['generated_sha256'].items()}
    spec['settings']=dict(manifest['control_sha256'],**{'manifest.json':sha(encoded(manifest))})
    files={'rtl/'+n:t.encode() for n,t in full['files'].items()};files.update(controls)
    proof=dict(schema='fit-provisional-aw8-geometry-v1',generator=dict(path=str(GENERATOR),sha256=PIN),kwargs=KWARGS,native_n=256,fit_n=65536)
    return manifest,files,spec,proof


def prepare(output,role,gate):
    out=Path(output).resolve();need(out.is_relative_to(ROOT) and not out.exists(),'fresh FIELD100 output')
    m,files,spec,proof=build(role,gate)
    for t in spec['transfers']:
        for a in t.get('exception',{}).get('contract_anchors',[]):
            need(a['source'] in files and files[a['source']].decode().count(a['text'])==1,'FIELD100 anchor '+t['id']+repr(a))
    for name,raw in files.items():
        p=out/'project'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    (out/'project/manifest.json').write_bytes(encoded(m))
    for name,obj in [('structural-inventory.json',spec),('provisional-geometry.json',proof)]: (out/name).write_bytes(encoded(obj))
    loader=importlib.util.spec_from_file_location('field100_guard',ROOT/'tools/prefit_structural_guard_v1.py')
    guard=importlib.util.module_from_spec(loader);loader.loader.exec_module(guard)
    result=guard.source_inventory(out/'project',spec);need(not result['findings'],'FIELD100 structural findings '+str(result['findings']))
    return dict(project=str(out/'project'),source_count=58,crossings=len(spec['transfers']),structural_sha256=sha(encoded(spec)),provisional_sha256=sha(encoded(proof)),source_findings=result['findings'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--native-role',required=True,type=Path);p.add_argument('--native-gate',required=True);a=p.parse_args()
    print(json.dumps(prepare(a.output,a.native_role,a.native_gate),indent=2))
