"""Additive bounded feed24 pilot on exact frozen fullN P8 host/T5b RTL.

No local HDL/ELF/fullN numeric arrays. Future100/1000 is a source plan only,
never automatic launch authority inherited from this pilot.
"""
import argparse
import ast
import json
from pathlib import Path
import re
from fpga.reference import stream27_host_chain_full_native_v1 as parent

ROOT=parent.ROOT
SELF='reference/stream27_host_chain_full_pilot_v1.py'
CPP='rtl/tb/stream27_host_chain_full_pilot_v1.cpp'
HEADER='rtl/tb/s4_host_chain_full_pilot_config_v1.h'
TEST='tests/test_stream27_host_chain_full_pilot_v1.py'
IDENTIFIER='s4-aw16-p8-full-host-pilot24-q1-v1'
DEPENDENCY=parent.IDENTIFIER
COUNT=24
PARENT_PIN='14837cbb854fcabb1ca94d67c769180a67181cfb82b6087ed08ebae1c59ed96a'
CPP_PIN='b5ef4659267497082ac8724ae8d5a5f3918c6dae118bcfe2f3d6cbfe0f745642'
NEGATIVE='S4_FULL_HOST_PILOT_AW16_P8_NEGATIVE_ORACLE_REJECT\n'
BITS=[0,1,0,1,1,0,1,0]*3
WALL_KEYS=('legacy_reference_ms','legacy_candidate_ms','legacy_t5b_ms','legacy_read_ms',
           'feed_reference_ms','feed_candidate_ms','feed_t5b_ms','feed_read_ms')
need,sha,canonical_json,dump=parent.need,parent.sha,parent.canonical_json,parent.dump


def verify():
    parent.verify()
    need(sha((ROOT/parent.SELF).read_bytes())==PARENT_PIN,'S4_FULL_PILOT_PARENT_DRIFT')
    need(sha((ROOT/CPP).read_bytes())==CPP_PIN,'S4_FULL_PILOT_CPP_DRIFT')


def counts():
    result=parent.counts();i=parent.GEOMETRY['warm_interval'];done=parent.GEOMETRY['carry_done'];n=parent.N
    result.update(operations=25,feed_descriptors=23,candidate_cycles=483707+3+23*i+done+2+7*n+4,
                  full_exchanges=19,backpressure_edges=19*i-20)
    return result


def fifo_ledger():
    """Independent pre-edge finite FIFO producer, no RTL/controller imports."""
    interval=parent.GEOMETRY['warm_interval'];level=0;next_index=1;pops=pushes=waits=exchanges=peak=0
    accept_edges=[];pop_edges=[]
    for edge in range(1,3+23*interval+1):
        pop=edge>=3+interval and (edge-3)%interval==0
        valid=next_index<COUNT;ready=level<4 or pop;push=valid and ready
        peak=max(peak,level)
        if valid and not ready:waits+=1
        if push and pop and level==4:exchanges+=1
        if pop:need(level>0,'S4_FULL_PILOT_LEDGER_UNDERFLOW');pops+=1;pop_edges.append(edge)
        if push:pushes+=1;next_index+=1;accept_edges.append(edge)
        level+=int(push)-int(pop);need(0<=level<=4,'S4_FULL_PILOT_LEDGER_WIDTH')
    need(level==0 and next_index==COUNT,'S4_FULL_PILOT_LEDGER_DRAIN')
    return dict(pushes=pushes,pops=pops,peak=peak,full_exchanges=exchanges,
                backpressure_edges=waits,accept_edges=accept_edges,pop_edges=pop_edges)


def footer_prefix():
    return 'S4_FULL_HOST_PILOT_PASS aw=16 p=8 '+' '.join(f'{k}={v}' for k,v in counts().items())+' t5b_wait_edges='


