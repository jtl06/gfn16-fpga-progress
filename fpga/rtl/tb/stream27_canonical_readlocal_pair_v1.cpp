// Native-only R4 paired canonical read-command contracts. No whole-core claim.
#include "Vgenefer_stream27_canonical_readlocal_pair_v1.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {
constexpr unsigned N=256,P=16,T=N/P,B=1009;
using Image=std::array<int32_t,N>;
void need(bool value,const char* text){if(!value)throw std::runtime_error(text);}
class H {
public:
 VerilatedContext context;
 Vgenefer_stream27_canonical_readlocal_pair_v1 d{&context};
 unsigned reads=0,images=0;
 H(){d.clk=1;d.rst_n=0;clear();d.base=B;d.load_row=d.read_address=0;
  for(unsigned b=0;b<P;b++)d.load_data[b]=d.c0[b]=d.c1[b]=0;d.eval();compare();}
 void clear(){d.load_valid=d.begin_canonical=d.read_req=0;}
 void compare(){
  need(d.parent_busy==d.local_busy&&d.parent_done==d.local_done&&d.parent_error==d.local_error&&
   d.parent_image_valid==d.local_image_valid&&d.parent_error_code==d.local_error_code&&
   d.parent_cycles==d.local_cycles&&d.parent_read_valid==d.local_read_valid,"R4_READLOCAL_EDGE_EQUIVALENCE");
  if(d.parent_read_valid){need(d.parent_read_address_out==d.local_read_address_out,"R4_READLOCAL_ADDRESS_EQUIVALENCE");
   for(unsigned k=0;k<3;k++)need(d.parent_read_data[k]==d.local_read_data[k],"R4_READLOCAL_DATA_EQUIVALENCE");}
 }
 void edge(){d.eval();compare();d.clk=0;context.timeInc(1);d.eval();compare();d.clk=1;context.timeInc(1);d.eval();compare();}
 void reset(){clear();d.rst_n=0;edge();need(!d.local_busy&&!d.local_done&&!d.local_error&&!d.local_image_valid&&
  !d.local_read_valid&&!d.local_cycles,"R4_READLOCAL_RESET_ELIGIBILITY");d.rst_n=1;d.base=B;
  for(unsigned b=0;b<P;b++)d.c0[b]=d.c1[b]=0;edge();}
 void load(const Image& x){clear();d.base=B;for(unsigned r=0;r<T;r++){
  d.load_valid=1;d.load_row=r;for(unsigned b=0;b<P;b++)d.load_data[b]=uint32_t(x[b*T+r]);edge();
  need(!d.local_error&&!d.local_busy&&!d.local_image_valid,"R4_READLOCAL_LOAD");}d.load_valid=0;}
 void begin(bool special=false){clear();d.base=B;for(unsigned b=0;b<P;b++){d.c0[b]=(special&&b==0)?0xffffffffu:0u;d.c1[b]=0;}
  d.begin_canonical=1;edge();d.begin_canonical=0;need(d.local_busy&&!d.local_error&&!d.local_cycles,"R4_READLOCAL_BEGIN");}
 void run(bool special=false){unsigned count=(special?10u:9u)*N;for(unsigned age=1;age<=count;age++){
  clear();edge();need(!d.local_error&&d.local_cycles==age,"R4_READLOCAL_CANONICAL_CYCLE");
  need(age==count?(!d.local_busy&&d.local_done&&d.local_image_valid):(d.local_busy&&!d.local_done&&!d.local_image_valid),
   "R4_READLOCAL_PUBLICATION_AGE");}images++;}
 void word(unsigned addr,int32_t expected,bool mutant=false){need(d.local_read_valid&&d.local_image_valid&&!d.local_error&&
  d.local_read_address_out==addr,"R4_READLOCAL_E1_RESPONSE");uint32_t sign=expected<0?0xffffffffu:0u;
  bool same=d.local_read_data[0]==uint32_t(expected)&&d.local_read_data[1]==sign&&d.local_read_data[2]==sign;
  if(!same)throw std::runtime_error(mutant?"R4_READLOCAL_WRONG_WORD":"R4_READLOCAL_SIGNED96_VALUE");reads++;}
 void all(const Image& x){clear();d.read_req=1;d.read_address=0;edge();need(!d.local_read_valid,"R4_READLOCAL_E0_NO_RESPONSE");
  for(unsigned a=1;a<N;a++){d.read_address=a;edge();word(a-1,x[a-1]);}d.read_req=0;edge();word(N-1,x[N-1]);}
 void image(const Image& x,bool special=false){reset();load(x);begin(special);run(special);}
 void quarantine(unsigned code){need(d.local_error&&d.local_error_code==code&&!d.local_busy&&!d.local_done&&
  !d.local_image_valid&&!d.local_read_valid,"R4_READLOCAL_ORIGIN_FAULT_PRIORITY");auto cycles=d.local_cycles;
  for(unsigned k=0;k<4;k++){d.load_valid=d.begin_canonical=d.read_req=1;edge();need(d.local_error&&
   d.local_error_code==code&&!d.local_image_valid&&!d.local_read_valid&&d.local_cycles==cycles,"R4_READLOCAL_STICKY_FAULT");}clear();}
};
Image input(){Image x{};for(unsigned a=0;a<N;a++)x[a]=int32_t((a*7+3)%B);return x;}
void normal(H& h){auto x=input();h.image(x);h.all(x);
 // Exclusive read deliberately carries invalid unrelated base/corrections.
 h.clear();h.d.base=0;for(unsigned b=0;b<P;b++)h.d.c0[b]=h.d.c1[b]=0x7fffffffu;
 h.d.read_req=1;h.d.read_address=17;h.edge();need(!h.d.local_read_valid&&!h.d.local_error,"R4_READLOCAL_DIRTY_INPUT_E0");
 h.d.read_req=0;h.edge();h.word(17,x[17]);
 h.clear();h.d.read_req=1;h.d.read_address=31;h.edge();need(!h.d.local_read_valid,"R4_READLOCAL_PIPE_E0");
 for(unsigned a=32;a<=33;a++){h.d.read_address=a;h.edge();h.word(a-1,x[a-1]);}h.d.read_req=0;h.edge();h.word(33,x[33]);
 Image zero{},special{};special[0]=-1;h.image(zero,true);h.all(special);
 need(h.images==2&&h.reads==516,"R4_READLOCAL_NORMAL_COUNTS");
}
void faults(H& h){auto x=input();unsigned cases=0;
 h.reset();h.d.read_req=1;h.edge();h.quarantine(5);cases++;
 // Conflicts dominate malformed base/correction inputs on the origin edge.
 for(unsigned mode=0;mode<4;mode++){
  h.image(x);h.clear();h.d.base=0;h.d.c0[0]=0x7fffffffu;
  if(mode>=2){h.d.read_req=1;h.d.read_address=9;h.edge();need(!h.d.local_read_valid,"R4_READLOCAL_PENDING_E0");h.clear();}
  h.d.load_valid=(mode==0||mode==2);h.d.begin_canonical=(mode==1||mode==3);h.d.read_req=(mode<2);
  h.edge();h.quarantine(1);cases++;
 }
 h.image(x);h.clear();h.d.read_req=1;h.d.read_address=N-1;h.edge();h.reset();
 for(unsigned k=0;k<8;k++){h.edge();need(!h.d.local_read_valid&&!h.d.local_image_valid&&!h.d.local_error,"R4_READLOCAL_RESET_PENDING_QUIET");}cases++;
 // Range/order priorities are unchanged; no raw payload trimming or bypass.
 h.reset();h.d.load_valid=1;h.d.load_row=1;h.d.base=0;h.d.load_data[0]=0xffffffffu;h.edge();h.quarantine(3);cases++;
 h.reset();h.d.load_valid=1;h.d.load_row=1;h.d.load_data[0]=B;h.edge();h.quarantine(6);cases++;
 h.reset();h.d.load_valid=1;h.d.load_row=1;for(unsigned b=0;b<P;b++)h.d.load_data[b]=0;h.edge();h.quarantine(2);cases++;
 h.reset();h.d.begin_canonical=1;h.d.base=0;h.edge();h.quarantine(5);cases++;
 h.reset();h.load(x);h.d.begin_canonical=1;h.d.base=0;h.edge();h.quarantine(3);cases++;
 h.reset();h.load(x);h.d.begin_canonical=1;h.d.c0[0]=B;h.edge();h.quarantine(4);cases++;
 h.image(x);h.all(x);need(cases==12&&h.reads==256,"R4_READLOCAL_FAULT_COUNTS");
}
}
int main(int argc,char** argv){try{
 if(argc==2&&std::string(argv[1])=="--runtime-probe"){
  std::cout<<"{\"context_threads\":1,\"model_threads\":1,\"expected_threads\":1}\n";return 0;}
 H h;if(argc==2&&std::string(argv[1])=="--faults"){faults(h);
  std::cout<<"R4_READLOCAL_FAULT_PASS aw=8 p=16 cases=12 pending_conflicts=2 pending_reset=1 recovery_reads=256 paired_edges=1\n";return 0;}
 need(argc==1||(argc==2&&std::string(argv[1])=="--wrong-word"),"R4_READLOCAL_ARGUMENTS");normal(h);
 if(argc==2){h.clear();h.d.read_req=1;h.d.read_address=0;h.edge();h.d.read_req=0;h.edge();h.word(0,0,true);
  throw std::runtime_error("R4_READLOCAL_WRONG_WORD_MISSED");}
 std::cout<<"R4_READLOCAL_NORMAL_PASS aw=8 p=16 images=2 signed96_reads=516 dirty_read=1 consecutive_reads=3 special_sentinel=1 paired_edges=1\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
