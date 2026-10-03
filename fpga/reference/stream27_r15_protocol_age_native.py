"""Own normal-first age-register compute cohort; no parent result inherited."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import re
from fpga.reference import stream27_r15_protocol_age_bind as binder
from fpga.reference import stream27_r15_normal_validator_v2 as old_validator

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_protocol_age_native.py'
BASE=ROOT/'results/throughput-20260929/trackS-r15-protocol-age-native-v1'
DONOR=binder.BASE
PINS={'aw8':'9ab2753162446e0b0f1ab569ec80dd9ddcccf1580accc1d320baf6b3b2870ed7',
      'full':'022cd0ccceee77227e38a13f50584262da747ab60f187a459e265dbf711422d9'}
IDS={stage:'s4-p16-r15-protocol-age-'+stage+'-normal-q1-v1' for stage in PINS}


def config():
    from fpga.reference import stream27_protected_field100_native_v2 as scalar
    return dict(scalar.config(),r15_flags=old_validator.FLAGS,epoch_age_reg=1)


def validate(stdout,stderr,rc,config,assets):
    if config!=globals()['config']() or assets!={}:raise ValueError('R15_AGE_NATIVE_CONFIG')
    old=dict(config);old.pop('epoch_age_reg')
    result=old_validator.validate_compute(stdout,stderr,rc,old,{})
    result.update(epoch_age_reg=1,scope='Own age-register COMPUTE60 healthy arithmetic/calendar. Lean build; host GL assumed unimplemented. No ancestor native/clock/fault, accelerated protocol wrap, PCIe or promotion claim.',promotion_allowed=False)
    return result


def role(stage):
    binder.need(stage in PINS,'NATIVE_STAGE')
    directory=DONOR/(stage+'-normal-v2')
    raw=(directory/'manifest.json').read_bytes();binder.need(binder.sha(raw)==PINS[stage],'NATIVE_FROZEN_DONOR')
    m=json.loads(raw);old=binder.capture(256 if stage=='aw8' else 65536)
    new=binder.bind(old,1)
    f={p:(directory/'source/fpga'/p).read_bytes() for p in m['sources']}
    binder.need(all(binder.sha(f[p])==pin for p,pin in m['sources'].items()),'NATIVE_SOURCE_PINS')
    for name,text in old['files'].items():
        binder.need(f['rtl/'+name]==text.encode(),'NATIVE_OLD60');f.pop('rtl/'+name)
    f.update({'rtl/'+name:text.encode() for name,text in new['files'].items()})
    sv=['rtl/'+p for p in new['rtl_sources']]
    if stage=='aw8':
        header='rtl/tb/s4_host_contexts_config_v1.h';text=f[header].decode()
        binder.need(text.count(old['top'])==2,'AW8_EXACT_CPP_HEADER')
        f[header]=text.replace(old['top'],new['top']).encode();m['build']['top']=new['top']
    else:
        observer='rtl/'+m['build']['top']+'.sv';text=f[observer].decode()
        binder.need(text.count(old['top'])==1,'FULL_STATELESS_OBSERVER_CALL')
        text=re.sub(r'\b'+re.escape(old['top'])+r'\b',new['top'],text)
        before='CARRY_QUARANTINE_LOCAL=1,';binder.need(text.count(before)==1,'OBSERVER_PARAM')
        text=text.replace(before,before+'EPOCH_AGE_REG=0,',1)
        before='  .CARRY_QUARANTINE_LOCAL(CARRY_QUARANTINE_LOCAL),'
        binder.need(text.count(before)==1,'OBSERVER_FORWARD')
        text=text.replace(before,before+'\n  .EPOCH_AGE_REG(EPOCH_AGE_REG),',1)
        binder.need(not re.search(r'\b(always|always_ff|always_comb|initial)\b',text),'STATELESS_OBSERVER')
        f[observer]=text.encode();sv.append(observer)
        m['steps'][0].update(name='normal-full-r15-protocol-age-alone-and-joint',
            validator=dict(source=SELF,function='validate',config=config(),assets={}))
    m['build'].update(sv_sources=sv,parameters=dict(new['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42))
    for path in (SELF,binder.SELF,binder.MODEL):f[path]=(ROOT/path).read_bytes()
    m['r15_protocol_age']=dict(production_top=new['top'],production_generated_sha256=new['generated_sha256'],
      parent_manifest_sha256=PINS[stage],private_contract=new['r15_protocol_age'],
      source_sha256={p:binder.sha(f[p]) for p in (SELF,binder.SELF,binder.MODEL)},
      source_default_OFF_literal=True,old_execution_not_inherited=True,
      lean_build_label='host GL assumed (unimplemented)',no_new_whole_fit=True,promotion_allowed=False)
    # Donor metadata remains explicitly ancestry; no stale production map.
    m['r15_compute']['age_successor']=dict(ancestor_only=True,parent_manifest_sha256=PINS[stage])
    m['r15_compute'].update(production_top=new['top'],production_generated_sha256=new['generated_sha256'])
    for key in ('r84_explicit_small','host_contexts'):
        if key in m:m[key]['generated_sha256']=new['generated_sha256']
    if stage=='full':m['r84']['native_observer'].update(production_top=new['top'],production_root_sha256=new['generated_sha256'][new['top']+'.sv'])
    m['sources']={p:binder.sha(v) for p,v in f.items()}
    snap={p:pin for p,pin in m['sources'].items() if p.endswith('.sv')}
    m.update(source_root='UNBOUND',output_parent='UNBOUND',test_role='normal',
      rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=IDS[stage].removesuffix('-q1-v1'),
      source_snapshot=snap,candidate_source_sha256=binder.sha(json.dumps(snap,sort_keys=True,separators=(',',':')).encode()),
      rtl_ready_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')))
    return m,f,new


def prepare(output,stage):
    out=Path(output).resolve();binder.need(out.is_relative_to(BASE) and not out.exists(),'NATIVE_FRESH_OUTPUT')
    binder.need(not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')),'NATIVE_PAUSE')
    m,f,b=role(stage);source=out/'source/fpga';source.mkdir(parents=True)
    for name,data in f.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as h:h.write(data)
    m['source_root']=str(source)
    for name,obj in (('manifest.json',m),('production-bundle.json',b)):
        with (out/name).open('x') as h:json.dump(obj,h,indent=2);h.write('\n')
    return dict(id=IDS[stage],manifest=str(out/'manifest.json'),compiled_sv=len(m['build']['sv_sources']),status='SOURCE_PREPARED_NOT_SUBMITTED')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--stage',choices=tuple(PINS),required=True)
    a=p.parse_args();print(json.dumps(prepare(a.output,a.stage),indent=2))
