"""Own normal-first fixed-schedule RTL captures, preserving FIELD100 numerics.

Source-only donor rebind; no ancestor execution/clock/fault result inheritance.
Packet construction uses the existing AzureFIT finite worker separately.
"""
import argparse
import copy
import json
from pathlib import Path
import re

from .stream27_context_storage_combo_registerederror_native import sha, need, dump, once, runtime_before_model
from . import stream27_r15_fixed_schedule_bind as core
from . import stream27_protected_field100_native_v2 as scalar_validator

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_r15_fixed_schedule_native.py'
BINDER = 'reference/stream27_r15_fixed_schedule_bind.py'
BINDER_PIN = '0b86fe6368e4f07172cf6049bfe5cf668424bde7d3e1981796c90d7baa296ae7'
SCALAR = 'reference/stream27_protected_field100_native_v2.py'
SCALAR_PIN = 'caf808cc6c96074ad77d89146bb0b919cec32d5040636a8bceea06c9d39d863c'
READY = '2026-10-03T08:22:31Z'
BASE = ROOT/'results/throughput-20260929/trackS-c2-protected-field100-native-v1'
DONORS = {'aw8': ('aw8-normal', 'a396059b51146bb5daffd13cd4f5403f146805293651fa81f41510dcaa1970e0',
                  'dd8d9196a5ac79381b8e701d021d19a067dde4d319b15799b13f8d8f61441a00'),
          'full': ('full-normal-v2', '51ef1347d976d852f0488d29b575c112329a1e43560b6ee94d53fdc924d4de6e',
                   'f5f0617d989b64bb965b612a0d0cb8b6074c1ecd4f85f01ed66f970dfbf521f2')}
IDS = {s: 's4-p16-c2-r15-fixed-'+s+'-normal-q1-v1' for s in DONORS}


def capture(stage):
    need(stage in DONORS, 'R15_FIXED_STAGE')
    name, mp, bp = DONORS[stage]
    directory = BASE/name
    mr, br = (directory/'manifest.json').read_bytes(), (directory/'production-bundle.json').read_bytes()
    need((sha(mr),sha(br)) == (mp,bp), 'R15_FIXED_IMMUTABLE_DONOR')
    manifest, parent = json.loads(mr), json.loads(br)
    files = {}
    for name, pin in manifest['sources'].items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'R15_FIXED_SOURCE_PATH')
        raw = (directory/'source/fpga'/name).read_bytes()
        need(sha(raw)==pin, 'R15_FIXED_CAPTURE:'+name)
        files[name]=raw
    need(len(parent['files'])==58 and all(files['rtl/'+n]==t.encode() for n,t in parent['files'].items()),
         'R15_FIXED_EXACT_PRODUCTION')
    runtime_before_model(files[manifest['build']['cpp_source']].decode())
    return manifest, files, parent


def config():
    return dict(scalar_validator.config(), fixed_schedule=1)


def validate(stdout, stderr, rc, config, assets):
    need(config==globals()['config']() and assets=={}, 'R15_FIXED_OWN_CONFIG')
    value=scalar_validator.validate(stdout,stderr,rc,scalar_validator.config(),{})
    value.update(scope='Own R15 fixed-schedule protected healthy arithmetic/calendar only; unchanged scalar validator reused, no ancestor native/clock/fault credit.',
                 fixed_schedule=1,promotion_allowed=False)
    return value


