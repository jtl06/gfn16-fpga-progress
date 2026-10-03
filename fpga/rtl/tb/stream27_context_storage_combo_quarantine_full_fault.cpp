#define main storage2_full_normal_unused_main
#include "stream27_p16_two_context_full_native.cpp"
#undef main
#include "c2_storage2_full_fault_config.h"

// Diagnostics mutate only this source's actual simulation registers. No
// production fault-injection port, delayed authority or peer recovery claim.
static void fault_reset(DUT& d){
 clear(d);d.rst_n=0;edge(d);
 need(!d.error&&!d.busy&&!d.done&&!d.canonical_ready&&!d.read_valid&&!d.feed_level,"C2_FULL_RESET_PUBLIC");
 need(!STORAGE(seed_running)&&!STORAGE(payload_reserved)&&!STORAGE(payload_ready)&&
      !STORAGE(term_producer__DOT__product_slot)&&
      !STORAGE(term_producer__DOT__context_valid)[0]&&!STORAGE(term_producer__DOT__context_valid)[1],
      "C2_FULL_RESET_VALIDITY");
 d.rst_n=1;d.clk=0;d.eval();
}
static void fault_job(DUT& d,const std::array<Image,2>& input,bool bad_base=false,bool feed=false){
 fault_reset(d);
 for(unsigned c=0;c<2;c++)for(unsigned a=0;a<N;a++){
  clear(d);d.load_we=1;d.host_context=c;d.host_addr=a;d.write_data=uint32_t(input[c][a]);edge(d);
 }
 clear(d);d.start_contexts=d.batch_mode=3;d.feed_mode=feed?3:0;
 d.base=uint64_t(bad_base?1:BASES[0])|(uint64_t(BASES[1])<<32);
 d.warm_count=uint64_t(COUNT)|(uint64_t(COUNT)<<32);
 d.double_bit=(BITS[0][0]?1u:0u)|(BITS[1][0]?2u:0u);
 d.double_mask=uint64_t(BITS[0][1]<<1)|(uint64_t(BITS[1][1]<<1)<<32);
 edge(d);if(!bad_base)need(!d.error&&d.busy==3,"C2_FULL_JOB_START");
}
static void fault_quarantine(DUT& d){
 need(d.error&&!d.busy&&!d.done&&!d.canonical_ready&&!d.read_valid,"C2_FULL_GLOBAL_ABORT");
 for(unsigned k=0;k<8;k++){
  clear(d);d.host_context=k&1;d.read_en=d.load_we=d.command_valid=1;d.start_contexts=3;
  edge(d);need(d.error&&!d.busy&&!d.done&&!d.canonical_ready&&!d.read_valid&&!d.command_accept,
               "C2_FULL_STICKY_NO_PUBLICATION");
 }
}
static uint64_t recover(DUT& d,const std::array<Image,2>& input,const std::array<Image,2>& reference){
 Result result=run(d,3,input,reference);
 need(result.reads==4*N&&result.peer_reads==N,"C2_FULL_RECOVERY_READS");return result.reads;
}
static void external(DUT& d,const std::array<Image,2>& input){
 fault_job(d,input,true);fault_quarantine(d);
 for(unsigned mode=0;mode<2;mode++){
  fault_job(d,input,false,true);clear(d);d.command_valid=1;d.command_context=0;
  d.command_index=mode?65537:1;d.command_generation=mode?1:2;
  edge(d);fault_quarantine(d);
 }
 std::cout<<"C2_STORAGE_FULL_EXTERNAL_PASS bad_base=1 stale_generation=1 full32_index=1 global_abort=3 peer_recovery=0\n";
}
static void owners(DUT& d,const std::array<Image,2>& input,const std::array<Image,2>& reference){
 const unsigned corrupt_bits[4]={25,24,23,7};
 recover(d,input,reference); // Native normal baseline before mutations.
 for(unsigned mode=0;mode<4;mode++){
  fault_job(d,input);bool injected=false,failed=false;
  for(unsigned age=1;age<2*INTERVAL+CARRY_DONE;age++){
   clear(d);d.clk=0;d.eval();need(!d.done&&!d.canonical_ready&&!d.read_valid,"C2_FULL_OWNER_NO_PUBLICATION");
   if(!injected&&(STORAGE(payload_ready)&1u)){
    auto& key=STORAGE(payload_owner)[0];
    need((STORAGE(payload_reserved)&1u)&&!(key&(1u<<24)),"C2_FULL_OWNER_REAL_KEY");
    key^=1u<<corrupt_bits[mode];injected=true;d.eval();
   }
   d.clk=1;d.eval();if(d.error){failed=true;break;}
  }
  need(injected&&failed,"C2_FULL_OWNER_REJECTION");fault_quarantine(d);
 }
 recover(d,input,reference);
 std::cout<<"C2_STORAGE_FULL_OWNER_PASS mutants=4 full27=1 bank_context_epoch_generation=1 publication=0 baseline_reads=262144 recovered_reads=262144 simulation_only=1\n";
}
static void resets(DUT& d,const std::array<Image,2>& input,const std::array<Image,2>& reference){
 uint64_t reads=0;
 for(unsigned mode=0;mode<3;mode++){
  fault_job(d,input);bool found=false;
  for(unsigned age=1;age<2*INTERVAL+CARRY_DONE;age++){
   clear(d);d.clk=0;d.eval();need(!d.error&&!d.done&&!d.canonical_ready,"C2_FULL_RESET_PRE_NORMAL");
   bool event=mode==0?bool(STORAGE(seed_running)):mode==1?bool(STORAGE(fwd_slot)):
    bool(STORAGE(fwd_slot)&&STORAGE(protocol_pw_row)==T-1&&STORAGE(term_producer__DOT__product_slot));
   if(event){found=true;fault_reset(d);break;}d.clk=1;d.eval();
  }
  need(found,"C2_FULL_RESET_ACTUAL_EVENT");
  for(unsigned k=0;k<8;k++){
   clear(d);d.read_en=1;edge(d);need(!d.error&&!d.busy&&!d.done&&!d.canonical_ready&&!d.read_valid&&
    !STORAGE(payload_ready)&&!STORAGE(term_producer__DOT__product_slot),"C2_FULL_RESET_QUIET_TAIL");
  }
  reads+=recover(d,input,reference);
 }
 need(reads==12*N,"C2_FULL_RESET_RECOVERY_COUNT");
 std::cout<<"C2_STORAGE_FULL_RESET_PASS seed=1 pointwise=1 last_read_e4=1 quiet_edges=24 recovered_reads=786432 epoch_wrap=0\n";
}
static void ordinal(DUT& d,const std::array<Image,2>& input,const std::array<Image,2>& reference){
 recover(d,input,reference);
 fault_job(d,input);bool injected=false,origin=false;
 for(unsigned age=1;age<2*INTERVAL+CARRY_DONE;age++){
  clear(d);d.clk=0;d.eval();
  need(!d.error&&!d.done&&!d.canonical_ready&&!d.read_valid,"C2_FULL_ORDINAL_PRE_NORMAL");
  if(!injected&&lane32(d.operations_started,0)>=1&&lane32(d.operations_started,1)>=1){
   need(HOST(job_count)[0]==COUNT,"C2_FULL_ORDINAL_ACTUAL_COUNT");
   HOST(job_count)[0]+=65536;injected=true;d.eval();
  }
  const bool bad=HOST(capture_bad);
  if(bad){need(injected&&!d.final_image_rows,"C2_FULL_ORDINAL_ORIGIN_BEFORE_CAPTURE");origin=true;}
  d.clk=1;d.eval();
  if(origin){need(d.error,"C2_FULL_ORDINAL_SAME_EDGE_FAULT");break;}
  need(!d.error,"C2_FULL_ORDINAL_NO_UNRELATED_FAULT");
 }
 need(injected&&origin,"C2_FULL_ORDINAL_FULL56_CAPTURE_REJECT");fault_quarantine(d);
 recover(d,input,reference);
 std::cout<<"C2_STORAGE_FULL_ORDINAL_PASS alias_delta=65536 low16_epoch_same=1 full56=1 capture_bad_origin=1 same_edge_error=1 publication=0 baseline_reads=262144 recovered_reads=262144 simulation_only=1\n";
}
static void early_cache(DUT& d,const std::array<Image,2>& input){
 fault_job(d,input);bool failed=false,observed=false;
 for(unsigned age=1;age<1000;age++){
  clear(d);d.clk=0;d.eval();
  if(STORAGE(seed_running)&&STORAGE(term_cache_ready)&&!observed){
   need(!STORAGE(term_producer__DOT__product_slot),"C2_FULL_EARLY_CACHE_ACTUAL_PREMATURE_TOKEN");observed=true;
  }
  d.clk=1;d.eval();need(!d.done&&!d.canonical_ready&&!d.read_valid,"C2_FULL_EARLY_CACHE_NO_PUBLICATION");
  if(d.error){failed=true;break;}
 }
 need(observed&&failed,"C2_FULL_EARLY_CACHE_NOT_DETECTED");fault_quarantine(d);
 std::cout<<"C2_STORAGE_FULL_EARLY_CACHE_PASS seed_start_token=1 premature_cache_rejected=1 publication=0 simulation_only=1\n";
}
int main(int argc,char** argv){try{
 VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d{&context};
 if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
 need(argc==2&&gfn16_runtime::matches(context,d),"C2_FULL_FAULT_ARGUMENTS_THREADS");
 std::array<Image,2> input={initial(0),initial(1)},reference=input;
 std::string mode=argv[1];
 if(mode=="--external"){external(d,input);return 0;}
 if(mode=="--early-cache"){early_cache(d,input);return 0;}
 s4_full_reference::self_check();
 for(unsigned c=0;c<2;c++)for(unsigned k=0;k<COUNT;k++)reference[c]=s4_full_reference::square(reference[c],BASES[c],BITS[c][k]);
 need(reference[0]!=reference[1]&&reference[0][0]!=-1&&reference[1][0]!=-1,"C2_FULL_DISTINCT_REFERENCE");
 if(mode=="--owner")owners(d,input,reference);else if(mode=="--reset")resets(d,input,reference);
 else if(mode=="--ordinal")ordinal(d,input,reference);
 else if(mode=="--oracle"){reference[0][0]^=1;run(d,3,input,reference);need(false,"C2_FULL_WRONG_WORD_NOT_DETECTED");}
 else need(false,"C2_FULL_FAULT_MODE");return 0;
}catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}}
