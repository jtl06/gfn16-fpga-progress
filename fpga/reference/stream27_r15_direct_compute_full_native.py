"""Own combined DIRECT65 full normal through real load ACK/COMMIT authority.

Cold transport is outside START-relative arithmetic/calendar measurements. This
is a trusted core-clock source, not real PCIe/CDC or host GL qualification.
"""
import json
from pathlib import Path
import re
from fpga.reference import stream27_protected_field100_native_v2 as scalar
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump,runtime_before_model

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_direct_compute_full_native.py'
BINDER='reference/stream27_r15_all_io_bind.py'
BINDER_PIN='60b270f21ee4f0b93a8a2089af14d5a61e181e25d09c76f35c63fbdac55513bb'
READY='2026-10-03T09:00:26Z'
CAPTURE=ROOT/'results/throughput-20260929/trackS-r15-compute-native-v1/full-normal-v2'
CAPTURE_PIN='022cd0ccceee77227e38a13f50584262da747ab60f187a459e265dbf711422d9'
CPP='rtl/tb/stream27_r15_direct_compute_full.cpp'
FLAGS=dict(FIXED_SCHEDULE=1,LEAN_BUILD=1,PROGRESS_WATCHDOG=1,STORAGE_TO_RAM=1,DIRECT_COLD=1,PCIE_SHELL=0)
ID='s4-p16-c2-r15-direct-compute-full-normal-q1-v1'

DRIVER=r'''
// Core-clock producer: no grant/ACK/loaded/canonical authority is forced.
static unsigned direct_words=0;
static void direct_init(DUT& d){
 d.dc_link_drained=1;d.dc_current_session=7;d.dc_transport_empty=1;
 d.dc_begin=d.dc_cancel=d.dc_commit=d.dc_word_valid=d.dc_context=0;
 d.dc_owner=d.dc_session=d.dc_lease=d.dc_count=d.dc_mask=d.dc_mode=d.dc_index=d.dc_word=0;
 for(auto&v:d.dc_profile)v=0;direct_words=0;
}
static void direct_load(DUT& d,unsigned ctx,const Image& input){
 clear(d);d.dc_context=ctx;d.dc_session=d.dc_current_session;d.dc_lease=d.dc_next_lease;
 unsigned gen=uint8_t(d.dc_job_generation>>(ctx*8))+1;
 unsigned epoch=uint16_t((d.dc_next_epoch>>(ctx*16))+COUNT-1);
 d.dc_owner=(uint64_t(COUNT-1)<<24)|(uint64_t(epoch)<<8)|gen;
 need(d.dc_owner==owner(ctx)&&gen==1&&(d.dc_idle&(1u<<ctx)),"R15_DIRECT_CORE_ISSUED_OWNER_LEASE");
 d.dc_count=COUNT;d.dc_mask=uint32_t(BITS[ctx][1]<<1);d.dc_mode=1u|(BITS[ctx][0]?4u:0u);
 for(auto&v:d.dc_profile)v=0;d.dc_profile[0]=BASES[ctx];d.dc_profile[1]=gen;
 d.dc_begin=1;edge(d);d.dc_begin=0;
 need(d.dc_active&&!d.dc_error&&!d.error&&!(d.dc_loaded&(1u<<ctx)),"R15_DIRECT_ACCEPTED_BEGIN");
 d.dc_transport_empty=0;
 for(unsigned index=0;index<N+2*P;index++){
  d.dc_word_valid=1;d.dc_index=index;d.dc_word=uint32_t(index<N?input[index]:0);
  unsigned waits=0;
  while(true){d.clk=0;d.eval();bool accepted=d.dc_word_ready;edge(d);
   need(!d.dc_error&&!d.error,"R15_DIRECT_WORD_OR_REAL_RAM_ACK");
   if(accepted){need(unsigned(d.dc_applied)==index+1,"R15_DIRECT_ACTUAL_APPLIED_COUNT");direct_words++;break;}
   need(++waits<32,"R15_DIRECT_PORT_GRANT_BOUNDED");
  }
 }
 d.dc_word_valid=0;d.dc_transport_empty=1;
 edge(d);edge(d);need(!d.dc_error&&!d.error&&d.dc_applied==N+2*P,"R15_DIRECT_ACK_DRAIN");
 d.dc_commit=1;edge(d);d.dc_commit=0;
 for(unsigned e=0;e<4&&!(d.dc_loaded&(1u<<ctx));e++)edge(d);
 need(!d.dc_error&&!d.error&&!d.dc_active&&(d.dc_loaded&(1u<<ctx)),"R15_DIRECT_COMMIT_LOADED_AUTHORITY");
 edge(d);
}
'''