def validate(stdout,stderr,returncode,config,assets):
    need(type(config) is dict and set(config)=={'aw','p','mode'} and type(config['aw']) is int and config['aw']==16 and
         type(config['p']) is int and config['p']==8 and config['mode'] in ('normal','oracle') and assets=={},
         'S4_FULL_PILOT_CONFIG')
    need(type(stdout) is str and type(stderr) is str and type(returncode) is int,'S4_FULL_PILOT_OUTPUT_TYPES')
    measured=None;wall={}
    if config['mode']=='oracle':
        need((returncode,stdout,stderr)==(1,'',NEGATIVE),'S4_FULL_PILOT_TYPED_ORACLE')
    else:
        pattern=re.escape(footer_prefix())+r'([1-9][0-9]*)'
        for key in WALL_KEYS:pattern+=' '+key+r'=(0|[1-9][0-9]*)'
        match=re.fullmatch(pattern+r'\n',stdout,re.ASCII)
        need(returncode==0 and stderr=='' and bool(match),'S4_FULL_PILOT_TYPED_NORMAL')
        measured=int(match.group(1));wall=dict(zip(WALL_KEYS,map(int,match.groups()[1:])))
        need(25<=measured<=25*(20*parent.N+100000),'S4_FULL_PILOT_T5B_BOUND')
        need(sum(wall.values())<=1800000,'S4_FULL_PILOT_WALL_COMMAND_BOUND')
    return dict(status='PASS_expected_contracts',aw=16,p=8,mode=config['mode'],counts=counts(),
                measured_t5b_wait_edges=measured,measured_simulator_wall_ms=wall,promotion_allowed=False,
                scope='Bounded legacy1+dependent mixedfeed24/25 operations; wall times are simulator/reference measurements, not FPGA/PRP performance.')


def source_delta():
    """Reverse ONLY explicit count/label/timing additions to recover v1 bytes."""
    text=(ROOT/CPP).read_text();old=(ROOT/parent.CPP).read_text()
    changes=[
      ('#include "s4_host_chain_full_pilot_config_v1.h"','#include "s4_host_chain_full_config_v1.h"'),
      ('#include <cstdint>\n#include <chrono>','#include <cstdint>'),
      (';std::array<uint64_t,2> reference_ms{},candidate_ms{},t5b_ms{},read_ms{};',';'),
      ('template<class Action>static uint64_t measured_ms(Action action){auto begin=std::chrono::steady_clock::now();action();return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-begin).count();}\n',''),
      ('feed={0,1,0,1,1,0,1,0,0,1,0,1,1,0,1,0,0,1,0,1,1,0,1,0}','feed={0,1,0,1,1,0,1,0}'),
      ('c.reference_ms[job]=measured_ms([&](){for(unsigned bit:bits)reference=s4_full_reference::square(reference,BASE,bit);});','for(unsigned bit:bits)reference=s4_full_reference::square(reference,BASE,bit);'),
      ('c.candidate_ms[job]=measured_ms([&](){candidate(d,bits,bool(job),bool(job),special,c);});','candidate(d,bits,bool(job),bool(job),special,c);'),
      ('c.t5b_ms[job]=measured_ms([&](){production(d,bits,c);});','production(d,bits,c);'),
      ('c.read_ms[job]=measured_ms([&](){compare(d,reference,job,negative,c);});','compare(d,reference,job,negative,c);'),
      ('c.operations==25&&c.descriptors==23','c.operations==9&&c.descriptors==7'),
      ('c.exchange==19&&c.backpressure==19*INTERVAL-20','c.exchange==3&&c.backpressure==3*INTERVAL-4'),
      ('S4_FULL_HOST_PILOT_AW16_P8_NEGATIVE_ORACLE_REJECT','S4_FULL_HOST_AW16_P8_NEGATIVE_ORACLE_REJECT'),
      ('S4_FULL_HOST_PILOT_PASS','S4_FULL_HOST_PASS'),
      ('<<" legacy_reference_ms="<<c.reference_ms[0]<<" legacy_candidate_ms="<<c.candidate_ms[0]<<" legacy_t5b_ms="<<c.t5b_ms[0]<<" legacy_read_ms="<<c.read_ms[0]<<" feed_reference_ms="<<c.reference_ms[1]<<" feed_candidate_ms="<<c.candidate_ms[1]<<" feed_t5b_ms="<<c.t5b_ms[1]<<" feed_read_ms="<<c.read_ms[1]',''),
      ('// Additive bounded full-N pilot: legacy1 then dependent mixed feed24.','// Two bounded full-N host invocations: legacy1 then dependent mixed feed8.')]
    for new,previous in changes:
        need(text.count(new)==1,'S4_FULL_PILOT_SOURCE_ANCHOR '+new[:50]);text=text.replace(new,previous)
    need(text==old,'S4_FULL_PILOT_EXACT_REVERSE_DELTA')
    return dict(parent_cpp_sha256=parent.PINS[parent.CPP],pilot_cpp_sha256=CPP_PIN,reverse_anchors=len(changes),
                independent_reference_unchanged=True,numeric_vectors_unchanged_except_chain_length=True)


