"""Own R15 DIRECT1/PCIe0 AW8 normal; actual ACK/COMMIT before joint START.

New core-clock lease-aware driver, not the old scalar LOAD ABI. Real PCIe/CDC,
GL/rollback and standalone-loader/ancestor native outcomes are not inherited.
"""
import argparse
import json
from pathlib import Path
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump,runtime_before_model

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_direct_compute_native.py'
BINDER='reference/stream27_r15_all_io_bind.py'
BINDER_PIN='60b270f21ee4f0b93a8a2089af14d5a61e181e25d09c76f35c63fbdac55513bb'
READY='2026-10-03T09:00:26Z'
CAPTURE=ROOT/'results/throughput-20260929/trackS-r15-compute-native-v1/aw8-normal-v2'
CAPTURE_PIN='9ab2753162446e0b0f1ab569ec80dd9ddcccf1580accc1d320baf6b3b2870ed7'
HEADER='rtl/tb/s4_host_contexts_config_v1.h'
CPP='rtl/tb/stream27_r15_direct_compute.cpp'
FLAGS=dict(FIXED_SCHEDULE=1,LEAN_BUILD=1,PROGRESS_WATCHDOG=1,STORAGE_TO_RAM=1,DIRECT_COLD=1,PCIE_SHELL=0)
ID='s4-p16-c2-r15-direct-compute-aw8-normal-q1-v1'

DRIVER=r'''
// Trusted core-clock producer, not a PCIe/CDC implementation.
static unsigned direct_words=0;
static void direct_init(DUT& d){
 d.dc_link_drained=1;d.dc_current_session=7;d.dc_transport_empty=1;
 d.dc_begin=d.dc_cancel=d.dc_commit=d.dc_word_valid=d.dc_context=0;
 d.dc_owner=d.dc_session=d.dc_lease=d.dc_count=d.dc_mask=d.dc_mode=d.dc_index=d.dc_word=0;
 for(auto&v:d.dc_profile)v=0;
 direct_words=0;
}
static void direct_load(DUT& d,unsigned ctx){
 clear(d);d.dc_context=ctx;d.dc_session=d.dc_current_session;d.dc_lease=d.dc_next_lease;
 unsigned gen=uint8_t(d.dc_job_generation>>(ctx*8))+1;
 unsigned epoch=uint16_t((d.dc_next_epoch>>(ctx*16))+COUNTS[ctx]-1);
 d.dc_owner=(uint64_t(COUNTS[ctx]-1)<<24)|(uint64_t(epoch)<<8)|gen;
 need(d.dc_owner==owner(ctx)&&gen==1&&(d.dc_idle&(1u<<ctx)),"R15_DIRECT_CORE_ISSUED_OWNER_LEASE");
 d.dc_count=COUNTS[ctx];d.dc_mask=0;d.dc_mode=1;
 for(auto&v:d.dc_profile)v=0;d.dc_profile[0]=BASES[ctx];d.dc_profile[1]=gen;
 d.dc_begin=1;edge(d);d.dc_begin=0;
 need(d.dc_active&&!d.dc_error&&!d.error&&!(d.dc_loaded&(1u<<ctx)),"R15_DIRECT_ACCEPTED_BEGIN");
 d.dc_transport_empty=0;
 for(unsigned index=0;index<N+2*P;index++){
  d.dc_word_valid=1;d.dc_index=index;
  d.dc_word=uint32_t(index<N?INITIAL[ctx][index]:(index<N+P?C0[ctx][index-N]:C1[ctx][index-N-P]));
  unsigned waits=0;
  while(true){d.clk=0;d.eval();bool accepted=d.dc_word_ready;edge(d);
   need(!d.dc_error&&!d.error,"R15_DIRECT_WORD_OR_REAL_RAM_ACK");
   if(accepted){need(unsigned(d.dc_applied)==index+1,"R15_DIRECT_ACTUAL_APPLIED_COUNT");direct_words++;break;}
   need(++waits<32,"R15_DIRECT_PORT_GRANT_BOUNDED");
  }
 }
 d.dc_word_valid=0;d.dc_transport_empty=1;
 // Drain the actual registered host-write acknowledgments before COMMIT.
 edge(d);edge(d);need(!d.dc_error&&!d.error&&d.dc_applied==N+2*P,"R15_DIRECT_ACK_DRAIN");
 d.dc_commit=1;edge(d);d.dc_commit=0;
 for(unsigned edge_count=0;edge_count<4&&!(d.dc_loaded&(1u<<ctx));edge_count++)edge(d);
 need(!d.dc_error&&!d.error&&!d.dc_active&&(d.dc_loaded&(1u<<ctx)),"R15_DIRECT_COMMIT_LOADED_AUTHORITY");
 edge(d);
}
'''