def config():return dict(scalar.config(),r15_flags=FLAGS)


def validate(stdout,stderr,rc,config,assets):
    need(config==globals()['config']() and assets=={},'R15_DIRECT_FULL_OWN_CONFIG')
    value=scalar.validate(stdout,stderr,rc,scalar.config(),{})
    value.update(r15_flags=FLAGS,promotion_allowed=False,
      scope='Own DIRECT65 ACK/COMMIT-loaded full context-alone/joint healthy output/calendar. Lean build; host GL assumed (unimplemented). START-relative cycles exclude cold transport; no real PCIe/CDC/protected-fault/clock claim.')
    return value


def direct_cpp(original):
    marker=' for(unsigned i=0;i<2*P;i++)d.initial_c0[i]=d.initial_c1[i]=0;\n}'
    need(original.count(marker)==1,'R15_DIRECT_FULL_CLEAR_ABI')
    text=original.replace(marker,marker[:-1]+' d.dc_begin=d.dc_cancel=d.dc_commit=d.dc_word_valid=0;\n}',1)
    marker='static void edge(DUT& d){d.clk=0;d.eval();d.clk=1;d.eval();d.clk=0;d.eval();}'
    need(text.count(marker)==1,'R15_DIRECT_FULL_EDGE_ABI');text=text.replace(marker,marker+DRIVER,1)
    marker=' clear(d);d.rst_n=0;edge(d);'
    need(text.count(marker)==1,'R15_DIRECT_FULL_RESET_ABI');text=text.replace(marker,' direct_init(d);clear(d);d.rst_n=0;edge(d);',1)
    old=''' for(unsigned ctx=0;ctx<2;ctx++)if(mask&(1u<<ctx))for(unsigned address=0;address<N;address++){
  clear(d);d.host_context=ctx;d.host_addr=address;d.write_data=uint32_t(input[ctx][address]);d.load_we=d.read_en=1;
  edge(d);need(!d.error&&!d.busy&&!d.read_valid&&!d.canonical_ready,"R84_COLD_LOAD_PRIORITY");
 }
'''
    need(text.count(old)==1,'R15_DIRECT_FULL_REPLACE_SCALAR_LOAD')
    text=text.replace(old,''' for(unsigned ctx=0;ctx<2;ctx++)if(mask&(1u<<ctx))direct_load(d,ctx,input[ctx]);
 need(d.dc_loaded==mask&&direct_words==unsigned((mask&1u)+((mask>>1)&1u))*(N+2*P),"R15_DIRECT_COMPLETE_COLD_CONTEXTS");
''',1)
    runtime_before_model(text)
    return text


