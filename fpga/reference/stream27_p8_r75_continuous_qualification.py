"""Private short/100 plans for the existing frozen r75 P8 FIFO candidate.

The shared source-selected continuous family owns validation. This constructor
does not execute HDL/reference arithmetic or admit an unmeasured 1000 run.
"""
import argparse
import hashlib
import json
from pathlib import Path
from . import stream27_p8_r75_qualification as source
from . import stream27_s4_continuous_v1 as continuous

ROOT=source.ROOT
SELF='reference/stream27_p8_r75_continuous_qualification.py'
SHORT='s4-p8-r75-short-normal-q1-v1'
PILOT='s4-p8-r75-continuous100-normal-q1-v1'
PRP='s4-p8-r75-eight-prp-normal-q1-v1'
FULL9='s4-aw16-p8-r75-host-normal-q1-v1'

def need(ok,why):
    if not ok:raise ValueError('P8_R75_CONTINUOUS_'+why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def dump(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2);f.write('\n')

def role(operations):
    need(type(operations) is int and operations in (1,100),'SHORT_OR_MEASURED_PILOT_ONLY')
    paired,fitted=source.full_source()
    m,files=continuous.role(operations,canonical_pipe_stages=1,p8_r75=1)
    need(len(m['build']['sv_sources'])==65,'PAIRED65')
    need(set(m['build']['sv_sources'])=={'rtl/'+n for n in paired['rtl_sources']},'EXACT_COMPILED_FULL_SOURCE_SET')
    for n,t in paired['files'].items():need(files['rtl/'+n]==t.encode(),'FROZEN_FULL_SOURCE:'+n)
    need(all(files['rtl/'+n]==t.encode() for n,t in fitted['files'].items()),'FITTED54_SUBSET')
    parameters=dict(AW=16,P=8,CONTEXTS=1,EPOCH_SEED=65534,CANONICAL_PIPE_STAGES=1,
        **{k.upper():v for k,v in source.FLAGS.items()})
    need(m['build']['parameters']==parameters,'EXACT_SIX_FLAGS')
    c=m['continuous'];plan=c['plan']
    need(plan['candidate_root_sha256']==source.ROOT_PIN and
        plan['geometry']==dict(interval=16654,carry_done=24848,first_digit=16653,cold_first=102),
        'OWN_R75_ROOT_AND_CALENDAR')
    need(m['steps'][0]['validator']['config']==dict(operations=operations,negative='none',
        canonical_pipe_stages=1,p8_r75=1),'OWN_VALIDATOR_SELECTION')
    counts=c['counts_ordinary_source_projection']
    need((counts['operations'],counts['resets'],counts['loads'],counts['starts'],counts['readbacks'])==
        (operations,1,1,1,1),'ONE_GENUINE_FIFO_JOB')
    need(counts['candidate_cycles']==680316+(operations-1)*16654 and
        counts['canonical_cycles']==9*65536 and counts['copy_cycles']==65539,'OWN_PHASE_LEDGER')
    files[SELF]=(ROOT/SELF).read_bytes()
    m['sources']={n:sha(raw) for n,raw in files.items()}
    m['r75_qualification']=dict(fitted_root_sha256=source.ROOT_PIN,exact_fitted54_in_paired65=True,
        original_full_RTL_unchanged=True,one_final_readback=True,operations=operations,
        full_N_math_locally_performed=False,promotion_allowed=False,
        longer_role_requires_own_measured_100_forecast_and_P16_priority=True)
    return m,files

def prepare(operations,output):
    output=Path(output).resolve()
    need(output.is_relative_to(ROOT) and not output.exists(),'FRESH_CONTAINED_OUTPUT')
    need(not any((ROOT/n).exists() for n in ('queue/PAUSE','docs/briefs/PAUSE')),'NO_PAUSE')
    m,files=role(operations);src=output/'source/fpga';src.mkdir(parents=True)
    for n,raw in files.items():
        p=src/n;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    m['source_root']=str(src);manifest=output/'manifest.json';dump(manifest,m)
    qid=SHORT if operations==1 else PILOT
    dependencies=[FULL9] if operations==1 else [SHORT,PRP]
    plan=dict(schema='gfn16-candidate-ladder-v1',candidate_id='s4-p8-r75-c138-fallback-v1',
        owner='independent-review',track='S',flags=dict(CANONICAL_PIPE_STAGES=1),
        roles=[dict(id=qid,stage='aw16' if operations==1 else 'pilot100',test_role='normal',priority='P3',
            est_minutes=15 if operations==1 else 25,
            manifest=dict(path=str(manifest),sha256=sha(manifest.read_bytes())),source_root=str(src),
            resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=8,after=dependencies)])
    dump(output/'candidate.json',plan)
    return dict(id=qid,status='source_ready_not_native',candidate=str(output/'candidate.json'))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--operations',type=int,choices=(1,100),required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.operations,a.output),indent=2))
