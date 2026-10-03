#include "Vgenefer_stream27_crt_tag_pair_v1.h"
#include "native_runtime_context_v1.h"
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
using DUT=Vgenefer_stream27_crt_tag_pair_v1;
static void need(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
static uint64_t token(uint64_t c,unsigned g){
 uint64_t x=(c+17)*0x9e3779b97f4a7c15ull+g;
 x=(x^(x>>30))*0xbf58476d1ce4e5b9ull;x=(x^(x>>27))*0x94d049bb133111ebull;
 return x^(x>>31);
}
int main(int argc,char** argv){try{
 VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d(&context);
 if(argc==2 && std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
 bool resets=argc==2 && std::string(argv[1])=="--reset-test";
 bool wrong=argc==2 && std::string(argv[1])=="--wrong-head";
 need(argc==1 || resets || wrong,"CRT_TAG_ARGUMENTS");
 need(gfn16_runtime::matches(context,d),"CRT_TAG_THREADS");
 std::array<std::array<uint64_t,16>,9> pipe{};std::array<bool,16> valid{};
 uint64_t cycles=0,checks=0;
 auto read=[](const auto& bus,unsigned g){return uint64_t(bus[2*g])|(uint64_t(bus[2*g+1])<<32);};
 auto compare=[&](){if(valid[15])for(unsigned g=0;g<9;g++){
  uint64_t old=read(d.parent_head,g),candidate=read(d.candidate_head,g);
  if(wrong && checks==0)candidate^=uint64_t(1)<<((g+25)%(30+g));
  need(old==pipe[g][15],"CRT_TAG_PARENT_REFERENCE");
  need(candidate==pipe[g][15],"CRT_TAG_CANDIDATE_REFERENCE");checks++;
 }};
 auto reset=[&](){d.clk=0;d.rst_n=0;valid.fill(false);d.eval();};
 auto tick=[&](bool joined,bool stop){
  d.clk=0;d.joined=joined;
  for(unsigned g=0;g<9;g++){
   uint64_t word=token(cycles,g)&((uint64_t(1)<<(30+g))-1);
   if(resets && cycles%41<38)word=uint64_t(1)<<(cycles%41%(30+g));
   d.write_words[2*g]=uint32_t(word);d.write_words[2*g+1]=uint32_t(word>>32);
  }
  d.eval();compare();context.timeInc(1);
  for(unsigned g=0;g<9;g++){
   uint64_t incoming=joined?read(d.write_words,g):pipe[g][0];
   for(unsigned s=15;s;s--)pipe[g][s]=pipe[g][s-1];pipe[g][0]=incoming;
  }
  if(d.rst_n){for(unsigned s=15;s;s--)valid[s]=valid[s-1];valid[0]=joined && !stop;}
  else valid.fill(false);
  d.clk=1;d.eval();compare();context.timeInc(1);
  d.clk=0;d.joined=!joined;for(unsigned i=0;i<18;i++)d.write_words[i]^=0xffffffffu;
  d.eval();compare();context.timeInc(1);cycles++;
 };
 d.clk=0;d.rst_n=1;d.joined=0;for(unsigned i=0;i<18;i++)d.write_words[i]=0;d.eval();reset();d.rst_n=1;
 if(!resets){for(unsigned c=0;c<4096;c++)tick(c<64 || token(c,0)%5!=0,c%97==11);}
 else for(unsigned age=0;age<40;age++){
  reset();for(unsigned i=0;i<3;i++)tick(true,false);d.rst_n=1;
  for(unsigned i=0;i<age;i++)tick(true,false);
  reset();for(unsigned i=0;i<3;i++)tick(i%2==0,false);d.rst_n=1;
  for(unsigned i=0;i<128;i++)tick(i<64 || token(cycles,1)%3!=0,i%31==17);
 }
 std::cout<<"CRT_TAG_"<<(resets?"RESET":"NORMAL")<<"_PASS geometries=9 cycles="<<cycles<<" comparisons="<<checks<<" preedge=exact\n";
 return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
