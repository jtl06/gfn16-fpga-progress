#include "Vgenefer_stream27_l7_bf_payload_pair_v1.h"
#include "verilated.h"
#include <cstdint>
#include <deque>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#ifndef TEST_P
#error TEST_P must match the RTL
#endif
static constexpr uint64_t P=TEST_P;
static void need(bool x,const char*m){if(!x)throw std::runtime_error(m);}
static uint64_t power(uint64_t x,uint64_t n){uint64_t y=1;for(;n;n>>=1,x=x*x%P)if(n&1)y=y*x%P;return y;}
struct Pending{uint64_t due;uint32_t y0,y1,tag;};
int main(int argc,char**argv){try{
 VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
 Vgenefer_stream27_l7_bf_payload_pair_v1 d{&context};
 if(argc==2&&std::string(argv[1])=="--thread-probe"){
  std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
  return context.threads()==1&&d.threads()==1?0:2;
 }
 need(argc==2,"BF_PAYLOAD_ARGS");std::ifstream input(argv[1]);
 std::string magic;uint64_t field,events;input>>magic>>field>>events;
 need(magic=="L7BFPAYLOAD1"&&field==P&&events>0,"BF_PAYLOAD_HEADER");
 const uint64_t inverse=power((uint64_t(1)<<32)%P,P-2);
 std::deque<Pending> pending;uint64_t checked=0,canceled=0,holds=0,dirty=0,ct=0,gs=0;
 uint32_t last0=0,last1=0,lasttag=0;bool lastvalid=false;
 for(uint64_t edge=0;edge<events;edge++){
  unsigned reset,valid,form,cancel;uint64_t u,v,w,tag;
  need(bool(input>>reset>>valid>>form>>u>>v>>w>>tag>>cancel),"BF_PAYLOAD_SHORT_INPUT");
  need(reset<2&&valid<2&&form<2&&cancel<2&&u<(1u<<28)&&v<(1u<<28)&&w<(1u<<27)&&tag<(uint64_t(1)<<32),"BF_PAYLOAD_PORT_RANGE");
  const bool active=reset&&!cancel;
  d.clk=0;d.rst_n=reset;d.cancel=cancel;d.in_valid=valid;d.gs=form;d.u=u;d.v=v;d.w=w;d.in_tag=tag;d.eval();
  if(!active){canceled+=pending.size();pending.clear();lastvalid=false;last0=last1=lasttag=0;}
  need(d.out_valid==(lastvalid?3:0)&&d.y0==last0&&d.y1==last1&&d.out_tag==lasttag&&d.old_y0==last0&&d.old_y1==last1&&d.old_out_tag==lasttag,"BF_PAYLOAD_BEFORE_EDGE");
  if(active&&valid){
   need(u<2*P&&v<2*P&&w<P,"BF_PAYLOAD_ADMITTED_RANGE");
   uint64_t a,b;
   if(form){a=(u+v)%(2*P);b=(((u+2*P-v)%(2*P))*w%P)*inverse%P;gs++;}
   else{uint64_t uc=u%P,t=(v*w%P)*inverse%P;a=uc+t;b=uc+P-t;ct++;}
   pending.push_back({edge+5,uint32_t(a),uint32_t(b),uint32_t(tag)});
  }else dirty+=u>=2*P||v>=2*P||w>=P;
  const bool due=!pending.empty()&&pending.front().due==edge;
  d.clk=1;d.eval();need(d.out_valid==(due?3:0),"BF_PAYLOAD_VALID_OR_LATENCY");
  if(due){
   auto expected=pending.front();pending.pop_front();
   need(d.y0==expected.y0&&d.y1==expected.y1&&d.out_tag==expected.tag&&d.y0<2*P&&d.y1<2*P,"BF_PAYLOAD_NEW_ARITHMETIC_OR_TAG");
   last0=expected.y0;last1=expected.y1;lasttag=expected.tag;checked++;
  }else holds++;
  need(d.y0==last0&&d.y1==last1&&d.out_tag==lasttag&&d.old_y0==last0&&d.old_y1==last1&&d.old_out_tag==lasttag,"BF_PAYLOAD_PUBLIC_RESET_OR_HOLD");
  lastvalid=due;
 }
 std::string extra;need(!(input>>extra)&&input.eof()&&pending.empty()&&dirty>0&&ct>0&&gs>0,"BF_PAYLOAD_TAIL_OR_COVERAGE");
 std::cout<<"PASS_L7_BF_PAYLOAD P="<<P<<" events="<<events<<" checked="<<checked<<" canceled="<<canceled<<" holds="<<holds<<" dirty="<<dirty<<" ct="<<ct<<" gs="<<gs<<" outputs=2 latency=5 ii=1\n";
 d.final();return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