def role(stage):
    need(sha((ROOT/BINDER).read_bytes())==BINDER_PIN and sha((ROOT/SCALAR).read_bytes())==SCALAR_PIN,
         'R15_FIXED_PRODUCER_AND_SCALAR_PINS')
    manifest, files, parent = capture(stage)
    production=core.prepare(parent['geometry']['n'],fixed_schedule=1)
    need(production['geometry']==parent['geometry'] and len(production['files'])==58 and
         production['parameters']==dict(parent['parameters'],FIXED_SCHEDULE=1), 'R15_FIXED_ZERO_EDGE_DELTA')
    oldtop,newtop=parent['top'],production['top']
    for name in parent['files']: files.pop('rtl/'+name)
    files.update({'rtl/'+n:t.encode() for n,t in production['files'].items()})
    sv=['rtl/'+n for n in production['rtl_sources']]
    if stage=='aw8':
        path='rtl/tb/s4_host_contexts_config_v1.h'
        text=files[path].decode();need(text.count(oldtop)==2,'R15_FIXED_SMALL_IDENTIFIER')
        files[path]=text.replace(oldtop,newtop).encode()
        manifest['build']['top']=newtop
    else:
        path='rtl/'+manifest['build']['top']+'.sv';text=files[path].decode()
        text,count=re.subn(r'\b'+re.escape(oldtop)+r'\b',newtop,text)
        need(count==1,'R15_FIXED_OBSERVER_CHILD')
        text=once(text,'CARRY_QUARANTINE_LOCAL=1,','CARRY_QUARANTINE_LOCAL=1,FIXED_SCHEDULE=1,')
        text=once(text,'  .CARRY_QUARANTINE_LOCAL(CARRY_QUARANTINE_LOCAL),',
                  '  .CARRY_QUARANTINE_LOCAL(CARRY_QUARANTINE_LOCAL),\n  .FIXED_SCHEDULE(FIXED_SCHEDULE),')
        need(not re.search(r'\b(always|always_ff|always_comb|initial)\b',text),'R15_FIXED_STATELESS_OBSERVER')
        files[path]=text.encode();sv.append(path)
        manifest['steps'][0].update(name='normal-full-r15-fixed-alone-and-joint',
             validator=dict(source=SELF,function='validate',config=config(),assets={}))
    manifest['build']['sv_sources']=sv
    manifest['build']['parameters']=dict(production['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42)
    for name,pin in production['source_sha256'].items():
        raw=(ROOT/name).read_bytes();need(sha(raw)==pin,'R15_FIXED_LINEAGE:'+name)
        files['lineage/'+name]=raw
    # Include actual captured JSON read by the pure fixed-schedule producer.
    for filename in ('manifest.json','production-bundle.json'):
        relative=(BASE/DONORS[stage][0]/filename).relative_to(ROOT)
        files['lineage/'+str(relative)]=(ROOT/relative).read_bytes()
    files[SELF]=(ROOT/SELF).read_bytes()
    files[SCALAR]=(ROOT/SCALAR).read_bytes()
    runtime_before_model(files[manifest['build']['cpp_source']].decode())
    for value in manifest.values():
        if isinstance(value,dict) and 'production_generated_sha256' in value:
            value.update(production_top=newtop,production_generated_sha256=production['generated_sha256'])
    if stage=='aw8':
        for key in ('r84_explicit_small','host_contexts'):manifest[key]['generated_sha256']=production['generated_sha256']
    else:
        manifest['r84']['native_observer'].update(production_top=newtop,
             production_root_sha256=production['generated_sha256'][newtop+'.sv'])
    manifest['r15_fixed_schedule']=dict(production_top=newtop,production_generated_sha256=production['generated_sha256'],
        source_sha256=production['source_sha256'],geometry=production['geometry'],contract=production['r15_fixed_schedule'],
        source_freeze_utc=READY,donor_manifest_sha256=DONORS[stage][1],donor_results_not_inherited=True,
        scalar_assertions_and_reference_reused_only=True,runtime_context_before_every_DUT=True,
        lean_build=False,promotion_allowed=False)
    manifest['sources']={name:sha(raw) for name,raw in files.items()}
    snapshot={name:pin for name,pin in manifest['sources'].items() if name.endswith('.sv')}
    manifest.update(source_root='UNBOUND',output_parent='UNBOUND',test_role='normal',
        rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=IDS[stage].removesuffix('-q1-v1'),
            source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
            rtl_ready_at_utc=READY))
    return manifest,files,production


def freeze(output,stage):
    out=Path(output).resolve();need(out.is_relative_to(ROOT) and not out.exists(),'R15_FIXED_FRESH_OUTPUT')
    manifest,files,production=role(stage)
    source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(raw)
    manifest['source_root']=str(source)
    dump(out/'manifest.json',manifest);dump(out/'production-bundle.json',production)
    return dict(id=IDS[stage],manifest=str(out/'manifest.json'),compiled_sv=len(manifest['build']['sv_sources']),
                status='FROZEN_SOURCE_NOT_NATIVE')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--stage',choices=tuple(DONORS),required=True)
    args=parser.parse_args();print(json.dumps(freeze(args.output,args.stage),indent=2))
