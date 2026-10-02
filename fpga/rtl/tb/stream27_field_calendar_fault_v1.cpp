#include "s4_calendar_fault_config_v1.h"
#include "verilated.h"
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
static void need(bool ok,const std::string& label){if(!ok)throw std::runtime_error(label);}
static void clear(DUT& d){
 d.in_slot_valid=0;d.frame_start=0;d.correction_valid=0;d.context_enabled=1;
 d.generation_in=7;d.live_generation=7;d.base_in=1000000000;
 d.epoch_in=0;d.correction_epoch=0;d.correction_generation=7;d.debug_drop_forward=0;
 for(unsigned j=0;j<P;++j){d.data_in[j]=0;d.c0_in[j]=0;d.c1_in[j]=0;}
}
static void edge(DUT& d){d.clk=0;d.eval();d.clk=1;d.eval();d.clk=0;d.eval();}
static void reset(DUT& d){clear(d);d.rst_n=0;edge(d);need(!d.out_error&&!d.out_slot_valid&&!d.commit_valid&&!d.owner_count,"S4_CALENDAR_RESET");d.rst_n=1;d.eval();}
static unsigned run(DUT& d,bool drop,bool negative){
 reset(d);unsigned physical=0,commits=0;
 for(unsigned tick=0;tick<SINK+T+3;++tick){
  clear(d);d.debug_drop_forward=drop;
  if(tick<T){d.in_slot_valid=1;d.frame_start=tick==0;}
  if(tick==0)d.correction_valid=1;
  d.clk=0;d.eval();
  if(tick==0)need(d.frame_accept&&d.correction_accept,"S4_CALENDAR_REAL_LEASE_ACCEPT");
  if(drop){
   need(!d.out_slot_valid&&!d.commit_valid,"S4_CALENDAR_NO_FALSE_DATA");
   if(tick<POINTWISE)need(!d.fault_pending&&!d.out_error,"S4_CALENDAR_NO_EARLY_CT_FAULT");
   if(tick==POINTWISE){
    need(d.fault_pending&&!d.out_error&&d.owner_count==1,"S4_CALENDAR_MISSING_FIRST_ORIGIN");
    edge(d);need(d.out_error,"S4_CALENDAR_REGISTERED_MISSING_FIRST");
    clear(d);d.in_slot_valid=1;d.frame_start=1;d.epoch_in=1;d.correction_epoch=1;d.correction_valid=1;d.eval();
    need(!d.frame_accept&&!d.correction_accept&&!d.out_slot_valid&&!d.commit_valid,"S4_CALENDAR_FAULT_QUARANTINE");
    if(negative)throw std::runtime_error("S4_CALENDAR_TYPED expected="+std::to_string(POINTWISE+1)+" actual="+std::to_string(tick));
    return tick;
   }
  }else{
   need(!d.fault_pending&&!d.out_error,"S4_CALENDAR_UNMODIFIED_NORMAL");
   if(d.out_slot_valid){++physical;need(tick>=PHYSICAL&&tick<PHYSICAL+T,"S4_CALENDAR_PHYSICAL_ORDER");
    for(unsigned j=0;j<(P*27+31)/32;++j)need(d.data_out[j]==0,"S4_CALENDAR_ZERO_ARITHMETIC");}
   if(d.commit_valid)++commits;
  }
  edge(d);
 }
 need(!drop&&physical==T&&commits==T,"S4_CALENDAR_NORMAL_COUNTS");return 0;
}
int main(int argc,char** argv){try{
 VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);DUT d{&context};
 if(argc==2&&std::string(argv[1])=="--runtime-probe"){
  std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";d.final();return 0;}
 bool negative=argc==2&&std::string(argv[1])=="--negative";need(argc==1||negative,"S4_CALENDAR_ARGS");
 run(d,false,false);unsigned fault=run(d,true,negative);
 reset(d);d.frame_start=1;d.in_slot_valid=0;d.eval();need(d.fault_pending&&!d.out_error,"S4_CALENDAR_RAW_EXTERNAL_START_FAULT");
 edge(d);need(d.out_error,"S4_CALENDAR_EXTERNAL_REGISTER");run(d,false,false);
 need(context.threads()==1&&d.threads()==1,"S4_CALENDAR_THREADS");
 std::cout<<PASS_LABEL<<" cases=4 normal_rows="<<2*T<<" missing_first_tick="<<fault<<" external_faults=1 reloads=1\n";
 d.final();return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
