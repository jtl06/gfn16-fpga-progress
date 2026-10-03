// The frozen R13 normal driver supplies the signed96 reference and full56 owner
// checks. It is captured, not copied from a newer shared candidate.
#define main relay13_normal_unused_main
#include "stream27_host_contexts.cpp"
#undef main
#include <sstream>

static void reset_probe(DUT& d){
 clear(d);d.diag_fault=0;d.diag_missing_mask=0;d.rst_n=0;d.clk=0;d.eval();edge(d);
 need(!d.probe_barrier&&!d.error&&!d.probe_pending&&!d.canonical_ready&&!d.done&&!d.read_valid,
      "RELAY13_BARRIER_RESET");
 need(!d.probe_local_q&&!d.probe_field_q&&!d.probe_field_report&&!d.probe_field_stop&&!d.probe_field_copies&&!d.probe_arith_report,"RELAY13_BARRIER_RESET_ORIGINS");
 need(!d.probe_relay_slots&&!d.probe_relay_starts,"RELAY13_BARRIER_RESET_RELAY_VALID_AUTHORITY");
 d.rst_n=1;d.clk=0;d.eval();
}
static void load_start(DUT& d,bool feed=false,bool reset=true,bool defer_start=false){
 if(reset)reset_probe(d);else{clear(d);d.diag_fault=0;d.diag_missing_mask=0;}
 for(unsigned c=0;c<2;c++)for(unsigned a=0;a<N;a++){
  clear(d);d.host_context=c;d.host_addr=a;d.load_we=1;d.write_data=INITIAL[c][a];edge(d);
  need(!d.error&&!d.probe_barrier,"RELAY13_BARRIER_LOAD");
 }
 clear(d);d.start_contexts=d.batch_mode=3;d.feed_mode=feed?3:0;
 d.base=uint64_t(BASES[0])|(uint64_t(BASES[1])<<32);
 d.warm_count=uint64_t(COUNTS[0])|(uint64_t(COUNTS[1])<<32);
 for(unsigned c=0;c<2;c++)for(unsigned b=0;b<P;b++){
  d.initial_c0[c*P+b]=uint32_t(C0[c][b]);d.initial_c1[c*P+b]=uint32_t(C1[c][b]);
 }
 d.clk=0;d.eval();need(d.probe_newjob,"RELAY13_BARRIER_REAL_NEWJOB");
 if(defer_start)return;
 edge(d);need(!d.probe_pending&&!d.probe_publish_owner&&!d.error&&d.busy==3,"RELAY13_BARRIER_NEWJOB_CLEAR");
}
static void baseline(DUT& d,bool visible=false){
 d.diag_fault=0;d.diag_missing_mask=0;
 std::ostringstream output;auto* saved=std::cout.rdbuf(output.rdbuf());
 try{run(d);}catch(...){std::cout.rdbuf(saved);throw;}
 std::cout.rdbuf(saved);
 need(d.probe_proposals==2&&d.probe_drains==2&&!d.probe_pending&&!d.probe_barrier,
      "RELAY13_BARRIER_NORMAL_TWO_FENCES");
 need(d.probe_private_ready==3&&!d.probe_owned,"RELAY13_BARRIER_NORMAL_RELEASE");
 if(visible)std::cout<<output.str();
}
static void external_mask(DUT& d){
 // PRIVATE published/done are deliberately not asserted zero.
 need(d.probe_barrier&&d.probe_child_barrier,"RELAY13_BARRIER_ORIGIN_FENCE");
 need(!d.canonical_ready&&!d.done&&!d.read_valid&&!d.command_ready&&!d.command_accept&&
      !d.operation_accept&&!d.busy&&!d.waiting_final,"RELAY13_BARRIER_EXTERNAL_MASK");
 need(!d.probe_host_controls&&!d.probe_arith_controls,"RELAY13_BARRIER_CONTROL_MASK");
}
static void quiet(DUT& d,unsigned origin){
 d.diag_fault=0;
 for(unsigned k=0;k<24;k++){
  clear(d);d.read_en=d.command_valid=d.load_we=1;d.host_context=k&1;d.start_contexts=3;
  edge(d);need(d.error,"RELAY13_BARRIER_PUBLIC_REPORT_NEXT_EDGE");external_mask(d);
  if(origin<3){
   need((d.probe_field_q&(1u<<origin))&&(d.probe_field_stop&(1u<<origin))&&
        (d.probe_field_report&(1u<<origin))&&(((d.probe_field_copies>>(2*origin))&3u)==3u),
        "RELAY13_BARRIER_STICKY_FAST_REPORT_NO_STOP_REQUALIFICATION");
   need(k==0?!d.probe_arith_report:bool(d.probe_arith_report),"RELAY13_BARRIER_ARITH_REPORT_EXACT_LAG2");
  }else need(d.probe_arith_report,"RELAY13_BARRIER_LOCAL_REPORT_LAG1");
 }
}
static void seek(DUT& d,unsigned seam,unsigned origin=0){
 for(unsigned k=0;k<15000;k++){
  clear(d);d.clk=0;d.eval();need(!d.error&&!d.probe_barrier,"RELAY13_BARRIER_HEALTHY_PRE_ORIGIN");
  bool ready=seam==0?bool(d.probe_proposal):seam==1?bool(d.probe_pending):
             seam==2?bool((d.canonical_ready&1u)&&(d.busy&2u)):
             seam>=5&&seam<=7?bool(d.probe_relay_slots&(1u<<(3*(seam-5)+(origin<3?origin:0)))):false;
  if(ready){
   if(seam==1){
    need(d.probe_owned&&d.probe_publish_owner==d.probe_live_owner&&
         d.probe_publish_context==d.probe_canonical_owner,"RELAY13_BARRIER_FULL56_DRAIN_LEASE");
    constexpr uint64_t MASK=(uint64_t(1)<<(AW+1))-1;
    need((d.probe_counts&MASK)==N&&((d.probe_counts>>(AW+1))&MASK)==N&&
         ((d.probe_counts>>(2*(AW+1)))&MASK)==N,"RELAY13_BARRIER_DRAIN_COUNTS");
   }
   return;
  }
  d.clk=1;d.eval();
 }
 need(false,"RELAY13_BARRIER_ACTUAL_SEAM_NOT_FOUND");
}
static void origin_edge(DUT& d,unsigned origin){
 d.diag_fault=1u<<origin;d.clk=0;d.eval();
 need(!d.error&&!d.probe_barrier,"RELAY13_BARRIER_RAW_NOT_FORCED_REGISTER");
 d.clk=1;d.eval();
 need(!d.error,"RELAY13_BARRIER_REQUIRED_REPORT_DELAY");
 need(origin==3?bool(d.probe_local_q):bool(d.probe_field_q&(1u<<origin)),
      "RELAY13_BARRIER_ACTUAL_STICKY_ORIGIN");
 need(!d.probe_field_report&&!d.probe_field_copies&&!d.probe_arith_report,
      "RELAY13_BARRIER_REPORTS_NOT_FAST");
 if(origin<3)need(d.probe_field_stop&(1u<<origin),"RELAY13_BARRIER_STOP_ACTUAL_FAST");
 external_mask(d);
}
static void fault_case(DUT& d,unsigned origin,unsigned seam,bool mutant=false){
 if(seam==4){baseline(d);load_start(d,false,false,true);}else load_start(d,seam==3);
 if(seam<3||seam>=5)seek(d,seam,origin);
 if(seam==2){d.read_en=1;d.host_context=0;d.host_addr=17;}
 if(seam==3){
  clear(d);d.command_valid=1;d.command_context=0;d.command_index=1;d.command_generation=1;
  d.clk=0;d.eval();need(d.command_ready&&d.command_accept,"RELAY13_BARRIER_REAL_FEED_ADMISSION");
 }
 if(seam==4)need(!d.probe_pending&&d.accepted_generation==0x0101&&d.probe_newjob,
                 "RELAY13_BARRIER_NEWJOB_PRE_ORIGIN");
 d.diag_missing_mask=mutant;
 origin_edge(d,origin);
 if(seam==4)need(!d.probe_pending&&!d.probe_publish_owner&&d.accepted_generation==0x0202,
                 "RELAY13_BARRIER_ACCEPTED_NEWJOB_GENERATION");
 quiet(d,origin);baseline(d);
}
static void reset_case(DUT& d,unsigned origin){
 load_start(d);seek(d,1);d.diag_fault=1u<<origin;d.rst_n=0;d.clk=0;d.eval();edge(d);
 need(!d.probe_local_q&&!d.probe_field_q&&!d.probe_pending&&!d.probe_publish_owner&&
      !d.probe_private_ready&&!d.probe_private_done&&!d.probe_barrier&&!d.error&&
      !d.canonical_ready&&!d.done&&!d.read_valid,"RELAY13_BARRIER_RESET_WINS_ORIGIN_AND_DRAIN");
 d.diag_fault=0;d.rst_n=1;d.clk=0;d.eval();
 for(unsigned k=0;k<8;k++){clear(d);d.read_en=1;edge(d);need(!d.error&&!d.probe_barrier&&
   !d.probe_pending&&!d.canonical_ready&&!d.done&&!d.read_valid,"RELAY13_BARRIER_RESET_QUIET");}
 baseline(d);
}
static void relay_reset_case(DUT& d,unsigned origin,unsigned seam){
 load_start(d);seek(d,seam,origin);
 unsigned bit=3*(seam-5)+(origin<3?origin:0);
 need(d.probe_relay_slots&(1u<<bit),"RELAY13_BARRIER_REAL_OCCUPIED_RELAY");
 d.diag_fault=1u<<origin;d.rst_n=0;d.clk=0;d.eval();edge(d);
 need(!d.probe_relay_slots&&!d.probe_relay_starts&&!d.probe_field_q&&
      !d.probe_field_report&&!d.probe_field_copies&&!d.probe_arith_report&&!d.probe_local_q&&
      !d.probe_barrier&&!d.error&&!d.probe_pending&&!d.canonical_ready&&!d.done&&!d.read_valid,
      "RELAY13_BARRIER_OCCUPIED_RESET_WINS_ORIGIN");
 d.diag_fault=0;d.rst_n=1;d.clk=0;d.eval();
 for(unsigned k=0;k<8;k++){
  clear(d);edge(d);need(!d.probe_relay_slots&&!d.probe_relay_starts&&
   !d.probe_field_q&&!d.probe_local_q&&!d.probe_barrier&&!d.error&&!d.canonical_ready&&
   !d.done&&!d.read_valid,"RELAY13_BARRIER_RELAY_RESET_NO_STALE_AUTHORITY");
 }
 baseline(d);
}
int main(int argc,char** argv){try{
 VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d(&context);
 if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
 need(argc==2&&gfn16_runtime::matches(context,d),"RELAY13_BARRIER_ARGUMENTS_RUNTIME");
 d.diag_fault=0;d.diag_missing_mask=0;std::string mode=argv[1];
 if(mode=="--normal"){
  baseline(d,true);
  std::cout<<"RELAY13_BARRIER_NORMAL_PASS production58=1 proposals=2 drains=2 signed96_reads=1024 full56=1 copy_n_plus4=1 runtime_before_dut=1\n";
 }else if(mode=="--faults"){
  for(unsigned origin=0;origin<4;origin++){
   for(unsigned seam=0;seam<8;seam++)fault_case(d,origin,seam);
   reset_case(d,origin);
   for(unsigned seam=5;seam<8;seam++)relay_reset_case(d,origin,seam);
  }
  std::cout<<"RELAY13_BARRIER_FAULT_PASS origins=4 proposal=4 drain=4 host_read_peer=4 admission=4 accepted_newjob=4 forward_occupied=4 term_occupied=4 inverse_occupied=4 reset=16 recovered_signed96_reads=49152 field_report_lag1=24 arithmetic_report_lag2=24 host_report_lag1=32 stop_requalification_loss=0 quiet_edges=768 private_pulses_allowed=1 relay_reset_valid_kill=1\n";
 }else if(mode=="--missing-mask-negative"){
  fault_case(d,0,1,true);need(false,"RELAY13_BARRIER_MISSING_MASK_NOT_DETECTED");
 }else need(false,"RELAY13_BARRIER_MODE");
 return 0;
}catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}}
