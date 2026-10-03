#include "Vgenefer_stream27_r15_crt_numeric_pair_v1.h"
#include "native_runtime_context_v1.h"
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
using DUT=Vgenefer_stream27_r15_crt_numeric_pair_v1;
using U=unsigned __int128;
static constexpr uint64_t P0=104857601,P1=69206017,P2=67239937;
static constexpr U MOD=U(P0)*P1*P2;
static void need(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
static uint64_t random_word(uint64_t n){
 uint64_t x=n+0x9e3779b97f4a7c15ull;
 x=(x^(x>>30))*0xbf58476d1ce4e5b9ull;x=(x^(x>>27))*0x94d049bb133111ebull;return x^(x>>31);
}
static uint64_t inverse(uint64_t a,uint64_t p){
 int64_t x=0,y=1,r=p,s=a;
 while(s){int64_t q=r/s;int64_t t=r-q*s;r=s;s=t;t=x-q*y;x=y;y=t;}
 need(r==1,"R15_CRT_REFERENCE_INVERSE");if(x<0)x+=int64_t(p);return uint64_t(x);
}
static U reconstruct(uint32_t a,uint32_t b,uint32_t c){
 static const uint64_t I1=inverse(P0%P1,P1),I2=inverse(uint64_t(U(P0)*P1%P2),P2);
 uint64_t t1=uint64_t(U((uint64_t(b)+P1-a%P1)%P1)*I1%P1);
 U x=U(P0)*t1+a;
 uint64_t t2=uint64_t(U((uint64_t(c)+P2-uint64_t(x%P2))%P2)*I2%P2);
 U value=x+U(P0)*P1*t2;
 // Two's complement 96-bit coefficient; no RTL/Montgomery oracle reuse.
 return (value>MOD/2 ? value-MOD : value)&((U(1)<<96)-1);
}
template<class Bus>static U read(const Bus& bus){return U(bus[0])|(U(bus[1])<<32)|(U(bus[2])<<64);}
int main(int argc,char** argv){try{
 VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d(&context);
 if(argc==2 && std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
 bool resets=argc==2 && std::string(argv[1])=="--reset-test";
 bool wrong=argc==2 && std::string(argv[1])=="--wrong-word";
 need(argc==1 || resets || wrong,"R15_CRT_ARGUMENTS");
 need(gfn16_runtime::matches(context,d),"R15_CRT_THREADS");
 std::array<U,16> words{};std::array<bool,16> valid{};
 U held=0;uint64_t cycles=0,accepted=0,eligible=0,checks=0,reset_edges=0;
 auto compare=[&](){
  need(bool(d.parent_valid)==valid[15] && bool(d.candidate_valid)==valid[15],"R15_CRT_VALID_EDGE");
  U candidate=read(d.candidate_coefficient);
  if(wrong && valid[15])candidate^=1;
  need(read(d.parent_coefficient)==held,"R15_CRT_PARENT_ORACLE");
  need(candidate==held,"R15_CRT_CANDIDATE_ORACLE");checks++;
 };
 auto reset=[&](){
  d.clk=0;d.rst_n=0;d.in_valid=0;valid.fill(false);held=0;d.eval();compare();
 };
 auto tick=[&](bool enable){
  uint64_t k=cycles;
  U represented=U(random_word(k+1))*random_word(k+2)%MOD;
  switch(k%31){case 0:represented=0;break;case 1:represented=MOD-1;break;
   case 2:represented=MOD/2;break;case 3:represented=MOD/2+1;break;case 4:represented=1;break;}
  d.clk=0;d.in_valid=enable;d.r1=uint32_t(represented%P0);
  d.r2=uint32_t(represented%P1);d.r3=uint32_t(represented%P2);d.eval();compare();
  U expected=reconstruct(d.r1,d.r2,d.r3);
  for(unsigned s=15;s;s--){words[s]=words[s-1];valid[s]=valid[s-1];}
  words[0]=expected;valid[0]=enable && d.rst_n;
  if(!d.rst_n){valid.fill(false);held=0;reset_edges++;}
  else {accepted+=enable;if(valid[15]){held=words[15];eligible++;}}
  d.clk=1;context.timeInc(1);d.eval();compare();
  // Settle unrelated payload without another acceptance edge.
  d.clk=0;d.in_valid=!enable;d.r1=(d.r1+7)%P0;d.r2=(d.r2+11)%P1;d.r3=(d.r3+13)%P2;
  context.timeInc(1);d.eval();compare();cycles++;
 };
 d.clk=0;d.rst_n=1;d.in_valid=0;d.r1=d.r2=d.r3=0;d.eval();reset();
 for(unsigned i=0;i<4;i++)tick(true);d.rst_n=1;
 if(!resets){for(unsigned i=0;i<10000;i++)tick(i<64 || random_word(i)%5!=0);}
 else for(unsigned age=0;age<32;age++){
  for(unsigned i=0;i<age;i++)tick(true);reset();
  for(unsigned i=0;i<3;i++)tick(i%2==0);d.rst_n=1;
  for(unsigned i=0;i<96;i++)tick(i<48 || random_word(cycles)%3!=0);
 }
 std::cout<<"R15_CRT_"<<(resets?"RESET":"NORMAL")<<"_PASS cycles="<<cycles
  <<" accepted="<<accepted<<" eligible="<<eligible<<" comparisons="<<checks
  <<" reset_edges="<<reset_edges<<" coefficient96=1 II1=1 E16=1 independent_garner=1\n";
 return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
