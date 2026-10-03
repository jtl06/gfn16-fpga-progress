"""Fresh own whole AGE60 normal cohort after declaration-width policy failure."""
import argparse
import json
from pathlib import Path
from fpga.reference import stream27_r15_protocol_age_native as parent
from fpga.reference import stream27_r15_protocol_age_bind as v1
from fpga.reference import stream27_r15_protocol_age_bind_v2 as binder

ROOT=parent.ROOT
BASE=ROOT/'results/throughput-20260929/trackS-r15-protocol-age-native-v2'
SELF='reference/stream27_r15_protocol_age_native_v2.py'
IDS={stage:'s4-p16-r15-protocol-age-'+stage+'-normal-q1-v2' for stage in parent.PINS}


def config():return dict(parent.config(),epoch_age_flag_width=32)


def validate(stdout,stderr,rc,config,assets):
    if config!=globals()['config']() or assets!={}:raise ValueError('R15_AGE_V2_NATIVE_CONFIG')
    old=dict(config);old.pop('epoch_age_flag_width')
    result=parent.validate(stdout,stderr,rc,old,{})
    result.update(epoch_age_flag_width=32,source_width_successor_own_native=True,
      ancestor_native_or_clock_inherited=False,independent_review=False,promotion_allowed=False)
    return result


def role(stage):
    v1.need(stage in parent.PINS,'V2_NATIVE_STAGE')
    m,f,old=parent.role(stage);new=binder.prepare(256 if stage=='aw8' else 65536,1)
    v1.need(old['top']==new['top'] and set(old['files'])==set(new['files']),'V2_SAME_SOURCE_GRAPH')
    for name,text in new['files'].items():f['rtl/'+name]=text.encode()
    for path in (SELF,binder.SELF):f[path]=(ROOT/path).read_bytes()
    if stage=='full':m['steps'][0]['validator']=dict(source=SELF,function='validate',config=config(),assets={})
    m['steps'][0]['name']='normal-'+stage+'-r15-protocol-age-width-v2'
    m['r15_protocol_age'].update(production_generated_sha256=new['generated_sha256'],private_contract=new['r15_protocol_age'],
      width_successor=True,flag_declaration_width=32,own_candidate_id=IDS[stage],
      v1_prebuild_policy_failure_preserved=True,old_execution_not_inherited=True,
      source_sha256={p:v1.sha(f[p]) for p in (parent.SELF,v1.SELF,v1.MODEL,SELF,binder.SELF)})
    m['r15_compute']['production_generated_sha256']=new['generated_sha256']
    # Only the two observed frozen parent metadata locations are updated.
    for key in ('r84_explicit_small','host_contexts'):
        if key in m:m[key]['generated_sha256']=new['generated_sha256']
    if stage=='full':m['r84']['native_observer']['production_root_sha256']=new['generated_sha256'][new['top']+'.sv']
    m['sources']={p:v1.sha(raw) for p,raw in f.items()}
    snap={p:pin for p,pin in m['sources'].items() if p.endswith('.sv')}
    m['rtl_readiness'].update(candidate_id=IDS[stage].removesuffix('-q1-v2'),source_snapshot=snap,
      candidate_source_sha256=v1.sha(json.dumps(snap,sort_keys=True,separators=(',',':')).encode()))
    return m,f,new


def prepare(output,stage):
    out=Path(output).resolve();v1.need(out.is_relative_to(BASE) and not out.exists(),'V2_NATIVE_FRESH_OUTPUT')
    v1.need(not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')),'V2_NATIVE_PAUSE')
    m,f,b=role(stage);source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in f.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as h:h.write(raw)
    m['source_root']=str(source)
    for name,obj in (('manifest.json',m),('production-bundle.json',b)):
        with (out/name).open('x') as h:json.dump(obj,h,indent=2);h.write('\n')
    return dict(id=IDS[stage],manifest=str(out/'manifest.json'),compiled_sv=len(m['build']['sv_sources']),status='SOURCE_PREPARED_NOT_SUBMITTED')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--stage',choices=tuple(parent.PINS),required=True)
    a=p.parse_args();print(json.dumps(prepare(a.output,a.stage),indent=2))
