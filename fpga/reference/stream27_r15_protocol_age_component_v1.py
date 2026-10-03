"""AUTHOR bounded old/new primitive equivalence, source-visible reset seeds.

Private diagnostic clones add ONLY RESET_CYCLE and reset timestamp seed. Both
old/new near-wrap instances seed fffffff0; no cycle/age/authority forcing at
runtime, no billions-edge claim, no whole COMPUTE numerical qualification.
"""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from . import stream27_r15_protocol_age_bind as binder

ROOT=binder.ROOT
BASE=ROOT/'results/throughput-20260929/trackS-r15-protocol-age-component-v1'
SELF='reference/stream27_r15_protocol_age_component_v1.py'
CPP='rtl/tb/stream27_r15_protocol_age_probe.cpp'
RUNTIME='rtl/tb/native_runtime_context_v1.h'
TOP='stream27_r15_protocol_age_probe'
OUTPUTS=[('frame_accept',1),('correction_accept',1),('correction_base',32),
 ('pointwise_accept',1),('commit_enable',1),('pointwise_epoch',16),('sink_epoch',16),
 ('pointwise_row',4),('sink_row',4),('correction_bank',2),('pointwise_bank',2),
 ('sink_bank',2),('owner_count',3),('out_error',1),('fault_pending',1),
 ('pointwise_payload_owner_next',27),('pointwise_payload_row_next',4)]
INPUTS=[('clk',1),('rst_n',1),('external_fault_pending',1),('fault_report_copies',2),
 ('frame_begin',1),('frame_context',1),('frame_epoch',16),('frame_generation',8),('frame_base',32),
 ('correction_valid',1),('correction_context',1),('correction_epoch',16),('correction_generation',8),
 ('cache_ready',1),('cache_context',1),('cache_epoch',16),('cache_generation',8),
 ('pointwise_slot',1),('pointwise_frame_start',1),('pointwise_context',1),('pointwise_epoch_in',16),('pointwise_generation',8),
 ('sink_slot',1),('sink_frame_start',1),('sink_context',1),('sink_epoch_in',16),('sink_generation',8),
 ('context_enabled',2),('live_generation',16)]


def declaration(direction,name,width):return f'{direction} logic '+(f'[{width-1}:0] ' if width!=1 else '')+name


def diagnostic(parent,name):
    before='parameter int unsigned ROWS='
    if parent.count(before)!=1 or parent.count("cycle_count<='0;")!=1:raise ValueError('R15_AGE_COMPONENT_RESET_ANCHOR')
    text=parent.replace(before,"parameter logic [31:0] RESET_CYCLE=32'b0,\n "+before,1)
    text=text.replace("cycle_count<='0;",'cycle_count<=RESET_CYCLE;',1)
    old=parent.split('module ',1)[1].split(' #(',1)[0]
    if text.count('module '+old+' #(')!=1:raise ValueError('R15_AGE_COMPONENT_MODULE')
    text=text.replace('module '+old+' #(','module '+name+' #(',1)
    reverse=text.replace('module '+name+' #(','module '+old+' #(',1)
    reverse=reverse.replace("parameter logic [31:0] RESET_CYCLE=32'b0,\n "+before,before,1)
    reverse=reverse.replace('cycle_count<=RESET_CYCLE;',"cycle_count<='0;",1)
    if reverse!=parent:raise ValueError('R15_AGE_COMPONENT_DIAGNOSTIC_REVERSE')
    return text


def probe():
    ports=[declaration('input',n,w) for n,w in INPUTS]
    ports += [declaration('output',n,128) for n in ('old0','new0','oldhi','newhi')]
    ports += [declaration('output',n,1) for n in ('invariant0','invarianthi','old_frame_accept','old_correction_accept','old_pointwise_accept','old_commit_enable','old_error')]
    ports += [declaration('output','old_owner_count',3),declaration('output','high_cycle',32)]
    lines=['module '+TOP+'(\n '+',\n '.join(ports)+'\n);']
    for tag in ('o0','n0','oh','nh'):
        lines += [declaration('wire',tag+'_'+n,w)+';' for n,w in OUTPUTS]
        connections=[f'.{n}({n})' for n,_ in INPUTS]+[f'.{n}({tag}_{n})' for n,_ in OUTPUTS]
        connections+=['.quarantine('+tag+'_out_error)']
        seed="32'hfffffff0" if tag.endswith('h') else "32'b0"
        module='r15_age_component_new' if tag.startswith('n') else 'r15_age_component_old'
        parameters=f'.ROWS(16),.POINTWISE_FIRST(79),.SINK_FIRST(153),.CONTEXTS(2),.BANKS(4),.RESET_CYCLE({seed})'
        if tag.startswith('n'):parameters+=',.EPOCH_AGE_REG(1)'
        lines += [module+' #('+parameters+') '+tag+'('+','.join(connections)+');']
        output={'o0':'old0','n0':'new0','oh':'oldhi','nh':'newhi'}[tag]
        lines += [f'assign {output}=128\'('+ '{'+','.join(tag+'_'+n for n,_ in OUTPUTS)+'});']
    for out,signal in [('old_frame_accept','frame_accept'),('old_correction_accept','correction_accept'),('old_pointwise_accept','pointwise_accept'),('old_commit_enable','commit_enable'),('old_error','out_error'),('old_owner_count','owner_count')]:
        lines += [f'assign {out}=o0_{signal};']
    lines += ['assign high_cycle=oh.cycle_count;','always_comb begin',' invariant0=1;invarianthi=1;',
     " for(int i=0;i<4;i=i+1)begin",
     '  if(n0.valid[i] && (n0.pw_age_q[i]!=(n0.cycle_count-n0.pw_first[i]) || n0.sink_age_q[i]!=(n0.cycle_count-n0.sink_first[i])))invariant0=0;',
     '  if(nh.valid[i] && (nh.pw_age_q[i]!=(nh.cycle_count-nh.pw_first[i]) || nh.sink_age_q[i]!=(nh.cycle_count-nh.sink_first[i])))invarianthi=0;',
     ' end','end','endmodule']
    return '\n'.join(lines)+'\n'