def role():
    from fpga.reference import stream27_r15_all_io_bind as core
    from fpga.reference.stream27_r15_direct_cold_bind import PORTS
    need(sha((ROOT/BINDER).read_bytes())==BINDER_PIN,'R15_DIRECT_FULL_FROZEN_COMBINED')
    raw=(CAPTURE/'manifest.json').read_bytes();need(sha(raw)==CAPTURE_PIN,'R15_DIRECT_FULL_CAPTURED_CORPUS')
    manifest=json.loads(raw);parent=json.loads((CAPTURE/'production-bundle.json').read_bytes())
    files={n:(CAPTURE/'source/fpga'/n).read_bytes() for n in manifest['sources']}
    need(all(sha(files[n])==pin for n,pin in manifest['sources'].items()),'R15_DIRECT_FULL_CAPTURE_CLOSURE')
    bundle=core.prepare(65536,p=16,contexts=2,**{k.lower():v for k,v in FLAGS.items()})
    need(len(bundle['files'])==65 and bundle['r15_all_io']['flags']==FLAGS and
         bundle['geometry']==parent['geometry'],'R15_DIRECT_FULL_COMBINED65_GEOMETRY')
    for name in parent['files']:files.pop('rtl/'+name)
    files.update({'rtl/'+n:t.encode() for n,t in bundle['files'].items()})
    observer='rtl/'+manifest['build']['top']+'.sv';text=files[observer].decode()
    need(text.count(parent['top'])==1 and text.count('DIRECT_COLD=0')==1,'R15_DIRECT_FULL_OBSERVER_ABI')
    text=text.replace(parent['top'],bundle['top'],1).replace('DIRECT_COLD=0','DIRECT_COLD=1',1)
    marker=' input logic clk,rst_n,host_context,load_we,read_en,'
    need(text.count(marker)==1,'R15_DIRECT_FULL_PORT_ABI');text=text.replace(marker,PORTS+marker,1)
    text=text.replace('=candidate.','=candidate.direct_cold.candidate.').replace('{candidate.','{candidate.direct_cold.candidate.').replace(',candidate.',',candidate.direct_cold.candidate.')
    need(not re.search(r'\b(always|always_ff|always_comb|initial)\b',text),'R15_DIRECT_FULL_STATELESS_OBSERVER')
    files[observer]=text.encode()
    original=files[manifest['build']['cpp_source']].decode();files[CPP]=direct_cpp(original).encode()
    files[SELF]=(ROOT/SELF).read_bytes()
    for name,pin in bundle['source_sha256'].items():
        value=(ROOT/name).read_bytes();need(sha(value)==pin,'R15_DIRECT_FULL_LINEAGE:'+name);files['lineage/'+name]=value
    manifest['build'].update(cpp_source=CPP,sv_sources=['rtl/'+n for n in bundle['rtl_sources']]+[observer],
      parameters=dict(bundle['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),runtime_threads=1)
    manifest['steps'][0].update(name='normal-full-r15-direct-compute-alone-and-joint',
      validator=dict(source=SELF,function='validate',config=config(),assets={}))
    manifest['r15_direct_compute']=dict(contract=bundle['r15_all_io'],production_top=bundle['top'],
      production_generated_sha256=bundle['generated_sha256'],source_sha256=bundle['source_sha256'],
      source_freeze_utc=READY,raw_cold_words_per_context=65568,actual_ACK_before_COMMIT=True,
      core_issued_owner_session_lease=True,context_alone_and_joint=True,internal_calendar_unchanged=True,
      cold_transport_excluded_from_START_relative_cycles=True,real_PCIe_CDC=False,host_GL_implemented=False,
      no_ancestor_or_standalone_execution_credit=True,promotion_allowed=False)
    manifest['sources']={n:sha(v) for n,v in files.items()}
    snapshot={n:p for n,p in manifest['sources'].items() if n.endswith('.sv')}
    manifest.update(source_root='UNBOUND',output_parent='UNBOUND',test_role='normal',
      rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=ID.removesuffix('-q1-v1'),
        source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
        rtl_ready_at_utc=READY))
    return manifest,files,bundle


def freeze():
    manifest,files,bundle=role();out=ROOT/'results/throughput-20260929/trackS-r15-direct-compute-native-v1/full-normal'
    need(not out.exists(),'R15_DIRECT_FULL_FRESH_OUTPUT');source=out/'source/fpga';source.mkdir(parents=True)
    for name,value in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(value)
    manifest['source_root']=str(source);dump(out/'manifest.json',manifest);dump(out/'production-bundle.json',bundle)
    return dict(id=ID,manifest=str(out/'manifest.json'),compiled_sv=len(manifest['build']['sv_sources']),status='SOURCE_PREPARED_NOT_NATIVE')


if __name__=='__main__':print(json.dumps(freeze(),indent=2))
