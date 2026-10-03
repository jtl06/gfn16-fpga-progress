"""Preserved unstarted full application, actual-core-edge wait correction only."""
import json
from pathlib import Path
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_application_horizon_adapter_v5.py'
BASE=ROOT/'results/throughput-20260929/trackS-r15-shell-application-native-v2'
PARENT=BASE/'full-normal-v3'
PARENT_PIN='a21fa6c57952e5639146a29406288e892473c95dea2a26e2e021c439f84b7751'
ID='s4-p16-c2-r15-shell-application-full-normal-q1-v5'
OUT=BASE/'full-normal-v5'


def role():
    raw=(PARENT/'manifest.json').read_bytes();need(sha(raw)==PARENT_PIN,'R15_APP_HORIZON_CAPTURE_PIN')
    m=json.loads(raw);b=json.loads((PARENT/'production-bundle.json').read_bytes())
    f={n:(PARENT/'source/fpga'/n).read_bytes() for n in m['sources']}
    need(all(sha(f[n])==h for n,h in m['sources'].items()),'R15_APP_HORIZON_CAPTURE_CLOSURE')
    p=m['build']['cpp_source'];old=f[p].decode()
    need(old.count('i<36ull*N')==1 and old.count('next%12==6')==1,'R15_APP_HORIZON_ONE_CORE_EDGE_PER12_TICKS')
    new=old.replace('i<36ull*N','i<432ull*N',1)
    need(new.replace('i<432ull*N','i<36ull*N',1)==old,'R15_APP_HORIZON_ONLY_DIFF_EXACT_REVERSE')
    f[p]=new.encode();f[SELF]=(ROOT/SELF).read_bytes()
    need(all(f['rtl/'+n]==t.encode() for n,t in b['files'].items()),'R15_APP_HORIZON_ALL70_LITERAL')
    m['r15_application_horizon_v5']=dict(original_manifest_sha256=PARENT_PIN,
      original_cpp_sha256=sha(old.encode()),new_cpp_sha256=sha(new.encode()),
      only_wait_limit_changed=True,cpp_literal_reverse=True,old_ticks_per_N=36,new_ticks_per_N=432,
      ticks_per_core_edge=12,actual_core_edges_per_N=36,
      all70_parameters_header_reference_calendar_control_expectations_unchanged=True,
      original_unstarted_capture_preserved=True,promotion_allowed=False)
    m['sources']={n:sha(v) for n,v in f.items()};m['source_root']=m['output_parent']='UNBOUND'
    m['rtl_readiness']['candidate_id']=ID.removesuffix('-q1-v5')
    return m,f,b


def freeze():
    m,f,b=role();need(not OUT.exists(),'R15_APP_HORIZON_FRESH_OUTPUT');s=OUT/'source/fpga';s.mkdir(parents=True)
    for n,v in f.items():
        p=s/n;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as stream:stream.write(v)
    m['source_root']=str(s);dump(OUT/'manifest.json',m);dump(OUT/'production-bundle.json',b)
    return dict(id=ID,manifest=str(OUT/'manifest.json'),status='CORE_EDGE_WAIT_ONLY_SUCCESSOR_NOT_NATIVE')


if __name__=='__main__':print(json.dumps(freeze(),indent=2))
