"""Own full application-v2 joint normal; transport time is not compute time.

Uses remote independent whole-integer reference and actual MMIO/DATA/A32
through the real application/CDC. No vendor HIP, board or GL claim.
"""
import json
from pathlib import Path
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump,runtime_before_model
from fpga.reference import stream27_r15_shell_application_native as small

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_shell_application_full_native.py'
CPP='rtl/tb/stream27_r15_shell_application_full.cpp'
HEADER='rtl/tb/s4_p16_two_context_full_config.h'
CAPTURE=ROOT/'results/throughput-20260929/trackS-r15-direct-compute-native-v1/full-normal-v2'
CAPTURE_PIN='41a2bd16c1d52c50c803e1e7e9cfee87d95db65e728061d430a2df6b4a4ae38a'
SMALL=ROOT/'results/throughput-20260929/trackS-r15-shell-application-native-v2/aw8-normal-v3'
SMALL_PIN='6c4d230dfef7a08992e53739035e0297c14ed5cfbd40079e1d01341a6a9397fa'
TOP='genefer_stream27_r15_application_full_observer_v2'
ID='s4-p16-c2-r15-shell-application-full-normal-q1-v3'
OUT=ROOT/'results/throughput-20260929/trackS-r15-shell-application-native-v2/full-normal-v3'
FOOTER='R15_APPLICATION_PASS aw=16 contexts=2 squares=4 signed96_words=262144 cold_records=131136 interval=8461 first=204/4434 core_publication=1 live_core_cdc=1 mmio_data_a32=1 vendor_hip_simulated=0 host_gl=0\n'
SETUP='''
using Image=std::vector<int32_t>;
static std::array<Image,2> INITIAL,EXPECTED;
static void reference_inputs(){
 s4_full_reference::self_check();
 for(unsigned c=0;c<2;c++){
  INITIAL[c].resize(N);uint32_t state=SEEDS[c];
  for(unsigned j=0;j<N;j++){state^=state<<13;state^=state>>17;state^=state<<5;INITIAL[c][j]=int32_t(state%BASES[c]);}
  INITIAL[c][17]=INITIAL[c][N-1]=-1;EXPECTED[c]=INITIAL[c];
  for(unsigned ordinal=0;ordinal<COUNT;ordinal++)EXPECTED[c]=s4_full_reference::square(EXPECTED[c],BASES[c],BITS[c][ordinal]);
 }
 need(EXPECTED[0]!=EXPECTED[1]&&EXPECTED[0][0]!=-1&&EXPECTED[1][0]!=-1,"R15_APPLICATION_OWN_FULL_REFERENCE_DISTINCT");
}
'''


def config():
    return dict(aw=16,n=65536,p=16,contexts=2,counts=[2,2],epochs=[0,0],
      interval=8461,first=[204,4434],r15_flags=small.FLAGS,application_version=2,
      endpoint_version=6,runtime_threads=1,pcie_core_clock_ratio=[3,1])


def validate(stdout,stderr,rc,config,assets):
    need(config==globals()['config']() and assets=={},'R15_APPLICATION_FULL_OWN_CONFIG')
    need(rc==0 and stderr=='' and stdout==FOOTER,'R15_APPLICATION_FULL_ACTUAL_TERMINAL')
    return dict(status='PASS_expected_contracts',measurements=dict(squares=4,signed96_words=262144,
      cold_records=131136,interval=8461,first=[204,4434],runtime_threads=1,independent_reference=True,
      actual_mmio_data_a32=True,actual_application_core_cdc=True),promotion_allowed=False,
      scope='Own application v2/endpoint v6 FULL joint normal at physical-effective epoch defaults0/0. Lean build; host GL assumed (unimplemented). Separate ideal clocks; cold and A32 transport not free and excluded from START-relative compute calendar. No context-alone identity, peer-live count, vendor HIP/PLL, clock, GL or hardware inheritance.')


def full_cpp(original):
    text=original
    replacements={
      '#include "s4_host_contexts_config_v1.h"':'#include "s4_p16_two_context_full_config.h"\n#include "stream27_host_chain_full_reference_v1.h"\n#include <vector>',
      'static_assert(AW==8&&N==256&&P==16,"Own AW8 application normal only");':'static_assert(AW==16&&N==65536&&P==16,"Own full application joint normal only");',
      'static uint32_t lane32':SETUP+'static uint32_t lane32',
      'need(age<100000,"R15_APPLICATION_BOUNDED_CORE_PROGRAM");':'need(age<100ull*N,"R15_APPLICATION_BOUNDED_CORE_PROGRAM");',
      'wr(d,0x24,gen);wr(d,0x50,1);wr(d,0x60,0);wr(d,0x64,session);':
        'wr(d,0x24,gen);wr(d,0x50,1u|(BITS[c][0]?4u:0u));wr(d,0x60,uint32_t(BITS[c][1]<<1));wr(d,0x64,session);',
      'uint32_t word=uint32_t(index<N?INITIAL[c][index]:(index<N+P?C0[c][index-N]:C1[c][index-N-P]));':
        'uint32_t word=uint32_t(index<N?INITIAL[c][index]:0);',
      'static void run(DUT&d){':'static void run(DUT&d){\n reference_inputs();',
      'for(unsigned i=0;i<2000000&&(d.probe_ready!=3||d.probe_busy);i++)tick(d);':
        'for(uint64_t i=0;i<36ull*N&&(d.probe_ready!=3||d.probe_busy);i++)tick(d);',
      small.FOOTER.rstrip('\n').replace('\n','\\n'):FOOTER.rstrip('\n').replace('\n','\\n'),
    }
    for old,new in replacements.items():
        need(text.count(old)==1,'R15_APPLICATION_FULL_DRIVER_ANCHOR:'+old[:80]);text=text.replace(old,new,1)
    runtime_before_model(text)
    need('for(auto&v:d.cold_writedata)' not in text,'R15_APPLICATION_FULL_PACKED_ABI_CORRECTED')
    return text