def role(variant='normal'):
    if variant not in ('normal','fault','bad-allocation','bad-stop'):raise ValueError('R15_AGE_COMPONENT_VARIANT')
    parent=binder.capture(256)['files'][binder.LEAF]
    new,_=binder.leaf(parent,bad_allocation=variant=='bad-allocation',freeze_on_stop=variant=='bad-stop')
    f={p:(ROOT/p).read_bytes() for p in (SELF,binder.SELF,binder.MODEL,CPP,RUNTIME)}
    old_path='rtl/kernel/r15_age_component_old.sv';new_path='rtl/kernel/r15_age_component_new.sv';probe_path='rtl/tb/'+TOP+'.sv'
    f[old_path]=diagnostic(parent,'r15_age_component_old').encode()
    f[new_path]=diagnostic(new,'r15_age_component_new').encode();f[probe_path]=probe().encode()
    pins={p:hashlib.sha256(raw).hexdigest() for p,raw in f.items()}
    negative=variant.startswith('bad-');fault=variant in ('fault','bad-stop')
    stdout='R15_AGE_COMPONENT_FAULT_PASS origins=2 stop_advances=1 report_copy=1 reset_recovery=1 tuple_authority=1 native_billions=0\n' if fault else 'R15_AGE_COMPONENT_NORMAL_PASS frames=8 pointwise=128 commits=80 modulo32_reset_seed=1 canceled_raw_retire=1 reset_reallocate=1 native_billions=0\n'
    step=dict(name='protocol-age-component-'+variant,argv=['{exe}']+(['--faults'] if fault else []),
      expected_returncode=1 if negative else 0,expected_stderr='R15_AGE_NATIVE_EQUIVALENCE\n' if negative else '',expected_stdout='' if negative else stdout)
    snapshot={p:pins[p] for p in (old_path,new_path,probe_path)}
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',source_root='UNBOUND',output_parent='UNBOUND',sources=pins,
      build=dict(top=TOP,sv_sources=list(snapshot),cpp_source=CPP,parameters={},runtime_threads=1,
        cflags=['-std=c++17','-Werror=return-type','-DGFN16_RUNTIME_THREADS=1']),
      probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),steps=[step],
      test_role='normal' if variant=='normal' else 'deliberate_fault',
      rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-r15-protocol-age-component-'+variant,
        source_snapshot=snapshot,candidate_source_sha256=hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        rtl_ready_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')),
      scope=dict(author='p16_independent_reviewer',variant=variant,parent_leaf_sha256=binder.LEAF_PIN,
        production_candidate_unchanged=True,diagnostic_reset_seeds=[0,0xfffffff0],runtime_age_or_clock_forcing=False,
        old_new_all_ports_checked=True,valid_modular_invariant_checked=True,canceled_raw_retirement=True,
        full_COMPUTE=False,billions_native_edges=False,clock_area=False,independent_review=False,promotion_allowed=False))
    return m,f


def prepare(output,variant='normal'):
    out=Path(output).resolve()
    if not out.is_relative_to(BASE) or out.exists():raise ValueError('R15_AGE_COMPONENT_FRESH_OUTPUT')
    if any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')):raise ValueError('R15_AGE_COMPONENT_PAUSE')
    m,f=role(variant);source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in f.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as h:h.write(raw)
    m['source_root']=str(source)
    with (out/'manifest.json').open('x') as h:json.dump(m,h,indent=2);h.write('\n')
    return dict(id='s4-r15-protocol-age-component-'+variant+'-q1-v1',manifest=str(out/'manifest.json'),status='SOURCE_PREPARED_NOT_SUBMITTED')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--variant',default='normal')
    a=p.parse_args();print(json.dumps(prepare(a.output,a.variant),indent=2))