def direct_cpp(original):
    clear_marker='for(unsigned i=0;i<2*P;i++)d.initial_c0[i]=d.initial_c1[i]=0;}'
    need(original.count(clear_marker)==1,'R15_DIRECT_CLEAR_ABI')
    text=original.replace(clear_marker,clear_marker[:-1]+'d.dc_begin=d.dc_cancel=d.dc_commit=d.dc_word_valid=0;}',1)
    marker='static void edge(DUT& d){d.clk=0;d.eval();d.clk=1;d.eval();}'
    need(text.count(marker)==1,'R15_DIRECT_EDGE_ABI');text=text.replace(marker,marker+DRIVER,1)
    marker='static void run(DUT& d){\n    clear(d);'
    need(text.count(marker)==1,'R15_DIRECT_RESET_ABI');text=text.replace(marker,'static void run(DUT& d){\n    direct_init(d);clear(d);',1)
    old='    for(unsigned ctx=0;ctx<2;ctx++)for(unsigned address=0;address<N;address++){clear(d);d.host_context=ctx;d.host_addr=address;d.load_we=1;d.write_data=INITIAL[ctx][address];edge(d);need(!d.error&&!d.read_valid&&!d.canonical_ready,"S4_HOST_CONTEXT_COLD_LOAD");}'
    need(text.count(old)==1,'R15_DIRECT_REPLACE_LEGACY_SCALAR_LOAD')
    text=text.replace(old,'    for(unsigned ctx=0;ctx<2;ctx++)direct_load(d,ctx);\n    need(d.dc_loaded==3&&direct_words==2*(N+2*P),"R15_DIRECT_COMPLETE_COLD_PAIR");',1)
    return text


def role():
    from fpga.reference import stream27_r15_all_io_bind as core
    need(sha((ROOT/BINDER).read_bytes())==BINDER_PIN,'R15_DIRECT_FROZEN_COMBINED')
    raw=(CAPTURE/'manifest.json').read_bytes();need(sha(raw)==CAPTURE_PIN,'R15_DIRECT_CAPTURED_CORPUS')
    manifest=json.loads(raw);parent=json.loads((CAPTURE/'production-bundle.json').read_bytes())
    files={n:(CAPTURE/'source/fpga'/n).read_bytes() for n in manifest['sources']}
    need(all(sha(files[n])==pin for n,pin in manifest['sources'].items()),'R15_DIRECT_CAPTURE_CLOSURE')
    bundle=core.prepare(256,p=16,contexts=2,**{k.lower():v for k,v in FLAGS.items()})
    need(len(bundle['files'])==65 and bundle['r15_all_io']['flags']==FLAGS and
         bundle['geometry']==parent['geometry'],'R15_DIRECT_COMBINED65_SOURCE')
    for name in parent['files']:files.pop('rtl/'+name)
    files.update({'rtl/'+n:t.encode() for n,t in bundle['files'].items()})
    text=files[HEADER].decode();need(text.count(parent['top'])==2,'R15_DIRECT_HEADER_TOP')
    files[HEADER]=text.replace(parent['top'],bundle['top']).encode()
    original=files[manifest['build']['cpp_source']].decode();cpp=direct_cpp(original);runtime_before_model(cpp)
    files[CPP]=cpp.encode();files[SELF]=(ROOT/SELF).read_bytes()
    for name,pin in bundle['source_sha256'].items():
        value=(ROOT/name).read_bytes();need(sha(value)==pin,'R15_DIRECT_LINEAGE:'+name);files['lineage/'+name]=value
    manifest['build'].update(top=bundle['top'],cpp_source=CPP,sv_sources=['rtl/'+n for n in bundle['rtl_sources']],
      parameters=dict(bundle['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),runtime_threads=1)
    manifest['r15_direct_compute']=dict(contract=bundle['r15_all_io'],production_top=bundle['top'],
      production_generated_sha256=bundle['generated_sha256'],source_sha256=bundle['source_sha256'],
      source_freeze_utc=READY,raw_cold_words=576,lease_and_session_from_core=True,actual_ACK_before_COMMIT=True,
      original_header_reference_and_post_START_assertions=True,internal_calendar_unchanged=True,
      raw_cold_transport_cost_not_zero=True,real_PCIe_CDC=False,host_GL_implemented=False,
      no_source_or_standalone_native_result_inheritance=True,promotion_allowed=False)
    manifest['sources']={n:sha(v) for n,v in files.items()}
    snapshot={n:p for n,p in manifest['sources'].items() if n.endswith('.sv')}
    manifest.update(source_root='UNBOUND',output_parent='UNBOUND',test_role='normal',
      rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=ID.removesuffix('-q1-v1'),
        source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
        rtl_ready_at_utc=READY))
    return manifest,files,bundle


def freeze():
    manifest,files,bundle=role();out=ROOT/'results/throughput-20260929/trackS-r15-direct-compute-native-v1/aw8-normal'
    need(not out.exists(),'R15_DIRECT_FRESH_OUTPUT');source=out/'source/fpga';source.mkdir(parents=True)
    for name,value in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(value)
    manifest['source_root']=str(source);dump(out/'manifest.json',manifest);dump(out/'production-bundle.json',bundle)
    return dict(id=ID,manifest=str(out/'manifest.json'),status='SOURCE_PREPARED_NOT_NATIVE')


if __name__=='__main__':print(json.dumps(freeze(),indent=2))