def role():
    verify();delta=source_delta();manifest,files=parent.role()
    files[CPP]=(ROOT/CPP).read_bytes()
    header=files[parent.HEADER].decode().replace('EXPECTED_CYCLES=1083886','EXPECTED_CYCLES=1350334')
    need(header!=files[parent.HEADER].decode(),'S4_FULL_PILOT_CYCLE_HEADER_ANCHOR');files[HEADER]=header.encode()
    for name in (SELF,TEST):files[name]=(ROOT/name).read_bytes()
    manifest['build']['cpp_source']=CPP;manifest['sources']={name:sha(raw) for name,raw in files.items()}
    profile=manifest['full_host'];profile['counts']=counts();profile['jobs'][1].update(count=24,bits=BITS)
    profile['scope']='Legacy1+one dependent mixedfeed24,25 operations/all2N final signed96 words, not fullNPRP or physical clock.'
    profile.update(pilot_source_delta=delta,preserved_actual_v1=parent.IDENTIFIER,
        projected_fifo_ledger=fifo_ledger(),simulator_timing_schema=list(WALL_KEYS),
        expectation_scope='Source-derived expectations below, not measured pilot results.',
        projected_programs=[dict(kind='legacy1',setup=99,conversion=8192,warm_done=24950,canonical=393216,copy=65539,host_done=483707),
                            dict(kind='feed24',setup=0,conversion=8192,warm_done=407870,canonical=393216,copy=65539,host_done=866627)],
        runtime_forecast=dict(basis_actual9_normal_seconds=453.6230092370024,naive25_seconds=453.6230092370024*25/9,
                             with25percent_contingency_seconds=453.6230092370024*25/9*1.25,
                             ordinary_command_seconds=1800,ordinary_overall_seconds=3600,
                             warning='Coarse projection only, timeout/OOM retained; no new runtime/budget/thread allowance.'))
    for step in manifest['steps']:step['validator']['source']=SELF
    return manifest,files


def function_body(name):
    raw=(ROOT/parent.SELF).read_text();need(sha(raw.encode())==PARENT_PIN,'S4_FULL_PILOT_FACTORY_PARENT')
    node=next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name==name)
    return ''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])


def namespace():
    result=dict(vars(parent));result.update(role=role,verify=verify,IDENTIFIER=IDENTIFIER,DEPENDENCY=DEPENDENCY,
                                          counts=counts,validate=validate)
    return result


def prepare(output,budget):
    body=function_body('prepare')
    for old,new in (("'s4-aw16-p8-full-host-'+pair+'-v1'","'s4-aw16-p8-full-host-pilot24-'+pair+'-v1'"),
                    ("schema='s4-full-host-dual-v1'","schema='s4-full-host-pilot24-dual-v1'")):
        need(body.count(old)==1,'S4_FULL_PILOT_PACKAGE_ANCHOR');body=body.replace(old,new)
    ns=namespace();exec(compile(body,'[frozen packaging + additive pilot24]','exec'),ns)
    return ns['prepare'](output,budget)


def replay():
    ns=namespace();exec(compile(function_body('replay'),'[source-bound pilot24 owner replay]','exec'),ns)
    result=ns['replay']();result['scope']='Actual bounded legacy1+mixedfeed24/25 operations, not fullNPRP/clock/promotion.'
    result['source_delta']=source_delta()
    normal=next(row for row in result['typed_results'] if row['mode']=='normal')
    normal_step=next(row for row in result['steps'] if row['name']=='full-host-normal')
    need(sum(normal['measured_simulator_wall_ms'].values())<=normal_step['seconds']*1000,
         'S4_FULL_PILOT_WALL_IN_RECORDED_COMMAND')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--budget',type=Path);parser.add_argument('--replay',action='store_true');args=parser.parse_args()
    if args.replay:result=replay();dump(args.output,result)
    else:need(args.budget is not None,'S4_FULL_PILOT_BUDGET');result=prepare(args.output,args.budget)
    print(json.dumps({k:result[k] for k in ('status',) if k in result},indent=2))
