#include "Vgenefer_stream27_l3_static_direction_probe_v1.h"
#include "verilated.h"
#include <cstdint>
#include <deque>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#ifndef TEST_P
#define TEST_P 104857601
#endif
static constexpr uint64_t P=TEST_P;
static void require(bool good,const char* why){if(!good)throw std::runtime_error(why);}
static uint64_t power(uint64_t a,uint64_t e){uint64_t r=1;while(e){if(e&1)r=r*a%P;a=a*a%P;e>>=1;}return r;}
template<class T>static void put(T&words,unsigned offset,unsigned width,uint32_t value){
 for(unsigned k=0;k<width;k++){unsigned at=offset+k;uint32_t mask=uint32_t(1)<<(at%32);
  words[at/32]=(words[at/32]&~mask)|(((value>>k)&1)?mask:0);}}
template<class T>static uint32_t get(const T&words,unsigned offset,unsigned width){uint32_t value=0;
 for(unsigned k=0;k<width;k++)value|=((words[(offset+k)/32]>>((offset+k)%32))&1)<<k;return value;}
struct Pending{uint64_t due;uint32_t a,b,tag;};
int main(int argc,char**argv){try{
 VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
 Vgenefer_stream27_l3_static_direction_probe_v1 d{&context};d.eval();
 if(argc==2&&std::string(argv[1])=="--runtime-probe"){
  std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
  return context.threads()==1&&d.threads()==1?0:2;}
 require(argc==2,"STATIC_ARGS");std::ifstream input(argv[1]);std::string magic;uint64_t field,events;
 input>>magic>>field>>events;require(magic=="LAZYBFLY1"&&field==P&&events>0,"STATIC_HEADER");
 const uint64_t ri=power((uint64_t(1)<<32)%P,P-2);std::deque<Pending> pending[4];
 uint64_t checked[4]={0,0,0,0},cancelled=0,holds=0;uint32_t last0[4]={},last1[4]={},lasttag=0,lastvalid=0;
 for(uint64_t edge=0;edge<events;edge++){
  unsigned reset,valid,ignored_form;uint64_t u,v,w,tag;
  require(bool(input>>reset>>valid>>ignored_form>>u>>v>>w>>tag),"STATIC_SHORT_INPUT");
  require(reset<2&&valid<2&&ignored_form<2&&u<2*P&&v<2*P&&w<P&&tag<(uint64_t(1)<<32),"STATIC_INPUT_RANGE");
  const unsigned mask=valid?(edge%5==0?15u:(15u^(1u<<(edge%4)))):0;
  d.clk=0;d.rst_n=reset;d.in_valid=mask;d.in_tag=0;
  for(unsigned word=0;word<4;word++){d.u[word]=0;d.v[word]=0;d.w[word]=0;}
  for(unsigned cell=0;cell<4;cell++){
   put(d.u,28*cell,28,u);put(d.v,28*cell,28,v);put(d.w,27*cell,27,w);
   const unsigned token=(tag^(edge>>(cell+1))^cell)&1;d.in_tag|=token<<cell;
   if(!reset){cancelled+=pending[cell].size();pending[cell].clear();last0[cell]=last1[cell]=0;}
  }
  d.eval();if(!reset){lastvalid=0;lasttag=0;}
  require(d.out_valid==lastvalid&&d.out_tag==lasttag,"STATIC_BEFORE_EDGE_METADATA");
  for(unsigned cell=0;cell<4;cell++){
   require(get(d.y0,28*cell,28)==last0[cell]&&get(d.y1,28*cell,28)==last1[cell],"STATIC_BEFORE_EDGE_PAYLOAD");
   if(reset&&(mask&(1u<<cell))){uint64_t a,b;
    if(cell>=2){a=(u+v)%(2*P);b=(((u+2*P-v)%(2*P))*w%P)*ri%P;}
    else{uint64_t t=(v*w%P)*ri%P;a=u%P+t;b=u%P+P-t;}
    pending[cell].push_back({edge+6,uint32_t(a),uint32_t(b),(d.in_tag>>cell)&1u});}
  }
  d.clk=1;d.eval();unsigned expected_valid=0;
  for(unsigned cell=0;cell<4;cell++){
   bool due=!pending[cell].empty()&&pending[cell].front().due==edge;expected_valid|=unsigned(due)<<cell;
   uint32_t a=get(d.y0,28*cell,28),b=get(d.y1,28*cell,28),token=(d.out_tag>>cell)&1;
   if(due){Pending expected=pending[cell].front();pending[cell].pop_front();
    require(a<2*P&&b<2*P,"STATIC_PUBLIC_RANGE");
    require(a%P==expected.a%P&&b%P==expected.b%P&&token==expected.tag,"STATIC_MODE_VALUE_TAG");
    if(cell%2==0)require(a==expected.a&&b==expected.b,"STATIC_NORMALIZED_BIT_EXACT");
    last0[cell]=a;last1[cell]=b;lasttag=(lasttag&~(1u<<cell))|(token<<cell);checked[cell]++;
   }else{require(a==last0[cell]&&b==last1[cell]&&token==((lasttag>>cell)&1),"STATIC_INVALID_HOLD");holds++;}
  }
  require(d.out_valid==expected_valid,"STATIC_VALID_E6");lastvalid=expected_valid;
 }
 std::string extra;require(!(input>>extra)&&input.eof(),"STATIC_TAIL");
 for(unsigned cell=0;cell<4;cell++)require(pending[cell].empty()&&checked[cell]>3000,"STATIC_COVERAGE");
 std::cout<<"P5_STATIC_PASS p="<<P<<" events="<<events<<" normalized_ct="<<checked[0]<<" fused_ct="<<checked[1]
  <<" normalized_gs="<<checked[2]<<" fused_gs="<<checked[3]<<" cancelled="<<cancelled<<" holds="<<holds<<"\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
