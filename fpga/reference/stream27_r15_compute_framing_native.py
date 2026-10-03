"""Own minimal external framing/underflow and reset recovery, both R15 modes.

No authoritative state pokes or removed-lean detector expectations. Actual
public commands create faults; private canceled raw tails are not field flush.
"""
import argparse
import json
from pathlib import Path
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump,runtime_before_model

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_compute_framing_native.py'
CPP='rtl/tb/stream27_r15_compute_framing.cpp'
CAPTURES={
 'lean':('trackS-r15-compute-native-v1/aw8-normal-v2','9ab2753162446e0b0f1ab569ec80dd9ddcccf1580accc1d320baf6b3b2870ed7'),
 'protected':('trackS-r15-compute-protected-twin-native-v1/aw8-normal','8765d20f613eaea5ed78874705851b33d4ab9321910a0dedb4d4d5c05eb9764b'),
}
FOOTER='R15_FRAMING_PASS cases=7 malformed_ingress=6 required_token_underflow=1 sticky_quiet_edges=168 reset_recovery_signed96_words=7168 public_masks=1 private_field_flush_claim=0\n'

FRAMING=r'''
static bool expect_nonabort=false;
static void public_abort(DUT&d){
 need(d.error&&!d.command_ready&&!d.command_accept&&!d.busy&&!d.done&&!d.canonical_ready&&!d.read_valid,
      "R15_FRAMING_PUBLIC_ABORT_MASKS");
 // operation_accept and field raw slots are canceled private work, not a
 // universal HOST-error flush contract. Never authorize them as publication.
}
static void framing_case(DUT&d,unsigned which){
 clear(d);d.rst_n=0;edge(d);need(!d.error&&!d.busy&&!d.done&&!d.canonical_ready&&!d.read_valid,"R15_FRAMING_RESET");
 d.rst_n=1;clear(d);edge(d);
 for(unsigned c=0;c<2;c++)for(unsigned a=0;a<N;a++){
  clear(d);d.host_context=c;d.host_addr=a;d.load_we=1;d.write_data=INITIAL[c][a];edge(d);
  need(!d.error&&!d.canonical_ready&&!d.read_valid,"R15_FRAMING_COLD_LOAD");
 }
 clear(d);d.start_contexts=d.batch_mode=d.feed_mode=3;
 d.base=uint64_t(BASES[0])|(uint64_t(BASES[1])<<32);d.warm_count=uint64_t(COUNTS[0])|(uint64_t(COUNTS[1])<<32);
 for(unsigned c=0;c<2;c++)for(unsigned b=0;b<P;b++){d.initial_c0[c*P+b]=uint32_t(C0[c][b]);d.initial_c1[c*P+b]=uint32_t(C1[c][b]);}
 edge(d);need(d.busy==3&&!d.error&&d.accepted_generation==0x0101,"R15_FRAMING_ACTUAL_JOB_ACCEPT");
 if(which<6){
  clear(d);d.command_context=which==5?1:0;d.command_index=1;d.command_generation=1;
  d.clk=0;d.eval();need(d.command_ready,"R15_FRAMING_ACTUAL_INGRESS_READY");
  d.command_valid=1;
  switch(which){case 0:d.command_generation=2;break;case 1:d.command_index=0;break;
   case 2:d.command_index=2;break;case 3:d.command_index=COUNTS[0];break;
   case 4:d.command_index=0xffffffffu;break;case 5:d.command_generation=0;break;}
  d.eval();need(!d.command_accept,"R15_FRAMING_REJECT_NOT_ACCEPTED");edge(d);
  if(expect_nonabort)need(!d.error,"R15_FRAMING_NONABORT_EXPECTATION_MUTANT");
  public_abort(d);
 }else{
  // Deliberately do not supply the required next-frame token. No arbitrary
  // stall is allowed and missing FIFO input cannot disarm inflight work.
  unsigned age=0;for(age=1;age<=FIRST[0]+INTERVAL+2&&!d.error;age++){
   clear(d);edge(d);need(!d.done&&!d.canonical_ready&&!d.read_valid,"R15_FRAMING_UNDERFLOW_NO_PUBLICATION");
  }
  need(d.error&&age<=FIRST[0]+INTERVAL+3,"R15_FRAMING_REQUIRED_TOKEN_TYPED_UNDERFLOW");public_abort(d);
 }
 for(unsigned q=0;q<24;q++){
  clear(d);d.read_en=1;d.host_addr=q;d.command_valid=1;d.command_context=q&1;
  d.command_generation=1;d.command_index=1;d.start_contexts=d.batch_mode=d.feed_mode=3;
  edge(d);public_abort(d);need(d.accepted_generation==0x0101,"R15_FRAMING_NO_NEW_JOB_ACCEPT");
 }
 // Reuse the complete own dense17 independent signed96 oracle AFTER reset.
 run(d);
}
static void framing_suite(DUT&d){for(unsigned c=0;c<7;c++)framing_case(d,c);
 std::cout<<"R15_FRAMING_PASS cases=7 malformed_ingress=6 required_token_underflow=1 sticky_quiet_edges=168 reset_recovery_signed96_words=7168 public_masks=1 private_field_flush_claim=0\n";
}
'''


def config(branch,mode,footer):return dict(branch=branch,mode=mode,normal_footer=footer)


