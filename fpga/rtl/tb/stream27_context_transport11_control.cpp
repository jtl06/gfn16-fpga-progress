// Native-only R11 reset and real watchdog-fault quarantine seams.
// Numeric payload may remain dirty: only occupied/start authority resets.
#define main r11_full_normal_unused_main
#include "stream27_p16_two_context_full_native.cpp"
#undef main
#include "r11_transport_control_config.h"

static void job(DUT& d,const std::array<Image,2>& input){
 clear(d);d.rst_n=0;edge(d);
 need(!d.probe_slots&&!d.probe_starts&&!d.error&&!d.busy&&!d.done&&!d.read_valid&&
      !d.canonical_ready&&!d.probe_sent&&!d.probe_pending,"R11_CONTROL_RESET_VALID_AUTHORITY");
 d.rst_n=1;clear(d);edge(d);
 for(unsigned c=0;c<2;c++)for(unsigned a=0;a<N;a++){
  clear(d);d.load_we=1;d.host_context=c;d.host_addr=a;d.write_data=uint32_t(input[c][a]);edge(d);
 }
 clear(d);d.start_contexts=d.batch_mode=3;
 d.base=uint64_t(BASES[0])|(uint64_t(BASES[1])<<32);
 d.warm_count=uint64_t(COUNT)|(uint64_t(COUNT)<<32);
 d.double_bit=(BITS[0][0]?1u:0u)|(BITS[1][0]?2u:0u);
 d.double_mask=uint64_t(BITS[0][1]<<1)|(uint64_t(BITS[1][1]<<1)<<32);
 edge(d);need(d.busy==3&&!d.error&&!d.canonical_ready&&!d.done,"R11_CONTROL_JOB_START");
}

static void reset_seam(DUT& d,unsigned mode,const std::array<Image,2>& input){
 job(d,input);bool found=false;
 // The lowest field0 bits are term JOIN, inverse ingress, then common CRT.
 const unsigned bit=mode==0?0:mode==1?1:6;
 for(unsigned age=1;age<2*INTERVAL+CARRY_DONE;age++){
  clear(d);d.clk=0;d.eval();
  need(!d.error&&!d.done&&!d.canonical_ready&&!d.read_valid,"R11_CONTROL_RESET_PRE_HEALTHY");
  if(d.probe_slots&(1u<<bit)){
   found=true;d.rst_n=0;d.eval();
   need(!d.probe_slots&&!d.probe_starts,"R11_CONTROL_ASYNC_SLOT_START_CLEAR");
   edge(d);need(!d.error&&!d.busy&&!d.done&&!d.canonical_ready&&!d.read_valid&&
        !d.probe_sent&&!d.probe_pending,"R11_CONTROL_RESET_PUBLIC");
   d.rst_n=1;break;
  }
  d.clk=1;d.eval();
 }
 need(found,"R11_CONTROL_ACTUAL_OCCUPIED_EVENT");
 for(unsigned k=0;k<8;k++){
  clear(d);d.read_en=1;d.host_context=k&1;edge(d);
  need(!d.error&&!d.busy&&!d.done&&!d.read_valid&&!d.canonical_ready&&
       !d.probe_slots&&!d.probe_starts,"R11_CONTROL_RESET_NO_STALE_TAIL");
 }
}

static void watchdog_expiry(DUT& d,const std::array<Image,2>& input){
 job(d,input);bool injected=false;
 for(unsigned age=1;age<2*INTERVAL+CARRY_DONE;age++){
  clear(d);d.clk=0;d.eval();
  need(!d.error&&!d.done&&!d.canonical_ready&&!d.read_valid,"R11_CONTROL_FAULT_PRE_HEALTHY");
  if((d.probe_slots&(1u<<6))&&!d.probe_progress){
   // Accelerate ONLY the real watchdog's age, never payload/error/owner/valid.
   WATCHDOG_AGE=64*N+4096-1;injected=true;d.eval();d.clk=1;d.eval();
   // Private phases may remain; public BUSY is explicitly safety-masked.
   need(d.error&&d.probe_stop&&!d.busy&&!d.done&&!d.canonical_ready&&!d.read_valid,
        "R11_CONTROL_REAL_WATCHDOG_FAULT_PUBLIC_KILL");
   break;
  }
  d.clk=1;d.eval();
 }
 need(injected,"R11_CONTROL_FAULT_AT_ACTUAL_CRT_TUPLE");
 for(unsigned k=0;k<8;k++){
  clear(d);d.read_en=1;d.host_context=k&1;d.start_contexts=3;d.load_we=1;
  edge(d);need(d.error&&d.probe_stop&&!d.busy&&!d.done&&!d.canonical_ready&&!d.read_valid&&
       !d.command_accept&&!d.probe_slots&&!d.probe_starts,
       "R11_CONTROL_QUARANTINE_NO_PUBLICATION_OR_STALE_TUPLE");
 }
}

int main(int argc,char**argv){try{
 VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d{&context};
 if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
 need((argc==1||(argc==2&&std::string(argv[1])=="--wrong-reference"))&&
      gfn16_runtime::matches(context,d),"R11_CONTROL_ARGUMENTS_THREADS");
 s4_full_reference::self_check();
 std::array<Image,2> input={initial(0),initial(1)},reference=input;
 for(unsigned c=0;c<2;c++)for(unsigned k=0;k<COUNT;k++)
  reference[c]=s4_full_reference::square(reference[c],BASES[c],BITS[c][k]);
 if(argc==2){reference[0][0]^=1;run(d,3,input,reference);need(false,"R11_CONTROL_ORACLE_NOT_SENSITIVE");}
 uint64_t reads=0;
 for(unsigned mode=0;mode<4;mode++){
  if(mode<3)reset_seam(d,mode,input);else watchdog_expiry(d,input);
  Result recovered=run(d,3,input,reference);
  need(recovered.reads==4*N&&recovered.peer_reads==N,"R11_CONTROL_FULL_RECOVERY");
  reads+=recovered.reads;
 }
 need(reads==16*N,"R11_CONTROL_RECOVERY_READ_COUNT");
 std::cout<<"R11_TRANSPORT_CONTROL_PASS reset_events=3 watchdog_expiry=1 quiet_edges=32 recovered_reads=1048576 signed96=1 own_reference=1 payload_zero_assumed=0 host_gl_assumed=1 simulation_only=1\n";
 d.final();return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
