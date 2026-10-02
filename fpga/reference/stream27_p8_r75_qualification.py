"""Existing frozen P8-r75 fallback: private small PRP/reset qualification.

No new RTL. The canonical harness is a mechanical donor, not inherited
numerical evidence. All fitted54 bytes join the captured paired65 full bundle.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from . import stream27_p8_canonpipe_qualification as donor
from . import stream27_timing_flags as compiler
from . import stream27_host_chain_param_v3 as calendar

ROOT=donor.ROOT
SELF='reference/stream27_p8_r75_qualification.py'
CPP='rtl/tb/stream27_p8_r75_prp_v1.cpp'
FAULT='rtl/tb/stream27_p8_r75_faults_v1.cpp'
HELPER='rtl/tb/stream27_p8_r75_helpers_v1.h'
SCALAR='rtl/tb/stream27_p8_r75_scalar_v1.cpp'
CONFIG='rtl/tb/stream27_p8_r75_config_v1.h'
BUNDLES='results/throughput-20260929/trackS-boundary-inputreg-v1/r75-bundles-v1'
ROOT_PIN='c13871f9d9bf13bdd50c2e4c0084d58351a5d30cdeca614537d0445dd62458d7'
FLAGS=dict(boundary_inputreg=1,descriptor_fifo_ff=1,quarantine_replicas=1,
    final_gs_inputreg=1,canonical_localbase=1,carry_localbase=1)

def need(ok,why):
    if not ok:raise ValueError('P8_R75_QUALIFICATION_'+why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def dump(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2);f.write('\n')
def once(text,old,new):
    need(text.count(old)==1,'ONE_SOURCE_ANCHOR:'+old);return text.replace(old,new)

def full_source():
    b=json.loads((ROOT/BUNDLES/'whole-paired-aw16.json').read_text())
    fitted=json.loads((ROOT/BUNDLES/'whole-standalone-aw16.json').read_text())
    need(len(b['rtl_sources'])==65 and len(fitted['rtl_sources'])==54,'FROZEN_65_54')
    need(sha(fitted['files'][fitted['top']+'.sv'].encode())==ROOT_PIN,'FROZEN_ROOT_C138')
    need(all(b['files'].get(n)==t for n,t in fitted['files'].items()),'54_SUBSET_EXACT')
    need((b['geometry']['first_digit'],b['geometry']['warm_interval'],b['geometry']['carry_done'])==(16653,16654,24848),'EXACT_R75_FULL_CALENDAR')
    return b,fitted

def role(mode='normal'):
    need(mode in ('normal','faults'),'MODE');full_source()
    m,files=donor.role('normal')
    b=compiler.prepare(32,8,paired=True,contexts=1,allow_full_constants=False,canonical_pipe_stages=1,**FLAGS)
    g=b['geometry'];need(len(b['rtl_sources'])==65 and (g['first_digit'],g['warm_interval'],g['carry_done'],g['feedback_delay'])==(123,129,130,5),'SUPPORTED_SMALL_CALENDAR')
    need(b['parameters']==dict(AW=5,P=8,CONTEXTS=1,CANONICAL_PIPE_STAGES=1,**{k.upper():v for k,v in FLAGS.items()}),'EXACT_SIX_FLAGS')
    for n in m['build']['sv_sources']:files.pop(n)
    files.update({'rtl/'+n:t.encode() for n,t in b['files'].items()})
    helper=once(files[donor.HELPER].decode(),'#include "stream27_p8_canonpipe_scalar_v1.cpp"','#include "stream27_p8_r75_scalar_v1.cpp"')
    scalar=once(files[donor.SCALAR].decode(),'#include "stream27_p8_canonpipe_config_v1.h"','#include "stream27_p8_r75_config_v1.h"')
    config=files[donor.CONFIG].decode();oldtop=m['build']['top'];need(config.count(oldtop)==2,'TOP_INCLUDE_TYPEDEF')
    config=config.replace(oldtop,b['top'])
    config=once(config,'MIN_BASE=172,INTERVAL=127,CARRY_DONE=129','MIN_BASE=172,INTERVAL=129,CARRY_DONE=130')
    config=once(config,'FIRST_DIGIT=122','FIRST_DIGIT=123')
    files.update({HELPER:helper.encode(),SCALAR:scalar.encode(),CONFIG:config.encode(),SELF:(ROOT/SELF).read_bytes(),
        CPP if mode=='normal' else FAULT:(ROOT/(CPP if mode=='normal' else FAULT)).read_bytes()})
    for n,pin in b['source_sha256'].items():
        raw=(ROOT/n).read_bytes();need(sha(raw)==pin,'API_LINEAGE:'+n);files['r75-lineage/'+n]=raw
    meta=m.pop('p8_prp_qualification');m.pop('canonical_qualification');expected=[]
    for case in meta['cases']:
        case['harness_donor_cycles']=case['cycles']
        case['cycles']=calendar.cycle_contract(32,g,count=case['operations'],special=case['expected'][0]==-1,canonical_pipe_stages=1)['host_done']
        expected.append(f"P8_R75_PRP_CASE index={case['index']} base={case['base']} operations={case['operations']} cycles={case['cycles']} prp={int(case['expected']==[1]+[0]*31)} reads=32")
    meta['host_cycles']=sum(c['cycles'] for c in meta['cases']);need(meta['operations']==5000,'FROZEN_8_COMPLETE_PRPS')
    expected.append(f"P8_R75_PRP_PASS cases=8 operations=5000 descriptors=4992 rows=32 reads=256 cycles={meta['host_cycles']} base_floor=172")
    if mode=='normal':
        m['steps']=[dict(name='p8-r75-eight-prp-normal',argv=['{exe}','{root}/assets/p8-eight-prp-v1.txt'],expected_returncode=0,
            expected_stdout='\n'.join(expected)+'\n',expected_stderr='')]
    else:
        m['steps']=[dict(name='p8-r75-minimal-reset-cancellation',argv=['{exe}'],expected_returncode=0,expected_stderr='',
            expected_stdout='P8_R75_FAULT_PASS underflow_cancels=1 reset_aborts=2 reset_ages=10,239 recovery_reads=128 nonzero_recovery_reads=32\n'),
            dict(name='p8-r75-typed-oracle-negative',argv=['{exe}','--negative-oracle'],expected_returncode=1,expected_stdout='',
                expected_stderr='S4_HOST_ORACLE_TYPED aw=5 case=0 job=0 address=0 expected=19 actual=18\n')]
    m['build'].update(top=b['top'],sv_sources=['rtl/'+n for n in b['rtl_sources']],cpp_source=CPP if mode=='normal' else FAULT,
        parameters=dict(b['parameters'],EPOCH_SEED=65534))
    m['r75_qualification']=dict(mode=mode,geometry=g,flags=FLAGS,source_sha256=b['source_sha256'],generated_sha256=b['generated_sha256'],
        fitted_full_root_sha256=ROOT_PIN,original_numeric_assets_preserved=True,oracle=meta if mode=='normal' else None,
        no_inherited_canonical_or_boundary_native_result=True,local_full_N_numeric_performed=False,promotion_allowed=False)
    m['sources']={n:sha(raw) for n,raw in files.items()};return m,files

def prepare(output,mode='normal'):
    output=Path(output).resolve();need(output.is_relative_to(ROOT) and not output.exists(),'FRESH')
    need(not any((ROOT/n).exists() for n in ('queue/PAUSE','docs/briefs/PAUSE')),'PAUSE')
    m,files=role(mode);source=output/'source/fpga';source.mkdir(parents=True)
    for n,raw in files.items():
        p=source/n;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    m['source_root']=str(source);manifest=output/'manifest.json';dump(manifest,m)
    qid='s4-p8-r75-eight-prp-normal-q1-v1' if mode=='normal' else 's4-p8-r75-host-faults-q1-v1'
    plan=dict(schema='gfn16-candidate-ladder-v1',candidate_id='s4-p8-r75-c138-fallback-v1',owner='independent-review',track='S',
        flags=dict(CANONICAL_PIPE_STAGES=1),roles=[dict(id=qid,stage='e2e1' if mode=='normal' else 'typed_mutant',
            test_role='normal' if mode=='normal' else 'deliberate_fault',priority='P3',est_minutes=15 if mode=='normal' else 5,
            manifest=dict(path=str(manifest),sha256=sha(manifest.read_bytes())),source_root=str(source),
            resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=8,
            after=['s4-aw16-p8-r75-host-normal-q1-v1'])])
    dump(output/'candidate.json',plan);return dict(id=qid,plan=str(output/'candidate.json'),status='source_ready_not_native')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--mode',choices=('normal','faults'),default='normal')
    a=p.parse_args();print(json.dumps(prepare(a.output,a.mode),indent=2))
