"""Observer readiness hash closure only; preserve unsubmitted v9 capture."""
import json
from pathlib import Path
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump
from fpga.reference import stream27_r15_application_full_live_monitor_v9 as body

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_application_full_live_monitor_closure_v2.py'
PARENT=body.OUT
PARENT_PIN='1cd82c28f8da246cfc2e32c6a21b7ad5bdd3bd4fbd6701c957ffe36bffb7c0fc'
OUT=ROOT/'results/throughput-20260929/trackS-r15-shell-application-native-v4/full-live-monitor-v9-closure-v2'
ID=body.ID


def role():
    raw=(PARENT/'manifest.json').read_bytes();need(sha(raw)==PARENT_PIN,'R15_APP_V9_CLOSURE_PRESERVED_PARENT')
    m=json.loads(raw);b=json.loads((PARENT/'production-bundle.json').read_bytes())
    f={n:(PARENT/'source/fpga'/n).read_bytes() for n in m['sources']}
    need(all(sha(f[n])==h for n,h in m['sources'].items()),'R15_APP_V9_CLOSURE_SOURCE_UNCHANGED')
    f[SELF]=(ROOT/SELF).read_bytes();m['sources']={n:sha(v) for n,v in f.items()}
    old=dict(m['rtl_readiness']['source_snapshot'])
    snapshot={n:m['sources'][n] for n in old}
    obs='rtl/'+m['build']['top']+'.sv'
    need({n for n in old if old[n]!=snapshot[n]}=={obs},'R15_APP_V9_ONE_STALE_PASSIVE_OBSERVER_HASH')
    m['rtl_readiness']['source_snapshot']=snapshot
    m['rtl_readiness']['candidate_source_sha256']=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode())
    m['r15_application_observer_closure_v2']=dict(parent_manifest_sha256=PARENT_PIN,
      only_observer_readiness_digest_closed=True,all_original_role_members_unchanged=True,
      failed_capture_not_executed=True,production70_parameters_header_reference_CPP_validator_unchanged=True)
    m['source_root']=m['output_parent']='UNBOUND'
    return m,f,b


def freeze():
    m,f,b=role();need(not OUT.exists(),'R15_APP_V9_CLOSURE_FRESH_OUTPUT')
    source=OUT/'source/fpga';source.mkdir(parents=True)
    for n,value in f.items():
        p=source/n;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as stream:stream.write(value)
    m['source_root']=str(source);dump(OUT/'manifest.json',m);dump(OUT/'production-bundle.json',b)
    return dict(id=ID,manifest=str(OUT/'manifest.json'),sha256=sha((OUT/'manifest.json').read_bytes()))


if __name__=='__main__':print(json.dumps(freeze(),indent=2))
