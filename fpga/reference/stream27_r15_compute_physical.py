"""Private R15 compute-only source/inventory emission; never shared RTL or launch."""
import argparse
import copy
import importlib.util
import json
import re
from pathlib import Path
from .stream27_context_storage_combo_physical import ROOT,sha,need,read,encoded

PARENT=ROOT/'results/throughput-20260929/trackS-c2-protected-field100-physical-v1/physical-12000-v3'
GENERATOR=ROOT/'reference/stream27_r15_all_bind.py'
PIN='7bf49d27c712d9a093b5f92d07f791d946ef0ac7bd526bb72186d4e8fac59099'
FLAGS=dict(FIXED_SCHEDULE=1,LEAN_BUILD=1,PROGRESS_WATCHDOG=1,STORAGE_TO_RAM=1,DIRECT_COLD=0,PCIE_SHELL=0)
KWARGS=dict(p=16,contexts=2,**{k.lower():v for k,v in FLAGS.items()})
GATE='s4-p16-c2-r15-compute-aw8-normal-q1-v1'


def build(role):
    role=Path(role).resolve();need(sha(GENERATOR.read_bytes())==PIN,'R15 frozen generator')
    native=read(role/'manifest.json');small=read(role/'production-bundle.json')
    full=read(role.parent/'full-normal/production-bundle.json')
    for b,n in ((small,256),(full,65536)):
        need(b['geometry']['n']==n and len(b['files'])==60,'R15 own geometry60')
        need(b['r15_all']['flags']==FLAGS and b['source_sha256']['reference/stream27_r15_all_bind.py']==PIN,'R15 flags/recipe')
        need(b['generated_sha256']=={n:sha(t.encode()) for n,t in b['files'].items()},'R15 exact production map')
        need(all(b['parameters'][k]==v for k,v in FLAGS.items()),'R15 no shell/lean mode identity')
    need(all(native['sources']['rtl/'+n]==p for n,p in small['generated_sha256'].items()),'R15 native role exact60')
    params=dict(native['build']['parameters'],AW=16)
    need(params==dict(full['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),'R15 actual compiled epochs/params')
    parent=read(PARENT/'project/manifest.json');spec=read(PARENT/'structural-inventory.json')
    controls={}
    for n,p in parent['control_sha256'].items():
        raw=(PARENT/'project'/n).read_bytes();need(sha(raw)==p,'frozen parent controls');controls[n]=raw
    qsf='\n'.join(s for s in controls['probe.qsf'].decode().splitlines()
                  if not s.startswith(('set_global_assignment -name SYSTEMVERILOG_FILE ','set_parameter -name ')))+'\n'
    qsf=qsf.replace(parent['top'],full['top'])
    qsf=re.sub(r'(?m)^set_global_assignment -name SEED \d+$','set_global_assignment -name SEED 1',qsf)
    qsf=re.sub(r'(?m)^set_global_assignment -name NUM_PARALLEL_PROCESSORS \d+$','set_global_assignment -name NUM_PARALLEL_PROCESSORS 16',qsf)
    qsf+=''.join(f'set_parameter -name {k} {v}\n' for k,v in params.items())
    qsf+=''.join('set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+n+'\n' for n in full['files'])
    controls['probe.qsf']=qsf.encode()
    manifest={k:copy.deepcopy(parent[k]) for k in ('scope','edition','device','address_width','bitstream_generation',
        'allowed_stages','raw_multiplier_parameters','field_parameters','intermediate_snapshots')}
    manifest.update(status='prepared_R15_compute_only_own_normal_pending',label='lean build; host GL assumed (unimplemented); no PCIe shell',
        seed=1,clock_period_ns=12.0,compile_processors=16,top=full['top'],geometry=full['geometry'],core_parameters=params,
        source_sha256=full['generated_sha256'],generator_source_sha256=full['source_sha256'],
        control_sha256={n:sha(raw) for n,raw in controls.items()},native_normal_id=GATE,
        native_role_manifest_sha256=sha((role/'manifest.json').read_bytes()),r15_flags=FLAGS,
        notes=['Fixed/lean/watch/numeric RAM ON; direct cold and PCIe OFF. No healthy latency delta versus own FIELD100 geometry.',
               'Preserved functional FAST/framing/owner/retirement, removed optional comm comparison/child numeric report aggregation. Protected fault coverage is not inherited.',
               'Completed-square per-context watchdog; no peer-progress reset, no in-flight pause by missing descriptor.',
               'Three CRT numeric delays mapped via ring8 model only; actual RAM/ALM/LAB and clock unmeasured.',
               '12ns Balanced seed1 Azure16physical/64GiB is an experiment, not a timing or resource result.'])
    # Rebind source anchors through the exact recorded additive text changes.
    mappings=[];edits=[]
    for meta in (full['r15_fixed_schedule'],full['r15_lean_watchdog']):
        mapping=dict(meta.get('module_mapping',{}))
        for n,row in meta['modified'].items():
            mapping[row['parent'][:-3]]=n[:-3]
            edits.extend(row['edits'])
            mapping.update(row.get('module_mapping',{}))
        mappings.append(mapping)
    last=full['r15_lean_watchdog']['modified']
    host_before=next(n[:-3] for n in last if n.startswith('genefer_stream27_host_contexts_'))
    mappings.append({host_before:full['top']})
    anchor_changes={
      'r1_pipe[0]<=r1[26:0];r2_input<=r2[26:0];r3_input<=r3[26:0];':'r1_stage0<=r1[26:0];r2_input<=r2[26:0];r3_input<=r3[26:0];',
      'wire auto_correction=boundary_valid && feedback_enabled[boundary_context] && !local_error;':'wire auto_correction=(|r15_correction) && !local_error;',
      'if((|field_error) || local_fault_q)out_error<=1;':'if(local_fault_q)out_error<=1;',
      'assign safety_error=local_error || child_error_barrier || canon_error;':'assign safety_error=local_error || child_error_barrier || canon_error || (|r15_watch_error);',
      'assign error=local_error || child_error || canon_error;':'assign error=local_error || child_error || canon_error || (|r15_watch_error);'}
    def remap(v):
        if isinstance(v,dict):return {k:remap(x) for k,x in v.items()}
        if isinstance(v,list):return [remap(x) for x in v]
        if not isinstance(v,str):return v
        for mapping in mappings:
            for a,b in mapping.items():v=re.sub(r'\b'+re.escape(a)+r'\b',b,v)
        for a,b in edits:v=v.replace(a,b)
        for a,b in anchor_changes.items():v=v.replace(a,b)
        return v
    spec=remap(spec)
    for t in spec['transfers']:
        if t['id']=='prospective_fault_to_sticky_origin':
            t['exception']['reason']+=' R15 LEAN: optional child numeric reports/lane report aggregation are absent; functional FAST, join/admission and descriptor/calendar authority remain. This is NOT protected fault equivalence.'
        if '_FAST_to_report_and_quarantine' in t['id']:
            t['exception']['reason']+=' R15 LEAN field out_error is tied low: report FF source may be optimized away; only actual FAST/quarantine functional branches are asserted, not a fitted report path.'
    host='rtl/'+full['top']+'.sv'
    warm='rtl/'+next(n for n in full['files'] if n.startswith('genefer_stream27_warm_contexts_aw'))
    watch='rtl/genefer_stream27_r15_progress_watchdog_v1.sv'
    spec['blocks'].append('context_progress_watchdog')
    spec['transfers'].append(dict(id='context_completion_to_watchdog',producer='warm_control',consumer='context_progress_watchdog',
        signals=['child_started','child_completed','r15_watch_demand','r15_watch_aux','r15_watch_error'],
        registered_stages=[dict(id='per_context_completed_observer',owner='context_progress_watchdog',edge=0,kind='flop',source=watch,
            payload=['completed_seen','age'],valid='demand',metadata=['new_job','active','stop'],
            anchors=["completed_seen[c]<=new_job[c] ? 32'd0 : completed[c*32+:32];"],alignment='same_accepted_edge')],
        control_reconvergence=[],exception=dict(kind='phase_local_control',
            reason='Independent per-context completion and context-owned auxiliary progress observe liveness, not arithmetic correctness. Inflight demand remains despite absent next descriptor; reset-only sticky timeout joins public safety barrier. No output latency introduced.',
            contract_anchors=[dict(source=watch,text='wire square_progress=completed[c*32+:32]>completed_seen[c];'),
              dict(source=watch,text="else if(age[c]==AGE_W'(LIMIT-1))error[c]<=1;"),
              dict(source=host,text='assign safety_error=local_error || child_error_barrier || canon_error || (|r15_watch_error);')])) )
    spec['exclusions'] += [
        dict(kind='inside_single_macroblock',endpoints=['warm_control'],reason='R15 modulo calendar replaces only pre-edge internal issue enables; original complete payload/owner FIFO remains. Phase anchored by accepted cold frame, local mismatch sticky fault retained; no external active stall.',
             contract_anchors=[dict(source=warm,text="else if(frame_accept && context_in==s)begin r15_phase[s]<=R15_PHASE_W'(1);r15_armed[s]<=1;r15_tail[s]<=0;end")]),
        dict(kind='inside_single_macroblock',endpoints=['CRT'],reason='Three per-lane numeric delay transports r1=27x6,d3=27x5,x12=53x6 use ring8 and continuous read/write distinct offsets3/4. Read prefetch payload unreset; reset fill masks early head. Original valid/E16 eligibility controls acceptance; no mapped saving claimed.')]
    spec['limitations'].append('R15 compute-only: no real shell/CDC/pin clock, GL implementation or protected-twin fault inheritance; source inventory is not netlist completeness.')
    spec['identity'].update(top=full['top'],parameters=params,clock_period_ns=12.0,seed=1)
    spec['sources']={'rtl/'+n:p for n,p in full['generated_sha256'].items()}
    spec['settings']=dict(manifest['control_sha256'],**{'manifest.json':sha(encoded(manifest))})
    files={'rtl/'+n:t.encode() for n,t in full['files'].items()};files.update(controls)
    proof=dict(schema='fit-provisional-aw8-geometry-v1',generator=dict(path=str(GENERATOR),sha256=PIN),kwargs=KWARGS,native_n=256,fit_n=65536)
    return manifest,files,spec,proof


def prepare(output,role):
    out=Path(output).resolve();need(out.is_relative_to(ROOT) and not out.exists(),'fresh R15 physical output')
    manifest,files,spec,proof=build(role)
    for t in spec['transfers']:
        for a in t.get('exception',{}).get('contract_anchors',[]):
            need(a['source'] in files and files[a['source']].decode().count(a['text'])==1,'R15 anchor '+t['id']+repr(a))
    for n,raw in files.items():
        p=out/'project'/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    (out/'project/manifest.json').write_bytes(encoded(manifest))
    for n,obj in [('structural-inventory.json',spec),('provisional-geometry.json',proof)]:(out/n).write_bytes(encoded(obj))
    loader=importlib.util.spec_from_file_location('r15_guard',ROOT/'tools/prefit_structural_guard_v1.py')
    guard=importlib.util.module_from_spec(loader);loader.loader.exec_module(guard)
    result=guard.source_inventory(out/'project',spec);need(not result['findings'],'R15 structural findings '+str(result['findings']))
    return dict(project=str(out/'project'),source_count=60,crossings=len(spec['transfers']),structural_sha256=sha(encoded(spec)),
                provisional_sha256=sha(encoded(proof)),source_findings=result['findings'],native_gate=GATE)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--native-role',required=True,type=Path)
    a=p.parse_args();print(json.dumps(prepare(a.output,a.native_role),indent=2))
