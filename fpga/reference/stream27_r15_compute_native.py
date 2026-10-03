"""Source-own R15 compute mode normal rebind; host GL assumed (unimplemented).

Fixed calendar, private numeric storage, lean reports and per-context watchdog.
No direct cold/PCIe path is claimed. All-OFF FIELD100 reference assertions are
reused only as healthy numerical contracts, not prior execution qualification.
"""
import argparse
import json
from pathlib import Path
import re
from . import stream27_r15_all_bind as core
from . import stream27_r15_fixed_schedule_native as donor
from .stream27_context_storage_combo_registerederror_native import sha, need, dump, once, runtime_before_model

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_compute_native.py'
BINDER='reference/stream27_r15_all_bind.py'
BINDER_PIN='7bf49d27c712d9a093b5f92d07f791d946ef0ac7bd526bb72186d4e8fac59099'
READY='2026-10-03T08:28:21Z'
FLAGS=dict(FIXED_SCHEDULE=1,LEAN_BUILD=1,PROGRESS_WATCHDOG=1,STORAGE_TO_RAM=1,DIRECT_COLD=0,PCIE_SHELL=0)
IDS={stage:'s4-p16-c2-r15-compute-'+stage+'-normal-q1-v1' for stage in ('aw8','full')}


def config():
    return dict(donor.scalar_validator.config(),r15_flags=FLAGS)


def validate(stdout,stderr,rc,config,assets):
    need(config==globals()['config']() and assets=={},'R15_COMPUTE_OWN_CONFIG')
    value=donor.scalar_validator.validate(stdout,stderr,rc,donor.scalar_validator.config(),{})
    value.update(scope='Own R15 compute healthy numeric/calendar only; lean build; host GL assumed (unimplemented); no protected-fault, PCIe/CDC or clock qualification.',
                 r15_flags=FLAGS,promotion_allowed=False)
    return value


def role(stage):
    need(stage in IDS and sha((ROOT/BINDER).read_bytes())==BINDER_PIN,'R15_COMPUTE_FROZEN_MODE')
    manifest,files,parent=donor.capture(stage)
    production=core.prepare(parent['geometry']['n'],p=16,contexts=2,**{k.lower():v for k,v in FLAGS.items()})
    need(production['r15_all']['source_ready'] and production['r15_all']['flags']==FLAGS and
         production['geometry']==parent['geometry'] and len(production['files'])==60,'R15_COMPUTE_OWN_ZERO_EDGE_SOURCE')
    oldtop,newtop=parent['top'],production['top']
    for name in parent['files']:files.pop('rtl/'+name)
    files.update({'rtl/'+n:t.encode() for n,t in production['files'].items()})
    sv=['rtl/'+n for n in production['rtl_sources']]
    if stage=='aw8':
        header='rtl/tb/s4_host_contexts_config_v1.h';text=files[header].decode()
        need(text.count(oldtop)==2,'R15_COMPUTE_SMALL_IDENTIFIER');files[header]=text.replace(oldtop,newtop).encode()
        manifest['build']['top']=newtop
    else:
        path='rtl/'+manifest['build']['top']+'.sv';text=files[path].decode()
        text,count=re.subn(r'\b'+re.escape(oldtop)+r'\b',newtop,text);need(count==1,'R15_COMPUTE_OBSERVER_CHILD')
        text=once(text,'CARRY_QUARANTINE_LOCAL=1,','CARRY_QUARANTINE_LOCAL=1,'+','.join(k+'='+str(v) for k,v in FLAGS.items())+',')
        text=once(text,'  .CARRY_QUARANTINE_LOCAL(CARRY_QUARANTINE_LOCAL),',
            '  .CARRY_QUARANTINE_LOCAL(CARRY_QUARANTINE_LOCAL),\n'+''.join('  .'+k+'('+k+'),\n' for k in FLAGS).rstrip('\n'))
        need(not re.search(r'\b(always|always_ff|always_comb|initial)\b',text),'R15_COMPUTE_STATELESS_OBSERVER')
        files[path]=text.encode();sv.append(path)
        manifest['steps'][0].update(name='normal-full-r15-compute-alone-and-joint',
            validator=dict(source=SELF,function='validate',config=config(),assets={}))
    manifest['build']['sv_sources']=sv
    manifest['build']['parameters']=dict(production['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42)
    for name,pin in production['source_sha256'].items():
        raw=(ROOT/name).read_bytes();need(sha(raw)==pin,'R15_COMPUTE_LINEAGE:'+name);files['lineage/'+name]=raw
    for stage_info in donor.DONORS.values():
        for filename in ('manifest.json','production-bundle.json'):
            relative=(donor.BASE/stage_info[0]/filename).relative_to(ROOT)
            files['lineage/'+str(relative)]=(ROOT/relative).read_bytes()
    for name in (SELF,donor.SELF,donor.SCALAR):files[name]=(ROOT/name).read_bytes()
    runtime_before_model(files[manifest['build']['cpp_source']].decode())
    for value in manifest.values():
        if isinstance(value,dict) and 'production_generated_sha256' in value:
            value.update(production_top=newtop,production_generated_sha256=production['generated_sha256'])
    if stage=='aw8':
        for key in ('r84_explicit_small','host_contexts'):manifest[key]['generated_sha256']=production['generated_sha256']
    else:manifest['r84']['native_observer'].update(production_top=newtop,
            production_root_sha256=production['generated_sha256'][newtop+'.sv'])
    manifest['r15_compute']=dict(contract=production['r15_all'],production_top=newtop,
        production_generated_sha256=production['generated_sha256'],source_sha256=production['source_sha256'],
        source_freeze_utc=READY,geometry=production['geometry'],donor_manifest_sha256=donor.DONORS[stage][1],
        donor_results_not_inherited=True,runtime_context_before_every_DUT=True,
        lean_build_label='lean build; host GL assumed (unimplemented)',host_GL_implemented=False,
        protected_fault_rollback_claim=False,pcie_CDC_backpressure_qualification=False,promotion_allowed=False)
    manifest['sources']={name:sha(raw) for name,raw in files.items()}
    snapshot={n:p for n,p in manifest['sources'].items() if n.endswith('.sv')}
    manifest.update(source_root='UNBOUND',output_parent='UNBOUND',test_role='normal',
        rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=IDS[stage].removesuffix('-q1-v1'),
          source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
          rtl_ready_at_utc=READY))
    return manifest,files,production


def freeze(output,stage):
    out=Path(output).resolve();need(out.is_relative_to(ROOT) and not out.exists(),'R15_COMPUTE_FRESH_OUTPUT')
    manifest,files,production=role(stage);source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(raw)
    manifest['source_root']=str(source);dump(out/'manifest.json',manifest);dump(out/'production-bundle.json',production)
    return dict(id=IDS[stage],manifest=str(out/'manifest.json'),compiled_sv=len(manifest['build']['sv_sources']),
                status='FROZEN_SOURCE_NOT_NATIVE')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--stage',choices=tuple(IDS),required=True)
    args=p.parse_args();print(json.dumps(freeze(args.output,args.stage),indent=2))
