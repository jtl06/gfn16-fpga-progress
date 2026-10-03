"""Fresh protected compute twin, compiled separately from the lean graph.

Same fixed/storage/watch settings and healthy corpus; no two bodies share one
module definition. Protected fault coverage is not inferred from numeric PASS.
"""
import argparse
import json
from pathlib import Path
import re
from fpga.reference import stream27_protected_field100_native_v2 as scalar
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump,runtime_before_model

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_compute_protected_twin_native.py'
BINDER='reference/stream27_r15_all_bind.py'
BINDER_PIN='7bf49d27c712d9a093b5f92d07f791d946ef0ac7bd526bb72186d4e8fac59099'
READY='2026-10-03T08:28:21Z'
FLAGS=dict(FIXED_SCHEDULE=1,LEAN_BUILD=0,PROGRESS_WATCHDOG=1,STORAGE_TO_RAM=1,DIRECT_COLD=0,PCIE_SHELL=0)
IDS={s:'s4-p16-c2-r15-compute-protected-twin-'+s+'-normal-q1-v1' for s in ('aw8','full')}


def validate(stdout,stderr,rc,config,assets):
    need(config==dict(scalar.config(),r15_flags=FLAGS) and assets=={},'R15_PROTECTED_TWIN_CONFIG')
    value=scalar.validate(stdout,stderr,rc,scalar.config(),{})
    value.update(r15_flags=FLAGS,promotion_allowed=False,
      scope='Own separately compiled protected fixed/storage/watch twin healthy outputs/cycles only. No lean/ancestor execution, fault protection, clock or host GL qualification.')
    return value


def role(stage):
    from fpga.reference import stream27_r15_all_bind as core
    from fpga.reference import stream27_r15_compute_native as lean_recipe
    need(stage in IDS and sha((ROOT/BINDER).read_bytes())==BINDER_PIN,'R15_PROTECTED_TWIN_FROZEN_CORE')
    manifest,files,parent=lean_recipe.role(stage)
    bundle=core.prepare(parent['geometry']['n'],p=16,contexts=2,**{k.lower():v for k,v in FLAGS.items()})
    need(bundle['geometry']==parent['geometry'] and bundle['r15_all']['flags']==FLAGS,
         'R15_PROTECTED_TWIN_OWN_SOURCE_FLAGS_GEOMETRY')
    for n in parent['files']:files.pop('rtl/'+n)
    files.update({'rtl/'+n:t.encode() for n,t in bundle['files'].items()})
    if stage=='aw8':
        path='rtl/tb/s4_host_contexts_config_v1.h';text=files[path].decode()
        need(text.count(parent['top'])==2,'R15_PROTECTED_TWIN_HEADER_TOP')
        files[path]=text.replace(parent['top'],bundle['top']).encode();manifest['build']['top']=bundle['top']
        sv=['rtl/'+n for n in bundle['rtl_sources']]
    else:
        path='rtl/'+manifest['build']['top']+'.sv';text=files[path].decode()
        need(text.count(parent['top'])==1 and text.count('LEAN_BUILD=1')==1,'R15_PROTECTED_TWIN_OBSERVER')
        text=text.replace(parent['top'],bundle['top'],1).replace('LEAN_BUILD=1','LEAN_BUILD=0',1)
        need(not re.search(r'\b(always|always_ff|always_comb|initial)\b',text),'R15_PROTECTED_TWIN_STATELESS')
        files[path]=text.encode();sv=['rtl/'+n for n in bundle['rtl_sources']]+[path]
        manifest['steps'][0].update(name='normal-full-r15-protected-compute-twin-alone-and-joint',
          validator=dict(source=SELF,function='validate',config=dict(scalar.config(),r15_flags=FLAGS),assets={}))
    files[SELF]=(ROOT/SELF).read_bytes()
    for n,pin in bundle['source_sha256'].items():
        raw=(ROOT/n).read_bytes();need(sha(raw)==pin,'R15_PROTECTED_TWIN_LINEAGE:'+n);files['lineage/'+n]=raw
    manifest['build'].update(sv_sources=sv,parameters=dict(bundle['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42))
    runtime_before_model(files[manifest['build']['cpp_source']].decode())
    manifest.pop('r15_compute',None)
    manifest['r15_protected_twin']=dict(contract=bundle['r15_all'],production_top=bundle['top'],
      production_generated_sha256=bundle['generated_sha256'],source_sha256=bundle['source_sha256'],
      separate_compilation=True,same_healthy_corpus_reference_and_START_calendar=True,
      no_lean_or_ancestor_execution_credit=True,own_fault_qualification_pending=True,promotion_allowed=False)
    manifest['sources']={n:sha(raw) for n,raw in files.items()}
    snapshot={n:p for n,p in manifest['sources'].items() if n.endswith('.sv')}
    manifest.update(source_root='UNBOUND',output_parent='UNBOUND',test_role='normal',
      rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=IDS[stage].removesuffix('-q1-v1'),
        source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
        rtl_ready_at_utc=READY))
    return manifest,files,bundle


def freeze(stage):
    m,f,b=role(stage);out=ROOT/'results/throughput-20260929/trackS-r15-compute-protected-twin-native-v1'/(stage+'-normal')
    need(not out.exists(),'R15_PROTECTED_TWIN_FRESH_OUTPUT');source=out/'source/fpga';source.mkdir(parents=True)
    for n,raw in f.items():
        p=source/n;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as stream:stream.write(raw)
    m['source_root']=str(source);dump(out/'manifest.json',m);dump(out/'production-bundle.json',b)
    return dict(id=IDS[stage],manifest=str(out/'manifest.json'),compiled_sv=len(m['build']['sv_sources']),status='SOURCE_NOT_NATIVE')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=tuple(IDS),required=True);a=p.parse_args()
    print(json.dumps(freeze(a.stage),indent=2))
