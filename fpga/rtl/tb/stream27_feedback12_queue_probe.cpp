// Native-only retained descriptor-authority seam; not a GL fault guarantee.
#include "s4_p16_two_context_full_config.h"
#include "native_runtime_context_v1.h"
#include "verilated.h"
#include <string>
struct QueuedFaultObserved {};
static unsigned queued_fault_mode=0;
static bool queued_injected=false;
template<class T> static void queued_inject(T& d);
template<class T> static void queued_observe(T& d);
#define main r12_queue_driver_unused_main
#include "stream27_feedback12_queue_driver.cpp"
#undef main
#include "r12_queue_probe_config.h"

template<class T> static void queued_inject(T& d){
 if(!queued_fault_mode || queued_injected || !d.probe_queue_needed)return;
 need(!d.probe_queue_bad&&!d.error&&!d.probe_stop&&!d.canonical_ready&&!d.done,
      "R12_QUEUE_ACTUAL_HEALTHY_CAPTURE");
 // Mutate only one captured descriptor-authority bit, not payload/owner/error.
 if(queued_fault_mode==1)QUEUED_INDEX^=1u;else QUEUED_GENERATION^=1u;
 queued_injected=true;
 // A harmless unpublished read-input toggle makes combinational evaluation
 // explicit after a simulation-only internal-register write.
 auto prior=d.read_en;d.read_en=!prior;d.eval();d.read_en=prior;d.eval();
 need(d.probe_queue_bad&&!d.operation_accept&&!d.canonical_ready&&!d.done,
      "R12_QUEUE_PRE_ACCEPT_RECHECK");
}

template<class T> static void queued_observe(T& d){
 if(!queued_injected)return;
 // Literal engine local_error/error_barrier assert at this accepted clock.
 need(d.error&&d.probe_stop&&!d.busy&&!d.done&&!d.canonical_ready&&!d.read_valid&&
      !d.command_accept,"R12_QUEUE_ORIGIN_PUBLIC_FENCE");
 for(unsigned k=0;k<8;k++){
  clear(d);d.read_en=1;d.host_context=k&1;d.start_contexts=3;d.load_we=1;edge(d);
  need(d.error&&d.probe_stop&&!d.busy&&!d.done&&!d.canonical_ready&&!d.read_valid&&
       !d.command_accept,"R12_QUEUE_STICKY_PUBLIC_FENCE");
 }
 // Existing occupied raw tails are not asserted empty; reset is the flush.
 throw QueuedFaultObserved{};
}

int main(int argc,char**argv){try{
 VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d{&context};
 if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
 const bool faults=argc==2&&std::string(argv[1])=="--faults";
 const bool wrong=argc==2&&std::string(argv[1])=="--wrong-reference";
 need((argc==1||faults||wrong)&&gfn16_runtime::matches(context,d),"R12_QUEUE_ARGUMENTS_THREADS");
 s4_full_reference::self_check();
 std::array<Image,2> input={initial(0),initial(1)},reference=input;
 for(unsigned c=0;c<2;c++)for(unsigned k=0;k<COUNT;k++)
  reference[c]=s4_full_reference::square(reference[c],BASES[c],BITS[c][k]);
 if(wrong)reference[0][0]^=1;
 if(!faults){
  Result result=run(d,3,input,reference);
  need(result.reads==4*N&&result.peer_reads==N&&result.descriptors==2*(COUNT-1),
       "R12_QUEUE_NORMAL_ALL_WORDS");
  std::cout<<"R12_QUEUE_NORMAL_PASS squares=200 signed96_reads=262144 independent_reference=1\n";
 }else{
  uint64_t reads=0;
  for(unsigned mode=1;mode<=2;mode++){
   queued_fault_mode=mode;queued_injected=false;bool caught=false;
   try{run(d,3,input,reference);}catch(const QueuedFaultObserved&){caught=true;}
   need(caught&&queued_injected,"R12_QUEUE_MUTATION_NOT_SENSITIVE");
   queued_fault_mode=0;queued_injected=false;
   clear(d);d.rst_n=0;edge(d);
   need(!d.error&&!d.probe_stop&&!d.probe_queue_needed&&!d.busy&&!d.done&&!d.read_valid&&
        !d.canonical_ready,"R12_QUEUE_RESET_PUBLIC_AUTHORITY");
   Result recovered=run(d,3,input,reference);
   need(recovered.reads==4*N&&recovered.peer_reads==N,"R12_QUEUE_RESET_RECOVERY_WORDS");
   reads+=recovered.reads;
  }
  need(reads==8*N,"R12_QUEUE_BOTH_RECOVERY_COUNTS");
  std::cout<<"R12_QUEUE_FAULT_PASS cases=2 index=1 generation=1 pre_accept_recheck=1 quiet_edges=16 recovered_signed96_reads=524288 simulation_only=1 host_gl_unimplemented=1\n";
 }
 d.final();return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
