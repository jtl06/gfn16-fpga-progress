"""Fresh own AGE60 source after two preserved prebuild width-policy failures."""
import argparse
import json
from pathlib import Path
from fpga.reference import stream27_r15_protocol_age_native_v2 as parent
from fpga.reference import stream27_r15_protocol_age_bind as original
from fpga.reference import stream27_r15_protocol_age_bind_v3 as binder

ROOT=parent.ROOT
BASE=ROOT/'results/throughput-20260929/trackS-r15-protocol-age-native-v3'
SELF='reference/stream27_r15_protocol_age_native_v3.py'
IDS={stage:'s4-p16-r15-protocol-age-'+stage+'-normal-q1-v3' for stage in parent.parent.PINS}


def config():return dict(parent.config(),epoch_age_boolean_condition=True)


def validate(stdout,stderr,rc,config,assets):
    if config!=globals()['config']() or assets!={}:raise ValueError('R15_AGE_V3_NATIVE_CONFIG')
    old=dict(config);old.pop('epoch_age_boolean_condition')
    result=parent.validate(stdout,stderr,rc,old,{})
    result.update(epoch_age_boolean_condition=True,ancestor_native_or_clock_inherited=False,
      independent_review=False,promotion_allowed=False)
    return result


def role(stage):
    original.need(stage in IDS,'V3_NATIVE_STAGE')
    m,f,old=parent.role(stage);new=binder.prepare(256 if stage=='aw8' else 65536,1)
    original.need(old['top']==new['top'] and set(old['files'])==set(new['files']),'V3_SAME_SOURCE_GRAPH')
    for name,text in new['files'].items():f['rtl/'+name]=text.encode()
    for path in (SELF,binder.SELF):f[path]=(ROOT/path).read_bytes()
    if stage=='full':m['steps'][0]['validator']=dict(source=SELF,function='validate',config=config(),assets={})
    m['steps'][0]['name']='normal-'+stage+'-r15-protocol-age-boolean-v3'
    m['r15_protocol_age'].update(production_generated_sha256=new['generated_sha256'],private_contract=new['r15_protocol_age'],
      boolean_predicate_successor=True,ternary_condition_width=1,own_candidate_id=IDS[stage],
      v1_v2_prebuild_policy_failures_preserved=True,old_execution_not_inherited=True)
    for path in (SELF,binder.SELF):m['r15_protocol_age']['source_sha256'][path]=original.sha(f[path])
    m['r15_compute']['production_generated_sha256']=new['generated_sha256']
    for key in ('r84_explicit_small','host_contexts'):
        if key in m:m[key]['generated_sha256']=new['generated_sha256']
    if stage=='full':m['r84']['native_observer']['production_root_sha256']=new['generated_sha256'][new['top']+'.sv']
    m['sources']={p:original.sha(raw) for p,raw in f.items()}
    snapshot={p:pin for p,pin in m['sources'].items() if p.endswith('.sv')}
    m['rtl_readiness'].update(candidate_id=IDS[stage].removesuffix('-q1-v3'),source_snapshot=snapshot,
      candidate_source_sha256=original.sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()))
    return m,f,new


def prepare(output,stage):
    out=Path(output).resolve();original.need(out.is_relative_to(BASE) and not out.exists(),'V3_NATIVE_FRESH_OUTPUT')
    original.need(not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')),'V3_NATIVE_PAUSE')
    m,f,b=role(stage);source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in f.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as h:h.write(raw)
    m['source_root']=str(source)
    for name,obj in (('manifest.json',m),('production-bundle.json',b)):
        with (out/name).open('x') as h:json.dump(obj,h,indent=2);h.write('\n')
    return dict(id=IDS[stage],manifest=str(out/'manifest.json'),compiled_sv=len(m['build']['sv_sources']),status='SOURCE_PREPARED_NOT_SUBMITTED')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--stage',choices=tuple(IDS),required=True)
    a=p.parse_args();print(json.dumps(prepare(a.output,a.stage),indent=2))
