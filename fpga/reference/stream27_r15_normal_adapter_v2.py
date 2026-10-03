"""Preserved R15 source roles, adapter-only import-closure successors.

Original v1 source captures are retained. RTL/reference/header/runtime/calendars
are unchanged; the existing typed worker loads an import-safe validator only.
"""
import argparse
import json
from pathlib import Path
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_normal_adapter_v2.py'
VALIDATOR='reference/stream27_r15_normal_validator_v2.py'
BASE=ROOT/'results/throughput-20260929'


def role(mode,stage):
    need(mode in ('fixed','compute') and stage in ('aw8','full'),'R15_ADAPTER_LITERAL_ROLE')
    cohort='trackS-r15-'+('fixed-schedule' if mode=='fixed' else 'compute')+'-native-v1'
    directory=BASE/cohort/(stage+'-normal')
    raw=(directory/'manifest.json').read_bytes();manifest=json.loads(raw)
    bundle=json.loads((directory/'production-bundle.json').read_bytes())
    key='r15_fixed_schedule' if mode=='fixed' else 'r15_compute'
    need(manifest[key]['donor_results_not_inherited'] and
         manifest['build']['parameters']['FIXED_SCHEDULE']==1,'R15_ADAPTER_SOURCE_COHORT')
    files={}
    for name,pin in manifest['sources'].items():
        value=(directory/'source/fpga'/name).read_bytes();need(sha(value)==pin,'R15_ADAPTER_IMMUTABLE_SOURCE:'+name)
        files[name]=value
    files[VALIDATOR]=(ROOT/VALIDATOR).read_bytes();files[SELF]=(ROOT/SELF).read_bytes()
    if stage=='full':
        spec=manifest['steps'][0]['validator']
        spec.update(source=VALIDATOR,function='validate_'+mode)
    manifest[key]['adapter_v2']=dict(original_manifest_sha256=sha(raw),
      only_typed_loader_import_closure_changed=True,production_and_calendar_unchanged=True,
      original_v1_retained_not_native_qualified=True)
    manifest['sources']={name:sha(value) for name,value in files.items()}
    manifest['source_root']=manifest['output_parent']='UNBOUND'
    return manifest,files,bundle


def freeze(mode,stage):
    manifest,files,bundle=role(mode,stage)
    cohort='trackS-r15-'+('fixed-schedule' if mode=='fixed' else 'compute')+'-native-v1'
    out=BASE/cohort/(stage+'-normal-v2');need(not out.exists(),'R15_ADAPTER_FRESH_OUTPUT')
    source=out/'source/fpga';source.mkdir(parents=True)
    for name,value in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(value)
    manifest['source_root']=str(source);dump(out/'manifest.json',manifest);dump(out/'production-bundle.json',bundle)
    return dict(manifest=str(out/'manifest.json'),status='ADAPTER_ONLY_SOURCE_SUCCESSOR_NOT_NATIVE')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=('fixed','compute'),required=True)
    p.add_argument('--stage',choices=('aw8','full'),required=True);args=p.parse_args()
    print(json.dumps(freeze(args.mode,args.stage),indent=2))
