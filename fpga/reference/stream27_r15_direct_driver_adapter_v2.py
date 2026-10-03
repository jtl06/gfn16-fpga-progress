"""Preserved DIRECT/application captures, packed-word C++ init-only successors.

VlWide has operator[] but no begin/end in the admitted Verilator5.032 ABI.
No generated RTL, header, reference, control, timing or expectation is changed.
"""
import argparse
import json
from pathlib import Path
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_direct_driver_adapter_v2.py'
BASE=ROOT/'results/throughput-20260929'
ROLES={
 'application':dict(parent='trackS-r15-shell-application-native-v2/aw8-normal',
   pin='a481bac910bee3e191be7957181621b181452b7350d0842348faffcd89af0041',
   output='trackS-r15-shell-application-native-v2/aw8-normal-v3',
   id='s4-p16-c2-r15-shell-application-aw8-normal-q1-v3',
   before='for(auto&v:d.cold_writedata)v=0;',after='for(unsigned i=0;i<8;i++)d.cold_writedata[i]=0;',count=1),
 'direct-aw8':dict(parent='trackS-r15-direct-compute-native-v1/aw8-normal',
   pin='927cdf1a784a444f482cf316e840f7b8ab69dad63d47160fec29023bbe18e1e2',
   output='trackS-r15-direct-compute-native-v1/aw8-normal-v2',
   id='s4-p16-c2-r15-direct-compute-aw8-normal-q1-v2',
   before='for(auto&v:d.dc_profile)v=0;',after='for(unsigned i=0;i<8;i++)d.dc_profile[i]=0;',count=2),
 'direct-full':dict(parent='trackS-r15-direct-compute-native-v1/full-normal',
   pin='838bc2ed9159770d9514bec182838304bdccd98f18ca1c3b133b0fc0b2524fdd',
   output='trackS-r15-direct-compute-native-v1/full-normal-v2',
   id='s4-p16-c2-r15-direct-compute-full-normal-q1-v2',
   before='for(auto&v:d.dc_profile)v=0;',after='for(unsigned i=0;i<8;i++)d.dc_profile[i]=0;',count=2),
}


def role(mode):
    need(mode in ROLES,'R15_DIRECT_ADAPTER_LITERAL_ROLE');r=ROLES[mode];parent=BASE/r['parent']
    raw=(parent/'manifest.json').read_bytes();need(sha(raw)==r['pin'],'R15_DIRECT_ADAPTER_ORIGINAL_CAPTURE')
    manifest=json.loads(raw);bundle=json.loads((parent/'production-bundle.json').read_bytes())
    files={n:(parent/'source/fpga'/n).read_bytes() for n in manifest['sources']}
    need(all(sha(files[n])==h for n,h in manifest['sources'].items()),'R15_DIRECT_ADAPTER_CAPTURE_CLOSURE')
    path=manifest['build']['cpp_source'];old=files[path].decode()
    need(old.count(r['before'])==r['count'],'R15_DIRECT_ADAPTER_PACKED_WORD_INIT_COUNT')
    new=old.replace(r['before'],r['after'])
    need(new.replace(r['after'],r['before'])==old,'R15_DIRECT_ADAPTER_CPP_EXACT_REVERSE')
    files[path]=new.encode();files[SELF]=(ROOT/SELF).read_bytes()
    manifest['r15_packed_driver_adapter_v2']=dict(original_manifest_sha256=r['pin'],
      original_cpp_sha256=sha(old.encode()),new_cpp_sha256=sha(new.encode()),
      replacements=r['count'],old=r['before'],new=r['after'],cpp_literal_reverse=True,
      production_header_reference_calendar_control_expectations_unchanged=True,
      original_native_failure_retained=mode=='direct-aw8',
      original_unstarted_capture_preserved=mode!='direct-aw8',promotion_allowed=False)
    need(all(files['rtl/'+n]==t.encode() for n,t in bundle['files'].items()),'R15_DIRECT_ADAPTER_ALL_PRODUCTION_LITERAL')
    manifest['sources']={n:sha(v) for n,v in files.items()}
    manifest['source_root']=manifest['output_parent']='UNBOUND'
    manifest['rtl_readiness']['candidate_id']=r['id'].rsplit('-q1-',1)[0]
    return manifest,files,bundle,r


def freeze(mode):
    manifest,files,bundle,r=role(mode);out=BASE/r['output'];need(not out.exists(),'R15_DIRECT_ADAPTER_FRESH_OUTPUT')
    source=out/'source/fpga';source.mkdir(parents=True)
    for name,value in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(value)
    manifest['source_root']=str(source);dump(out/'manifest.json',manifest);dump(out/'production-bundle.json',bundle)
    return dict(id=r['id'],manifest=str(out/'manifest.json'),status='CPP_INIT_ONLY_SUCCESSOR_NOT_NATIVE')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=tuple(ROLES),required=True);a=p.parse_args()
    print(json.dumps(freeze(a.mode),indent=2))