def role():
    from fpga.reference import stream27_r15_all_io_bind as direct,stream27_r15_pcie_application_bind_v2 as app
    raw=(CAPTURE/'manifest.json').read_bytes();need(sha(raw)==CAPTURE_PIN,'R15_APPLICATION_FULL_OWN_DIRECT_SOURCE')
    m=json.loads(raw);parent=json.loads((CAPTURE/'production-bundle.json').read_bytes())
    files={n:(CAPTURE/'source/fpga'/n).read_bytes() for n in m['sources']}
    need(all(sha(files[n])==h for n,h in m['sources'].items()),'R15_APPLICATION_FULL_CAPTURE_CLOSURE')
    need(sha((SMALL/'manifest.json').read_bytes())==SMALL_PIN and
         sha((ROOT/small.BINDER).read_bytes())==small.BINDER_PIN,'R15_APPLICATION_FULL_FROZEN_APP_DRIVER_ENTRY')
    sm=json.loads((SMALL/'manifest.json').read_bytes());driver=(SMALL/'source/fpga'/sm['build']['cpp_source']).read_bytes()
    need(sha(driver)==sm['sources'][sm['build']['cpp_source']],'R15_APPLICATION_FULL_CORRECTED_PACKED_DRIVER')
    component=direct.prepare(65536,p=16,contexts=2,**{k.lower():v for k,v in small.FLAGS.items() if k!='PCIE_SHELL'},pcie_shell=0)
    need(component['generated_sha256']==parent['generated_sha256'],'R15_APPLICATION_FULL_LITERAL65')
    b=app.application(component);need(len(b['files'])==70 and b['r15_shell_application']['endpoint_version']==6,
                                     'R15_APPLICATION_FULL_V2_SOURCE70')
    for n in parent['files']:files.pop('rtl/'+n)
    files.pop('rtl/'+m['build']['top']+'.sv')
    files.update({'rtl/'+n:t.encode() for n,t in b['files'].items()})
    obs='rtl/'+TOP+'.sv';files[obs]=small.observer(b).replace(small.TOP,TOP).encode()
    header=files[HEADER].decode();old=m['build']['top'];need(header.count(old)==2,'R15_APPLICATION_FULL_HEADER_TOP')
    need(header.count('EPOCHS[2]={65534,42}')==1,'R15_APPLICATION_FULL_OWN_PHYSICAL_EPOCH_HEADER')
    header=header.replace(old,TOP).replace('EPOCHS[2]={65534,42}','EPOCHS[2]={0,0}')+'''constexpr unsigned COUNTS[2]={COUNT,COUNT},FIRST[2]={204,4434},CANON_PASSES=9;
constexpr bool EXPECT_CAPTURE_COPY=false;
'''
    files[HEADER]=header.encode();files[CPP]=full_cpp(driver.decode()).encode()
    files[SELF]=(ROOT/SELF).read_bytes();files[small.SELF]=(ROOT/small.SELF).read_bytes()
    for name,pin in b['source_sha256'].items():
        value=(ROOT/name).read_bytes();need(sha(value)==pin,'R15_APPLICATION_FULL_LINEAGE:'+name);files['lineage/'+name]=value
    m['build'].update(top=TOP,cpp_source=CPP,sv_sources=['rtl/'+n for n in b['rtl_sources']]+[obs],
      parameters=dict(b['parameters'],EPOCH_SEED0=0,EPOCH_SEED1=0),runtime_threads=1)
    m['steps']=[dict(name='normal-full-r15-real-application-core-cdc-joint',argv=['{exe}'],expected_returncode=0,
      validator=dict(source=SELF,function='validate',config=config(),assets={}))]
    m['r15_shell_application_native']=dict(production_top=b['top'],production_generated_sha256=b['generated_sha256'],
      source_sha256=b['source_sha256'],component_source_literal=True,production_sv=70,compiled_sv=71,
      application_entry=small.BINDER,application_entry_sha256=small.BINDER_PIN,
      fixture_epochs=[0,0],physical_default_epochs=[0,0],native_parameters_identical_to_physical_epochs=True,
      actual_mmio_data_a32=True,ideal_separate_clock_ratio=[3,1],independent_reference=True,
      context_alone_identity_claim=False,peer_live_read_count_not_inherited=True,
      transport_cost_not_assumed_zero=True,vendor_HIP_PLL_simulated=False,host_GL_implemented=False,promotion_allowed=False)
    m['sources']={n:sha(v) for n,v in files.items()};snapshot={n:p for n,p in m['sources'].items() if n.endswith('.sv')}
    m.update(source_root='UNBOUND',output_parent='UNBOUND',test_role='normal',rtl_readiness=dict(
      schema='gfn16-candidate-rtl-ready-v1',candidate_id=ID.removesuffix('-q1-v3'),source_snapshot=snapshot,
      candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),rtl_ready_at_utc=small.READY))
    return m,files,b


def freeze():
    m,f,b=role();need(not OUT.exists(),'R15_APPLICATION_FULL_FRESH_OUTPUT');s=OUT/'source/fpga';s.mkdir(parents=True)
    for n,v in f.items():
        p=s/n;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as stream:stream.write(v)
    m['source_root']=str(s);dump(OUT/'manifest.json',m);dump(OUT/'production-bundle.json',b)
    return dict(id=ID,manifest=str(OUT/'manifest.json'),status='OWN_FULL_APP_SOURCE_NOT_NATIVE')


if __name__=='__main__':print(json.dumps(freeze(),indent=2))
