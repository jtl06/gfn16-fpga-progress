#include "Vstream27_r15_link_reset_probe.h"
#include "native_runtime_context_v1.h"
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>

static void need(bool b,const char*s){if(!b)throw std::runtime_error(s);}
struct State{bool common,preset,creset,pready,cready,exhausted;uint32_t session;};
static State sample(const Vstream27_r15_link_reset_probe&d,bool limit){
 if(limit)return{bool(d.limit_common_reset_n),bool(d.limit_pcie_reset_n),bool(d.limit_core_reset_n),bool(d.limit_pcie_ready),bool(d.limit_core_ready),bool(d.limit_exhausted),d.limit_session};
 return{bool(d.normal_common_reset_n),bool(d.normal_pcie_reset_n),bool(d.normal_core_reset_n),bool(d.normal_pcie_ready),bool(d.normal_core_ready),bool(d.normal_exhausted),d.normal_session};
}
static void quiet(const State&s){need(!s.common&&!s.preset&&!s.creset&&!s.pready&&!s.cready,"R15_RESET_ASYNC_ASSERT_AUTHORITY");}

int main(int argc,char**argv){try{
 VerilatedContext context;gfn16_runtime::configure(context,argc,argv);
 Vstream27_r15_link_reset_probe d(&context);
 if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
 need(argc==1&&gfn16_runtime::matches(context,d),"R15_RESET_RUNTIME");
 d.pcie_clk=d.core_clk=0;d.external_reset_n=0;d.eval();
 State old[2]={sample(d,false),sample(d,true)};
 unsigned p_edges[2]={0,0},c_edges[2]={0,0};
 unsigned sessions=0,async_asserts=0,coincident=0,stopped=0,normal_ready=0,limit_ready=0;
 bool previous_reset=true,saw_exhaustion=false;
 for(unsigned tick=0;tick<1800;tick++){
  bool reset=tick<8||(tick>=181&&tick<191)||(tick>=399&&tick<411)||
   (tick>=603&&tick<619)||(tick>=901&&tick<914);
  // Assert/deassert external PERST with clocks held at their old levels first.
  // This tests actual asynchronous assertion independent of either posedge.
  d.external_reset_n=!reset;d.eval();
  if(reset){quiet(sample(d,false));quiet(sample(d,true));if(!previous_reset)async_asserts++;}
  previous_reset=reset;
  bool p=(tick%6)>=3;
  bool pause=tick<70||(tick>=399&&tick<436);
  bool c=!pause&&((tick+2)%10)>=5;
  bool pe=!d.pcie_clk&&p,ce=!d.core_clk&&c;
  if(pe&&ce)coincident++;
  d.pcie_clk=p;d.core_clk=c;d.eval();context.timeInc(1);
  for(unsigned k=0;k<2;k++){
   State s=sample(d,k!=0);
   if(!s.common||!old[k].common){p_edges[k]=0;c_edges[k]=0;}
   else{if(pe)p_edges[k]++;if(ce)c_edges[k]++;}
   if(s.session!=old[k].session){need(pe&&!old[k].common&&!reset,"R15_RESET_SESSION_EDGE_OR_LIFETIME");
    need(old[k].session!=0xffffffffu&&s.session==old[k].session+1,"R15_RESET_SESSION_WRAP");if(k==0)sessions++;}
   if(s.common&&!old[k].common){need(pe&&s.session==old[k].session+1,"R15_RESET_SESSION_NOT_ADVANCED_BEFORE_RELEASE");}
   if(s.preset&&!old[k].preset)need(pe&&p_edges[k]>=2,"R15_RESET_PCIE_RELEASE_NOT_OWN_TWO_EDGES");
   if(s.creset&&!old[k].creset)need(ce&&c_edges[k]>=2,"R15_RESET_CORE_RELEASE_NOT_OWN_TWO_EDGES");
   if(s.pready)need(s.preset&&s.creset,"R15_RESET_PCIE_READY_BEFORE_PEER");
   if(s.cready)need(s.preset&&s.creset,"R15_RESET_CORE_READY_BEFORE_PEER");
   if(s.pready&&!old[k].pready)need(pe,"R15_RESET_PCIE_READY_ASYNC_RELEASE");
   if(s.cready&&!old[k].cready)need(ce,"R15_RESET_CORE_READY_ASYNC_RELEASE");
   if(s.exhausted){quiet(s);need(s.session==0xffffffffu,"R15_RESET_EXHAUSTED_SESSION_CHANGED");if(k==1)saw_exhaustion=true;}
   if(k==0){need(!s.exhausted,"R15_RESET_PREMATURE_EXHAUSTION");if(s.pready&&s.cready)normal_ready++;}
   else if(s.pready&&s.cready)limit_ready++;
   if(pause&&s.common){need(!s.creset&&!s.cready&&!s.pready,"R15_RESET_STOPPED_PEER_AUTHORITY");if(k==0)stopped++;}
   old[k]=s;
  }
 }
 need(sessions==5&&d.normal_session==5&&async_asserts==4,"R15_RESET_SESSION_COVERAGE");
 need(normal_ready>800&&limit_ready>20&&coincident>20&&stopped>10,"R15_RESET_CLOCK_RELEASE_COVERAGE");
 need(saw_exhaustion&&d.limit_session==0xffffffffu&&d.limit_exhausted,"R15_RESET_EXHAUSTION_COVERAGE");
 std::cout<<"R15_RESET_NORMAL_PASS ticks=1800 resets=5 seeds=0/fffffffe own_domain_release=2 async_assert=1 peer_wait=1 no_wrap=1 vendor_core=0\n";
 d.final();return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