def validate(stdout,stderr,rc,config,assets):
    need(set(config)=={'branch','mode','normal_footer'} and config['branch'] in CAPTURES and assets=={},'R15_FRAMING_CONFIG')
    mode=config['mode'];normal=config['normal_footer']
    need(normal.startswith('S4_HOST_CONTEXTS_PASS kind=dense aw=8 p=16 counts=3/14 chains=2 squares=17 reads=1024 ') and
         normal.endswith('owner_bits=56 signed96=1 canonical_host=1\n') and len(normal.splitlines())==1,'R15_FRAMING_OWN_DENSE_FOOTER')
    if mode=='nonabort-negative':
        need(type(rc) is int and rc==1 and stdout=='' and stderr=='R15_FRAMING_NONABORT_EXPECTATION_MUTANT\n',
             'R15_FRAMING_EXPECTATION_SENSITIVITY')
    else:
        need(mode in ('normal','faults') and type(rc) is int and rc==0 and stderr=='' and
             stdout==(normal if mode=='normal' else normal*7+FOOTER),'R15_FRAMING_TYPED_RAW_RESULT')
    return dict(status='PASS_expected_contracts',branch=config['branch'],mode=mode,promotion_allowed=False,
      scope='Own external malformed descriptor and required-token underflow, sticky public masks/reset recovery only. No removed lean detector, arbitrary corruption, peer-local recovery/field-flush, GL/clock/PCIe/protection inheritance.')


def role(branch='lean',faults=False):
    need(branch in CAPTURES and type(faults) is bool,'R15_FRAMING_LITERAL_ROLE')
    capture=ROOT/'results/throughput-20260929'/CAPTURES[branch][0]
    raw=(capture/'manifest.json').read_bytes();need(sha(raw)==CAPTURES[branch][1],'R15_FRAMING_OWN_CAPTURE')
    m=json.loads(raw);b=json.loads((capture/'production-bundle.json').read_bytes())
    f={n:(capture/'source/fpga'/n).read_bytes() for n in m['sources']}
    need(all(sha(f[n])==pin for n,pin in m['sources'].items()) and len(b['files'])==60 and
         b['r15_all']['flags']['LEAN_BUILD']==int(branch=='lean'),'R15_FRAMING_OWN60_CLOSED_FLAGS')
    text=f[m['build']['cpp_source']].decode()
    marker='int main(int argc,char** argv)';need(text.count(marker)==1,'R15_FRAMING_MAIN_ANCHOR')
    text=text.replace(marker,FRAMING+marker,1)
    marker='need((argc==1||oracle_negative)&&gfn16_runtime::matches(context,d),"S4_HOST_CONTEXT_ARGUMENTS_THREADS");run(d);return 0;'
    need(text.count(marker)==1,'R15_FRAMING_RUNTIME_ARGUMENT_ABI')
    text=text.replace(marker,'''bool faults=argc==2&&std::string(argv[1])=="--framing-faults";
 expect_nonabort=argc==2&&std::string(argv[1])=="--framing-nonabort-negative";
 need((argc==1||oracle_negative||faults||expect_nonabort)&&gfn16_runtime::matches(context,d),"S4_HOST_CONTEXT_ARGUMENTS_THREADS");
 if(expect_nonabort){framing_case(d,0);return 0;}if(faults){framing_suite(d);return 0;}run(d);return 0;''',1)
    runtime_before_model(text);f[CPP]=text.encode();f[SELF]=(ROOT/SELF).read_bytes();m['build']['cpp_source']=CPP
    footer=m['steps'][0]['expected_stdout'];modes=('faults','nonabort-negative') if faults else ('normal',)
    m['steps']=[dict(name='r15-'+branch+'-framing-'+mode,argv=['{exe}']+([] if mode=='normal' else ['--framing-'+('faults' if mode=='faults' else 'nonabort-negative')]),
      expected_returncode=1 if mode=='nonabort-negative' else 0,
      validator=dict(source=SELF,function='validate',config=config(branch,mode,footer),assets={})) for mode in modes]
    id='s4-r15-compute-'+branch+'-framing-'+('faults' if faults else 'normal')+'-q1-v1'
    m['r15_framing']=dict(production_top=b['top'],generated_sha256=b['generated_sha256'],own_capture_sha256=CAPTURES[branch][1],
      production_unchanged=True,external_inputs_only=True,no_internal_state_forcing=True,framing_cases=7,
      public_abort_mask_required=True,private_canceled_tail_flush_claim=False,reset_recovery_words=7168,
      lean_removed_detector_assertions=False,promotion_allowed=False)
    m['sources']={n:sha(v) for n,v in f.items()};snapshot={n:p for n,p in m['sources'].items() if n.endswith('.sv')}
    m.update(source_root='UNBOUND',output_parent='UNBOUND',test_role='deliberate_fault' if faults else 'normal',
      rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=id.removesuffix('-q1-v1'),source_snapshot=snapshot,
      candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),rtl_ready_at_utc=m['rtl_readiness']['rtl_ready_at_utc']))
    return m,f,b,id


def freeze(branch='lean',faults=False):
    m,f,b,id=role(branch,faults);out=ROOT/'results/throughput-20260929/trackS-r15-compute-framing-native-v1'/(branch+'-'+('faults' if faults else 'normal'))
    need(not out.exists(),'R15_FRAMING_FRESH_OUTPUT');source=out/'source/fpga';source.mkdir(parents=True)
    for n,v in f.items():
        p=source/n;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as stream:stream.write(v)
    m['source_root']=str(source);dump(out/'manifest.json',m);dump(out/'production-bundle.json',b)
    return dict(id=id,manifest=str(out/'manifest.json'),status='SOURCE_NOT_NATIVE')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--branch',choices=tuple(CAPTURES),default='lean');p.add_argument('--faults',action='store_true')
    a=p.parse_args();print(json.dumps(freeze(a.branch,a.faults),indent=2))
