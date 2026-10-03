// Additive simulation-only stored-correction sensitivity, not production ports.
#define main foldstage_original_main
#include "stream27_r15_canonical_foldstage.cpp"
#undef main
#include "Vgenefer_stream27_r15_canonical_foldstage_pair_v1___024root.h"

int main(int argc,char** argv){try{
 H h(argc,argv);
 if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(h.context,h.d);
 need(argc==1,"FOLDSTAGE_INTERNAL_ARGUMENTS");
 Image zero(N),q(P);unsigned cases=0;
 for(int32_t correction:{int32_t(3*MINBASE),-int32_t(3*MINBASE),INT32_MIN,INT32_MAX}){
  h.reset();h.load(zero,MINBASE);h.begin(MINBASE,q,q);h.edge();
  auto* r=h.d.rootp;
  need(r->genefer_stream27_r15_canonical_foldstage_pair_v1__DOT__parent_dut__DOT__state==2&&
       r->genefer_stream27_r15_canonical_foldstage_pair_v1__DOT__local_dut__DOT__state==2,
       "FOLDSTAGE_INTERNAL_ACTUAL_VALUE_PHASE");
  // Actual generated names inspected from OWN compiled normal header. Both
  // accepted BEGIN snapshots were zero. Inject identical stored FF error
  // after BEGIN/READ and before VALUE; never mutate range/state/public outputs.
  r->genefer_stream27_r15_canonical_foldstage_pair_v1__DOT__parent_dut__DOT__correction0[0]=uint32_t(correction);
  r->genefer_stream27_r15_canonical_foldstage_pair_v1__DOT__local_dut__DOT__correction0[0]=uint32_t(correction);
  h.d.eval();
  for(unsigned age=2;age<=4;++age){h.edge();
   need(!r->genefer_stream27_r15_canonical_foldstage_pair_v1__DOT__parent_dut__DOT__stored_digit_bad&&
        !r->genefer_stream27_r15_canonical_foldstage_pair_v1__DOT__local_dut__DOT__stored_digit_bad,
        "FOLDSTAGE_INTERNAL_NOT_DIGIT_FAULT");
   need(bool(h.d.parent_error)==(age>=3)&&bool(h.d.local_error)==(age>=4),"FOLDSTAGE_INTERNAL_PROCESS_ORIGIN");
   if(age>=3)need(h.d.parent_error_code==7,"FOLDSTAGE_PARENT_INTERNAL_CODE");
   if(age>=4)need(h.d.local_error_code==7,"FOLDSTAGE_LOCAL_INTERNAL_CODE");
  }h.sticky(7);++cases;
 }
 h.image(pattern(MINBASE),MINBASE,q,q);
 need(cases==4&&h.reads==N,"FOLDSTAGE_INTERNAL_COUNTS");
 std::cout<<"R15_FOLDSTAGE_INTERNAL_FF_PASS aw="<<AW<<" cases=4 signed_extrema=1 code=7 parent_origin=3 candidate_origin=4 recovery_reads="
  <<N<<" production_mutated=0 simulation_only=1 runtime_threads=1\n";
 return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
