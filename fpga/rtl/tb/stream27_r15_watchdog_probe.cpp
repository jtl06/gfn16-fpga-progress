#include "Vstream27_r15_watchdog_probe.h"
#include "native_runtime_context_v1.h"
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
namespace {
constexpr unsigned LIMIT=20480;
void need(bool value,const char*why){if(!value)throw std::runtime_error(why);}
struct C:VerilatedContext{C(int a,char**v){gfn16_runtime::configure(*this,a,v);}};
struct H{
 C c;Vstream27_r15_watchdog_probe d;
 H(int a,char**v):c(a,v),d(&c){
  need(gfn16_runtime::matches(c,d),"R15_WATCHDOG_RUNTIME");
  unsigned n=0;for(auto const&e:std::filesystem::directory_iterator("/proc/self/task")){(void)e;n++;}
  need(n==1,"R15_WATCHDOG_OS_THREADS");reset();
 }
 void tick(){d.clk=0;d.eval();d.clk=1;c.timeInc(1);d.eval();}
 void reset(){d.clk=0;d.rst_n=0;d.new_job=d.active=d.demand=d.aux_progress=d.stop=0;
  d.completed=0;d.legacy_progress=0;tick();need(!d.error&&!d.ages&&!d.legacy_error&&!d.legacy_age,"R15_WATCHDOG_RESET");
  d.rst_n=1;tick();}
 static unsigned count(unsigned age,unsigned first,unsigned latency){
  return age<first+latency?0:(age-first-latency)/214+1;
 }
 void normal(){reset();d.active=3;
  for(unsigned edge=0;edge<=20805;edge++){
   unsigned c0=count(edge,204,215),c1=count(edge,311,215);
   unsigned s0=count(edge,204,0),s1=count(edge,311,0);
   d.completed=uint64_t(c0)|(uint64_t(c1)<<32);
   d.demand=(s0>c0?1:0)|(s1>c1?2:0);
   d.legacy_progress=edge==0||edge==325;tick();
   need(!d.error,"R15_WATCHDOG_LEGITIMATE_SQUARE_FALSE_ABORT");
  }
  need(d.legacy_error&&d.legacy_age==20479,"R15_WATCHDOG_LEGACY_SENSITIVITY");
  need(uint32_t(d.completed)==96&&uint32_t(d.completed>>32)==95,"R15_WATCHDOG_OBSERVED_COMPLETION_COUNTS");
 }
 void faults(bool peer_mutant){
  reset();d.active=d.demand=3;unsigned c0=0;
  for(unsigned edge=0;edge<LIMIT;edge++){
   bool progress=edge%31==0;if(progress)c0++;
   d.completed=c0;d.aux_progress=peer_mutant&&progress?2:0;tick();
  }
  need((d.error&2)&&!(d.error&1),"R15_WATCHDOG_CONTEXT_STALL");
  // Stop/new-job disarm age, never waive a previously sticky failure.
  d.stop=2;d.new_job=2;tick();need((d.error&2)&&!(d.ages>>15),"R15_WATCHDOG_STICKY_CANCEL_NEWJOB");
  reset();d.active=1;d.demand=0;
  for(unsigned i=0;i<LIMIT+5;i++)tick();need(!d.error&&!d.ages,"R15_WATCHDOG_LEGAL_DESCRIPTOR_GAP");
  d.demand=1;for(unsigned i=0;i<LIMIT;i++)tick();need(d.error==1,"R15_WATCHDOG_REARMED_STALL");
  reset();d.active=d.demand=1;for(unsigned i=0;i<LIMIT-1;i++)tick();
  need((d.ages&32767)==LIMIT-1,"R15_WATCHDOG_DEADLINE_AGE");
  d.completed=1;tick();need(!d.error&&!d.ages,"R15_WATCHDOG_COMPLETION_ON_DEADLINE");
  reset();d.active=d.demand=1;d.completed=7;tick();
  for(unsigned i=0;i<LIMIT-1;i++)tick();d.completed=3;tick();need(d.error==1,"R15_WATCHDOG_DECREASE_NOT_PROGRESS");
  reset();d.active=d.demand=d.stop=3;for(unsigned i=0;i<LIMIT+5;i++)tick();
  need(!d.error&&!d.ages,"R15_WATCHDOG_CANCELLED_WORK_DISARMED");
 }
};
}
int main(int argc,char**argv){try{
 H h(argc,argv);std::string mode=argc>1?argv[1]:"";
 if(mode=="--runtime-probe")return gfn16_runtime::probe(h.c,h.d);
 bool fault=mode=="--fault"||mode=="--peer-reset-mutant";
 if(fault)h.faults(mode=="--peer-reset-mutant");else h.normal();
 if(fault)std::cout<<"R15_WATCHDOG_FAULT_PASS cases=6 contexts=2 peer_cannot_hide_stall=1 gap_disarm=1 sticky_reset_only=1 runtime_threads=1\n";
 else std::cout<<"R15_WATCHDOG_NORMAL_PASS trace_age=20805 limit=20480 old_false_abort=1 completed=96/95 repaired_errors=0 runtime_threads=1 model_scope=counter_only\n";
 return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
