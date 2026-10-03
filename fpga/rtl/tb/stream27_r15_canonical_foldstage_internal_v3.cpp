// Additive simulation-only FF sampling fix; v2 late-mutation failure retained.
#define main foldstage_original_main
#include "stream27_r15_canonical_foldstage.cpp"
#undef main
#include "Vgenefer_stream27_r15_canonical_foldstage_pair_v1___024root.h"
#define OLD(x) r->genefer_stream27_r15_canonical_foldstage_pair_v1__DOT__parent_dut__DOT__ ## x
#define NEW(x) r->genefer_stream27_r15_canonical_foldstage_pair_v1__DOT__local_dut__DOT__ ## x

int main(int argc,char** argv){try{
 H h(argc,argv);auto* r=h.d.rootp;
 if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(h.context,h.d);
 need(argc==1,"FOLDSTAGE_INTERNAL_ARGUMENTS");Image zero(N),q(P);unsigned cases=0;
 for(int32_t correction:{int32_t(3*MINBASE),-int32_t(3*MINBASE),INT32_MIN,INT32_MAX}){
  h.reset();h.load(zero,MINBASE);h.begin(MINBASE,q,q);
  need(OLD(state)==1&&NEW(state)==1,"FOLDSTAGE_INTERNAL_ACTUAL_READ_PHASE");
  // Direct writes to public FFs are not HDL events. The generated old fold
  // expression is NBA-combinational; READ must settle the injected value
  // before VALUE samples it. Inject after real accepted BEGIN/before READ,
  // not after READ immediately before the VALUE sampling edge as failed v2.
  OLD(correction0)[0]=uint32_t(correction);NEW(correction0)[0]=uint32_t(correction);
  h.edge();need(OLD(state)==2&&NEW(state)==2,"FOLDSTAGE_INTERNAL_VALUE_PHASE");
  const uint64_t mask=(1ull<<34)-1;
  const uint64_t expected_value=uint64_t(int64_t(correction))&mask;
  const uint64_t expected_remainder=uint64_t(int64_t(correction)+(correction<0?2ll*MINBASE:-2ll*MINBASE))&mask;
  const unsigned expected_q=correction<0?6u:2u;
  auto check=[&](bool ok,const char* why,unsigned age){if(!ok){
    std::cerr<<"FOLDSTAGE_INTERNAL_TRACE q="<<correction<<" age="<<age
      <<" states="<<unsigned(OLD(state))<<","<<unsigned(NEW(state))
      <<" errors="<<unsigned(h.d.parent_error)<<","<<unsigned(h.d.local_error)
      <<" qpayload="<<unsigned(OLD(fold_q_payload))<<","<<unsigned(NEW(fold_q_payload))
      <<" range="<<unsigned(OLD(fold_range_payload))<<","<<unsigned(NEW(fold_range_payload))
      <<" value="<<NEW(value)<<" expected="<<expected_value<<"\n";
    throw std::runtime_error(why);}};
  for(unsigned age=2;age<=4;++age){h.edge();
   check(OLD(correction0)[0]==uint32_t(correction)&&NEW(correction0)[0]==uint32_t(correction),"FOLDSTAGE_INTERNAL_STORED_FF_PERSIST",age);
   check(!OLD(stored_digit_bad)&&!NEW(stored_digit_bad),"FOLDSTAGE_INTERNAL_NOT_DIGIT",age);
   if(age==2)check(OLD(state)==3&&NEW(state)==6&&NEW(value)==expected_value&&
       OLD(fold_q_payload)==expected_q&&OLD(fold_remainder_payload)==expected_remainder&&OLD(fold_range_payload),
       "FOLDSTAGE_INTERNAL_VALUE_TOKEN",age);
   if(age==3)check(NEW(state)==3&&NEW(fold_q_payload)==expected_q&&NEW(fold_remainder_payload)==expected_remainder&&NEW(fold_range_payload),
       "FOLDSTAGE_INTERNAL_FOLD_TOKEN",age);
   check(bool(h.d.parent_error)==(age>=3)&&bool(h.d.local_error)==(age>=4),"FOLDSTAGE_INTERNAL_PROCESS_ORIGIN",age);
   if(age>=3)check(h.d.parent_error_code==7,"FOLDSTAGE_PARENT_INTERNAL_CODE",age);
   if(age>=4)check(h.d.local_error_code==7,"FOLDSTAGE_LOCAL_INTERNAL_CODE",age);
  }h.sticky(7);++cases;
 }
 h.image(pattern(MINBASE),MINBASE,q,q);need(cases==4&&h.reads==N,"FOLDSTAGE_INTERNAL_COUNTS");
 std::cout<<"R15_FOLDSTAGE_INTERNAL_FF_V3_PASS aw="<<AW<<" cases=4 signed_extrema=1 code=7 parent_origin=3 candidate_origin=4 recovery_reads="
  <<N<<" injected_before_READ=1 actual_value_fold_tokens=1 production_mutated=0 simulation_only=1 runtime_threads=1\n";
 return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
