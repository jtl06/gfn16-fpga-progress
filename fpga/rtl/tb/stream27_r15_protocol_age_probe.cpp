#include "Vstream27_r15_protocol_age_probe.h"
#include "native_runtime_context_v1.h"
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>

static void need(bool b,const char*s){if(!b)throw std::runtime_error(s);}
struct Bench{
 VerilatedContext context;Vstream27_r15_protocol_age_probe *p;
 unsigned wraps=0,accepts=0,corrections=0,pw=0,commits=0;
 Bench(int argc,char**argv){gfn16_runtime::configure(context,argc,argv);p=new Vstream27_r15_protocol_age_probe(&context);}
 ~Bench(){p->final();delete p;}
 auto& d(){return *p;}
 void check(){
  for(unsigned j=0;j<4;j++)need(p->old0[j]==p->new0[j]&&p->oldhi[j]==p->newhi[j],"R15_AGE_NATIVE_EQUIVALENCE");
  need(p->invariant0&&p->invarianthi,"R15_AGE_NATIVE_EQUIVALENCE");
 }
 void step(){
  p->clk=0;p->eval();check();
  accepts+=p->old_frame_accept;corrections+=p->old_correction_accept;
  pw+=p->old_pointwise_accept;commits+=p->old_commit_enable;
  auto before=p->high_cycle;
  p->clk=1;p->eval();context.timeInc(1);check();
  if(p->rst_n&&p->high_cycle<before)wraps++;
  p->clk=0;p->eval();check();
 }
 void reset(){
  p->clk=0;p->rst_n=0;p->frame_begin=p->correction_valid=p->cache_ready=0;
  p->pointwise_slot=p->pointwise_frame_start=p->sink_slot=p->sink_frame_start=0;
  p->frame_context=p->correction_context=p->cache_context=p->pointwise_context=p->sink_context=0;
  p->frame_epoch=p->correction_epoch=p->cache_epoch=p->pointwise_epoch_in=p->sink_epoch_in=0;
  p->frame_generation=p->correction_generation=p->cache_generation=p->pointwise_generation=p->sink_generation=1;
  p->frame_base=1009;p->context_enabled=3;p->live_generation=0x0101;
  p->external_fault_pending=0;p->fault_report_copies=0;p->eval();step();p->rst_n=1;p->eval();check();
 }
 void drive(unsigned tick,unsigned frames,bool cancel_peer=false){
  auto&d=*p;d.frame_begin=d.correction_valid=d.cache_ready=0;
  d.pointwise_slot=d.pointwise_frame_start=d.sink_slot=d.sink_frame_start=0;
  d.external_fault_pending=0;d.fault_report_copies=0;d.context_enabled=3;d.live_generation=0x0101;
  for(unsigned k=0;k<frames;k++)for(unsigned ctx=0;ctx<2;ctx++){
   unsigned a=240*k+37*ctx;uint16_t epoch=uint16_t((ctx?42:65534)+k);
   if(tick==a){d.frame_begin=1;d.frame_context=ctx;d.frame_epoch=epoch;d.frame_generation=1;d.frame_base=ctx?99991:1009;
    d.correction_valid=1;d.correction_context=ctx;d.correction_epoch=epoch;d.correction_generation=1;}
   if(tick==a+1){d.cache_ready=1;d.cache_context=ctx;d.cache_epoch=epoch;d.cache_generation=1;}
   if(tick>=a+79&&tick<a+95){d.pointwise_slot=1;d.pointwise_frame_start=tick==a+79;
    d.pointwise_context=ctx;d.pointwise_epoch_in=epoch;d.pointwise_generation=1;}
   if(tick>=a+153&&tick<a+169){d.sink_slot=1;d.sink_frame_start=tick==a+153;
    d.sink_context=ctx;d.sink_epoch_in=epoch;d.sink_generation=1;
    if(ctx&&cancel_peer){d.context_enabled=1;d.live_generation=0x0201;}}
  }
 }
};

int main(int argc,char**argv){try{
 Bench b(argc,argv);auto&d=b.d();
 if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(b.context,d);
 need(gfn16_runtime::matches(b.context,d),"R15_AGE_NATIVE_RUNTIME");
 const bool faults=argc==2&&std::string(argv[1])=="--faults";need(argc==1||faults,"R15_AGE_NATIVE_ARGS");
 if(!faults){
  b.reset();for(unsigned t=0;t<720;t++){b.drive(t,3,true);need(!d.old_error,"R15_AGE_NORMAL_ERROR");b.step();}
  need(b.accepts==6&&b.corrections==6&&b.pw==96&&b.commits==48,"R15_AGE_NORMAL_ACCEPT_COUNTS");
  need(d.old_owner_count==0&&b.wraps==1,"R15_AGE_RAW_CANCELED_RETIRE_OR_U32_WRAP");
  // Reallocation after a populated reset initializes age data independently
  // of reset-free stale q bits. This is a new sequence, not clock forcing.
  b.reset();for(unsigned t=0;t<210;t++){b.drive(t,1);b.step();}
  need(!d.old_error&&d.old_owner_count==0&&b.wraps==2&&b.accepts==8&&b.corrections==8&&b.pw==128&&b.commits==80,"R15_AGE_RESET_REALLOCATION");
  std::cout<<"R15_AGE_COMPONENT_NORMAL_PASS frames=8 pointwise=128 commits=80 modulo32_reset_seed=1 canceled_raw_retire=1 reset_reallocate=1 native_billions=0\n";
 }else{
  for(unsigned kind=0;kind<2;kind++){
   b.reset();bool saw=false;
   for(unsigned t=0;t<210;t++){
    b.drive(t,1);
    if(kind==0&&t==30)d.external_fault_pending=1;
    if(kind==1&&t==79)d.pointwise_generation=2;
    if(saw)d.fault_report_copies=1;
    b.step();saw=saw||d.old_error;
    if(saw){need(!d.old_frame_accept&&!d.old_correction_accept&&!d.old_pointwise_accept&&!d.old_commit_enable,"R15_AGE_STOP_AUTHORITY");}
   }
   need(saw&&d.old_error&&d.old_owner_count==(kind==0?1:2),"R15_AGE_STOP_OCCUPANCY");
  }
  b.reset();for(unsigned t=0;t<210;t++){b.drive(t,1);b.step();}
  need(!d.old_error&&d.old_owner_count==0,"R15_AGE_FAULT_RESET_RECOVERY");
  std::cout<<"R15_AGE_COMPONENT_FAULT_PASS origins=2 stop_advances=1 report_copy=1 reset_recovery=1 tuple_authority=1 native_billions=0\n";
 }
 return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
