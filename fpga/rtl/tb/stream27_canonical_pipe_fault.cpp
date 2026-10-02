// Native-only registered-boundary range/reset regression; no host/clock claim.
#include "Vgenefer_stream27_canonical_image_pipe_v1.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {
constexpr unsigned N=32,P=8,T=N/P,B=172;
using Image=std::array<int32_t,N>;
void need(bool ok,const char* label){if(!ok)throw std::runtime_error(label);}
class H {
 public:
 VerilatedContext context;
 Vgenefer_stream27_canonical_image_pipe_v1 d{&context};
 unsigned reads=0,images=0;
 H(){d.clk=1;d.rst_n=0;clear();d.base=B;d.load_row=0;d.read_address=0;
     for(unsigned b=0;b<P;++b)d.load_data[b]=d.c0[b]=d.c1[b]=0;d.eval();}
 void clear(){d.load_valid=d.begin_canonical=d.read_req=0;}
 void edge(){d.eval();d.clk=0;context.timeInc(1);d.eval();d.clk=1;context.timeInc(1);d.eval();}
 void flags(){need(!d.busy&&!d.done&&!d.error&&!d.image_valid&&!d.read_valid&&!d.cycles,"CANON_PIPE_RESET_FLAGS");}
 void reset(){clear();d.rst_n=0;edge();flags();d.rst_n=1;d.base=B;
   for(unsigned b=0;b<P;++b)d.c0[b]=d.c1[b]=0;edge();flags();}
 void idle_no_stale(){clear();for(unsigned k=0;k<8;++k){edge();flags();}}
 void load(const Image& x,unsigned base=B){clear();d.base=base;
   for(unsigned r=0;r<T;++r){d.load_valid=1;d.load_row=r;
     for(unsigned b=0;b<P;++b)d.load_data[b]=uint32_t(x[b*T+r]);edge();
     need(!d.error&&!d.image_valid&&!d.done&&!d.busy,"CANON_PIPE_LOAD_ORDER");}
   d.load_valid=0;}
 void begin(bool special=false,unsigned base=B){clear();d.base=base;
   for(unsigned b=0;b<P;++b){d.c0[b]=(special&&b==0)?0xffffffffu:0u;d.c1[b]=0;}
   d.begin_canonical=1;edge();d.begin_canonical=0;
   need(d.busy&&!d.done&&!d.image_valid&&!d.error&&d.cycles==0,"CANON_PIPE_BEGIN_L_PLUS_ONE");}
 void run(bool special=false){const unsigned limit=(special?10u:9u)*N;
   for(unsigned age=1;age<=limit;++age){clear();edge();
     need(!d.error&&!d.read_valid&&d.cycles==age,"CANON_PIPE_PROCESS_CYCLE");
     need(age==limit?(!d.busy&&d.done&&d.image_valid):(d.busy&&!d.done&&!d.image_valid),"CANON_PIPE_NO_EARLY_PUBLICATION");}
   ++images;}
 void word(unsigned address,int32_t expected,bool mutant=false){
   need(d.read_valid&&d.read_address_out==address&&d.image_valid&&!d.busy&&!d.error,"CANON_PIPE_E1_RESPONSE");
   const uint32_t sign=expected<0?0xffffffffu:0u;
   const bool same=d.read_data[0]==uint32_t(expected)&&d.read_data[1]==sign&&d.read_data[2]==sign;
   if(!same)throw std::runtime_error(mutant?"CANON_PIPE_WRONG_WORD_REJECT":"CANON_PIPE_RECOVERY_WORD");
   ++reads;}
 void all(const Image& x){clear();d.read_req=1;d.read_address=0;edge();
   need(!d.read_valid&&!d.done,"CANON_PIPE_E0_NO_RESPONSE");
   for(unsigned a=1;a<N;++a){d.read_address=a;edge();word(a-1,x[a-1]);}
   d.read_req=0;edge();word(N-1,x[N-1]);}
 void quarantine(){need(d.error&&d.error_code==6&&!d.busy&&!d.done&&!d.image_valid&&!d.read_valid,"CANON_PIPE_DIGIT_RANGE");
   auto frozen=d.cycles;for(unsigned k=0;k<4;++k){d.load_valid=d.begin_canonical=d.read_req=1;edge();
     need(d.error&&d.error_code==6&&!d.busy&&!d.done&&!d.image_valid&&!d.read_valid&&d.cycles==frozen,"CANON_PIPE_STICKY_QUARANTINE");}clear();}
 void recovery(const Image& x){reset();load(x);begin();run();all(x);}
};
void suite(H& h){Image x{},zero{},special{};for(unsigned a=0;a<N;++a)x[a]=int32_t((a*7+3)%B);special[0]=-1;
 // Illegal raw input is rejected on its load edge, with no success done.
 h.reset();h.d.load_valid=1;h.d.load_row=0;h.d.load_data[0]=B;h.edge();h.quarantine();h.recovery(x);
 // Lower frozen begin base rechecks the stored digit at the new PROCESS E3.
 Image high{};high.fill(B);h.reset();h.load(high,B+1);h.begin(false,B);
 for(unsigned age=1;age<=3;++age){h.clear();h.edge();
   if(age<3)need(h.d.busy&&!h.d.error&&!h.d.done&&!h.d.image_valid,"CANON_PIPE_RANGE_E3_NOT_EARLY");}
 need(h.d.cycles==3,"CANON_PIPE_RANGE_EXACT_E3");h.quarantine();h.recovery(x);
 const std::array<unsigned,8> ordinary{1,2,3,3*N-1,3*N,3*N+1,6*N,9*N-1};
 const std::array<unsigned,3> special_ages{9*N,9*N+1,10*N-1};
 for(auto age:ordinary){h.reset();h.load(x);h.begin();for(unsigned k=0;k<age;++k)h.edge();h.reset();h.idle_no_stale();h.recovery(x);}
 for(auto age:special_ages){h.reset();h.load(zero);h.begin(true);for(unsigned k=0;k<age;++k)h.edge();h.reset();h.idle_no_stale();h.recovery(x);}
 // Reset between accepted E0 read and E1 response revokes the response token.
 h.clear();h.d.read_req=1;h.d.read_address=N-1;h.edge();need(!h.d.read_valid,"CANON_PIPE_PENDING_E0");
 h.reset();h.idle_no_stale();h.recovery(x);
 h.reset();h.load(zero);h.begin(true);h.run(true);h.all(special);
 need(h.images==15&&h.reads==480,"CANON_PIPE_FAULT_COUNTS");
}
}
int main(int argc,char** argv){
 try{
  if(argc==2&&std::string(argv[1])=="--runtime-probe"){
   std::cout<<"{\"context_threads\":1,\"model_threads\":1,\"expected_threads\":1}\n";return 0;}
  H h;suite(h);
  if(argc==2&&std::string(argv[1])=="--wrong-word"){
   h.clear();h.d.read_req=1;h.d.read_address=0;h.edge();h.d.read_req=0;h.edge();h.word(0,0,true);
   throw std::runtime_error("CANON_PIPE_WRONG_WORD_MISSED");}
  need(argc==1,"CANON_PIPE_ARGUMENTS");
  std::cout<<"CANON_PIPE_FAULT_PASS aw=5 p=8 range_faults=2 reset_aborts=11 pending_read_resets=1 recovery_images=15 signed96_reads=480\n";
  return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
