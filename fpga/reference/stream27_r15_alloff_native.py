"""Fresh all-OFF literal FIELD100 normal outputs/cycles; no record inheritance."""
import argparse
import json
from pathlib import Path
from fpga.reference import stream27_protected_field100_native_v2 as scalar
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_alloff_native.py'
BINDER='reference/stream27_r15_all_bind.py'
BINDER_PIN='7bf49d27c712d9a093b5f92d07f791d946ef0ac7bd526bb72186d4e8fac59099'
READY='2026-10-03T08:28:21Z'
IDS={s:'s4-p16-c2-r15-alloff-'+s+'-normal-q1-v1' for s in ('aw8','full')}


def validate(stdout,stderr,rc,config,assets):
    if config!=dict(scalar.config(),r15_all_off=True) or assets!={}:raise ValueError('R15_ALLOFF_CONFIG')
    value=scalar.validate(stdout,stderr,rc,scalar.config(),{})
    value.update(scope='Fresh R15 all-OFF literal FIELD100 healthy outputs/cycles only; no adopted-record execution or clock credit.',
                 r15_all_off=True,promotion_allowed=False)
    return value


def role(stage):
    from fpga.reference import stream27_r15_all_bind as core
    from fpga.reference import stream27_r15_fixed_schedule_native as donor
    need(stage in IDS and sha((ROOT/BINDER).read_bytes())==BINDER_PIN,'R15_ALLOFF_FROZEN_CENTRAL')
    manifest,files,parent=donor.capture(stage)
    bundle=core.prepare(parent['geometry']['n'])
    need(bundle==parent,'R15_ALLOFF_LITERAL_BUNDLE')
    for name in (SELF,BINDER):files[name]=(ROOT/name).read_bytes()
    if stage=='full':manifest['steps'][0].update(name='normal-full-r15-alloff-alone-and-joint',
       validator=dict(source=SELF,function='validate',config=dict(scalar.config(),r15_all_off=True),assets={}))
    manifest['r15_all_off']=dict(all_OFF_source_literal=True,production_top=parent['top'],
      production_generated_sha256=parent['generated_sha256'],source_freeze_utc=READY,
      prior_record_execution_or_clock_not_inherited=True,own_native_pending=True)
    manifest['sources']={n:sha(raw) for n,raw in files.items()}
    snapshot={n:p for n,p in manifest['sources'].items() if n.endswith('.sv')}
    manifest.update(source_root='UNBOUND',output_parent='UNBOUND',test_role='normal',
      rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=IDS[stage].removesuffix('-q1-v1'),
        source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
        rtl_ready_at_utc=READY))
    return manifest,files,bundle


def freeze(stage):
    manifest,files,bundle=role(stage)
    out=ROOT/'results/throughput-20260929/trackS-r15-alloff-native-v1'/(stage+'-normal')
    need(not out.exists(),'R15_ALLOFF_FRESH_OUTPUT');source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(raw)
    manifest['source_root']=str(source);dump(out/'manifest.json',manifest);dump(out/'production-bundle.json',bundle)
    return dict(id=IDS[stage],manifest=str(out/'manifest.json'),status='SOURCE_PREPARED_NOT_NATIVE')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=tuple(IDS),required=True);args=p.parse_args()
    print(json.dumps(freeze(args.stage),indent=2))
