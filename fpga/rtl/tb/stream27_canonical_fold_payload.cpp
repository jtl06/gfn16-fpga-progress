// Native-only R8 single-context paired live-bound contracts; frozen RTL unchanged.
#include "Vgenefer_stream27_canonical_fold_payload_pair_v1.h"
#include "native_runtime_context_v1.h"
#include "stream27_host_chain_full_reference_v1.h"
#include <filesystem>
#include <array>
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {
constexpr unsigned N=256,P=16,T=N/P,B=1009;
using Image=std::array<int32_t,N>;
void need(bool value,const char* text){if(!value)throw std::runtime_error(text);}
unsigned peak_os_threads=0;
unsigned os_threads(){unsigned count=0;for(const auto& task:std::filesystem::directory_iterator("/proc/self/task")){
 (void)task;count++;}return count;}
struct RuntimeContext:VerilatedContext{
 RuntimeContext(int argc=0,char** argv=nullptr){gfn16_runtime::configure(*this,argc,argv);}
};
class H {
public:
 RuntimeContext context;
 Vgenefer_stream27_canonical_fold_payload_pair_v1 d;
 unsigned reads=0,images=0;
 H(int argc=0,char** argv=nullptr):context(argc,argv),d(&context){
  sample();d.clk=1;d.rst_n=0;clear();d.base=B;d.load_row=d.read_address=0;
  for(unsigned b=0;b<P;b++)d.load_data[b]=d.c0[b]=d.c1[b]=0;d.eval();compare();}
 void sample(){
  need(gfn16_runtime::matches(context,d),"FOLD_PAYLOAD_RUNTIME_CONTEXT_MODEL");
  auto count=os_threads();peak_os_threads=std::max(peak_os_threads,count);
  need(count==1,"FOLD_PAYLOAD_ACTUAL_OS_THREADS");
 }
 void clear(){d.load_valid=d.begin_canonical=d.read_req=0;}
 void compare(){
  need(d.parent_busy==d.local_busy&&d.parent_done==d.local_done&&d.parent_error==d.local_error&&
   d.parent_image_valid==d.local_image_valid&&d.parent_error_code==d.local_error_code&&
   d.parent_cycles==d.local_cycles&&d.parent_read_valid==d.local_read_valid,"FOLD_PAYLOAD_EDGE_EQUIVALENCE");
  if(d.parent_read_valid){need(d.parent_read_address_out==d.local_read_address_out,"FOLD_PAYLOAD_ADDRESS_EQUIVALENCE");
   for(unsigned k=0;k<3;k++)need(d.parent_read_data[k]==d.local_read_data[k],"FOLD_PAYLOAD_DATA_EQUIVALENCE");}
 }
 void edge(){d.eval();compare();d.clk=0;context.timeInc(1);d.eval();compare();d.clk=1;context.timeInc(1);d.eval();compare();}
 void reset(){clear();d.rst_n=0;edge();need(!d.local_busy&&!d.local_done&&!d.local_error&&!d.local_image_valid&&
  !d.local_read_valid&&!d.local_cycles,"FOLD_PAYLOAD_RESET_ELIGIBILITY");d.rst_n=1;d.base=B;
  for(unsigned b=0;b<P;b++)d.c0[b]=d.c1[b]=0;edge();}
 void load(const Image& x){clear();d.base=B;for(unsigned r=0;r<T;r++){
  d.load_valid=1;d.load_row=r;for(unsigned b=0;b<P;b++)d.load_data[b]=uint32_t(x[b*T+r]);edge();
  need(!d.local_error&&!d.local_busy&&!d.local_image_valid,"FOLD_PAYLOAD_LOAD");}d.load_valid=0;}
 void begin(bool special=false){clear();d.base=B;for(unsigned b=0;b<P;b++){d.c0[b]=(special&&b==0)?0xffffffffu:0u;d.c1[b]=0;}
  d.begin_canonical=1;edge();d.begin_canonical=0;need(d.local_busy&&!d.local_error&&!d.local_cycles,"FOLD_PAYLOAD_BEGIN");}
 void run(bool special=false){unsigned count=(special?10u:9u)*N;for(unsigned age=1;age<=count;age++){
  clear();edge();need(!d.local_error&&d.local_cycles==age,"FOLD_PAYLOAD_CANONICAL_CYCLE");
  need(age==count?(!d.local_busy&&d.local_done&&d.local_image_valid):(d.local_busy&&!d.local_done&&!d.local_image_valid),
   "FOLD_PAYLOAD_PUBLICATION_AGE");}images++;}
 void word(unsigned addr,int32_t expected,bool mutant=false){need(d.local_read_valid&&d.local_image_valid&&!d.local_error&&
  d.local_read_address_out==addr,"FOLD_PAYLOAD_E1_RESPONSE");uint32_t sign=expected<0?0xffffffffu:0u;
  bool same=d.local_read_data[0]==uint32_t(expected)&&d.local_read_data[1]==sign&&d.local_read_data[2]==sign;
  if(!same)throw std::runtime_error(mutant?"FOLD_PAYLOAD_WRONG_WORD":"FOLD_PAYLOAD_SIGNED96_VALUE");reads++;}
 void all(const Image& x){clear();d.read_req=1;d.read_address=0;edge();need(!d.local_read_valid,"FOLD_PAYLOAD_E0_NO_RESPONSE");
  for(unsigned a=1;a<N;a++){d.read_address=a;edge();word(a-1,x[a-1]);}d.read_req=0;edge();word(N-1,x[N-1]);}
 void image(const Image& x,bool special=false){reset();load(x);begin(special);run(special);}
 void quarantine(unsigned code){need(d.local_error&&d.local_error_code==code&&!d.local_busy&&!d.local_done&&
  !d.local_image_valid&&!d.local_read_valid,"FOLD_PAYLOAD_ORIGIN_FAULT_PRIORITY");auto cycles=d.local_cycles;
  for(unsigned k=0;k<4;k++){d.load_valid=d.begin_canonical=d.read_req=1;edge();need(d.local_error&&
   d.local_error_code==code&&!d.local_image_valid&&!d.local_read_valid&&d.local_cycles==cycles,"FOLD_PAYLOAD_STICKY_FAULT");}clear();}
};
Image input(){Image x{};for(unsigned a=0;a<N;a++)x[a]=int32_t((a*7+3)%B);return x;}
void normal(H& h){auto x=input();h.image(x);h.all(x);
 // Exclusive read deliberately carries invalid unrelated base/corrections.
 h.clear();h.d.base=0;for(unsigned b=0;b<P;b++)h.d.c0[b]=h.d.c1[b]=0x7fffffffu;
 h.d.read_req=1;h.d.read_address=17;h.edge();need(!h.d.local_read_valid&&!h.d.local_error,"FOLD_PAYLOAD_DIRTY_INPUT_E0");
 h.d.read_req=0;h.edge();h.word(17,x[17]);
 h.clear();h.d.read_req=1;h.d.read_address=31;h.edge();need(!h.d.local_read_valid,"FOLD_PAYLOAD_PIPE_E0");
 for(unsigned a=32;a<=33;a++){h.d.read_address=a;h.edge();h.word(a-1,x[a-1]);}h.d.read_req=0;h.edge();h.word(33,x[33]);
 Image zero{},special{};special[0]=-1;h.image(zero,true);h.all(special);
 need(h.images==2&&h.reads==516,"FOLD_PAYLOAD_NORMAL_COUNTS");
}
void faults(H& h){auto x=input();unsigned cases=0;
 h.reset();h.d.read_req=1;h.edge();h.quarantine(5);cases++;
 // Conflicts dominate malformed base/correction inputs on the origin edge.
 for(unsigned mode=0;mode<4;mode++){
  h.image(x);h.clear();h.d.base=0;h.d.c0[0]=0x7fffffffu;
  if(mode>=2){h.d.read_req=1;h.d.read_address=9;h.edge();need(!h.d.local_read_valid,"FOLD_PAYLOAD_PENDING_E0");h.clear();}
  h.d.load_valid=(mode==0||mode==2);h.d.begin_canonical=(mode==1||mode==3);h.d.read_req=(mode<2);
  h.edge();h.quarantine(1);cases++;
 }
 h.image(x);h.clear();h.d.read_req=1;h.d.read_address=N-1;h.edge();h.reset();
 for(unsigned k=0;k<8;k++){h.edge();need(!h.d.local_read_valid&&!h.d.local_image_valid&&!h.d.local_error,"FOLD_PAYLOAD_RESET_PENDING_QUIET");}cases++;
 // Range/order priorities are unchanged; no raw payload trimming or bypass.
 h.reset();h.d.load_valid=1;h.d.load_row=1;h.d.base=0;h.d.load_data[0]=0xffffffffu;h.edge();h.quarantine(3);cases++;
 h.reset();h.d.load_valid=1;h.d.load_row=1;h.d.load_data[0]=B;h.edge();h.quarantine(6);cases++;
 h.reset();h.d.load_valid=1;h.d.load_row=1;for(unsigned b=0;b<P;b++)h.d.load_data[b]=0;h.edge();h.quarantine(2);cases++;
 h.reset();h.d.begin_canonical=1;h.d.base=0;h.edge();h.quarantine(5);cases++;
 h.reset();h.load(x);h.d.begin_canonical=1;h.d.base=0;h.edge();h.quarantine(3);cases++;
 h.reset();h.load(x);h.d.begin_canonical=1;h.d.c0[0]=B;h.edge();h.quarantine(4);cases++;
 h.image(x);h.all(x);need(cases==12&&h.reads==256,"FOLD_PAYLOAD_FAULT_COUNTS");
}
void bounds(H& h){
 h.reset();h.clear();unsigned checks=0;
 const std::array<uint32_t,13> bases={0u,1u,2u,1008u,1009u,1010u,0x7ffffffeu,0x7fffffffu,
  0x80000000u,0x80000001u,0xfffffffeu,0xffffffffu,1000000000u};
 const std::array<int64_t,11> qs={INT32_MIN,int64_t(INT32_MIN)+1,-1010,-1009,-1008,-1,0,1,1008,1009,INT32_MAX};
 auto check=[&](uint32_t base,int32_t q,int32_t c1,unsigned lane){
  h.d.base=base;for(unsigned b=0;b<P;b++){h.d.c0[b]=0;h.d.c1[b]=0;}
  h.d.c0[lane]=uint32_t(q);h.d.c1[lane]=uint32_t(c1);h.d.eval();h.compare();
  constexpr int64_t K=2*N+24*P;
  int64_t bound=int64_t(base)-1;
  bool expected=(base==0)||int64_t(q)>bound||int64_t(q)<-bound||int64_t(c1)>K||int64_t(c1)<-K;
  need(bool(h.d.parent_bound_bad)==expected&&bool(h.d.local_bound_bad)==expected,
   "FOLD_PAYLOAD_LIVE_SIGNED33_ORACLE");checks++;
 };
 for(auto base:bases)for(auto q:qs)for(unsigned lane=0;lane<P;lane++)check(base,int32_t(q),0,lane);
 for(auto base:bases)for(int64_t q:{int64_t(base)-1,int64_t(base),-int64_t(base)+1,-int64_t(base)})
  if(q>=INT32_MIN&&q<=INT32_MAX)for(unsigned lane=0;lane<P;lane++)check(base,int32_t(q),0,lane);
 for(int c1:{895,896,897,-895,-896,-897})for(unsigned lane=0;lane<P;lane++)check(B,0,c1,lane);
 uint32_t rng=0x98664321u;
 for(unsigned i=0;i<20000;i++){rng=rng*1664525u+1013904223u;uint32_t base=rng;
  rng=rng*1664525u+1013904223u;check(base,int32_t(rng),0,i%P);}
 // Real accepted-BEGIN range faults after ordered payload capture. c0 stays live
 // until origin E0; malformed unrelated live values must not be cached.
 auto x=input();
 for(int64_t q:{int64_t(B),-int64_t(B),int64_t(INT32_MIN),int64_t(INT32_MAX)}){
  h.reset();h.load(x);h.clear();h.d.c0[0]=uint32_t(int32_t(q));h.d.begin_canonical=1;
  h.d.eval();need(h.d.local_bound_bad,"FOLD_PAYLOAD_LIVE_BEFORE_ORIGIN");
  h.edge();h.quarantine(4);
 }
 h.reads=h.images=0;faults(h);h.sample();h.reads=h.images=0;normal(h);h.sample();
 std::cout<<"FOLD_PAYLOAD_BOUND_PASS aw=8 p=16 live_checks="<<checks
  <<" u32_base=1 signed_extrema=1 zero_always_bad=1 c1_priority=1 origin_faults=4 paired_edges=1 os_threads_peak="<<peak_os_threads<<" runtime_contexts=1\n";
}


void corrections(H& h){
 const std::array<uint32_t,8> bases={599,600,1009,1013,131077,604832956,999999937,1000000000};
 for(unsigned index=0;index<bases.size();index++){
  uint32_t base=bases[index];Image x{};std::vector<s4_full_reference::I> effective(N);
  std::array<int32_t,P> q0{},q1{};
  for(unsigned a=0;a<N;a++){x[a]=int32_t((uint64_t(a)*771+37+index)%base);effective[a]=x[a];}
  for(unsigned b=0;b<P;b++){
   q0[b]=(b&1)?int32_t(base-1):-int32_t(base-1);
   q1[b]=(b&2)?896:-896;
   effective[b*T]+=q0[b];effective[b*T+1]+=q1[b];
  }
  auto gold=s4_full_reference::small_whole_integer(effective,base);
  bool special=gold[0]==-1;for(unsigned a=1;a<N;a++)if(special)need(gold[a]==0,"FOLD_PAYLOAD_SENTINEL_ORACLE");
  h.reset();h.clear();h.d.base=base;
  for(unsigned r=0;r<T;r++){
   h.d.load_valid=1;h.d.load_row=r;
   for(unsigned b=0;b<P;b++)h.d.load_data[b]=uint32_t(x[b*T+r]);
   h.edge();need(!h.d.local_error&&!h.d.local_busy,"FOLD_PAYLOAD_LIVE_BASE_LOAD");
  }
  h.clear();for(unsigned b=0;b<P;b++){h.d.c0[b]=uint32_t(q0[b]);h.d.c1[b]=uint32_t(q1[b]);}
  h.d.begin_canonical=1;h.edge();need(h.d.local_busy&&!h.d.local_error,"FOLD_PAYLOAD_ACCEPTED_BEGIN");
  // Only accepted-BEGIN threshold/correction snapshots govern active processing.
  h.clear();h.d.base=0;for(unsigned b=0;b<P;b++)h.d.c0[b]=h.d.c1[b]=0x7fffffffu;
  h.run(special);Image expected{};std::copy(gold.begin(),gold.end(),expected.begin());h.all(expected);
 }
 need(h.images==10&&h.reads==2564,"FOLD_PAYLOAD_ALL_NORMAL_COUNTS");
}
}
int main(int argc,char** argv){try{
 H h(argc,argv);
 if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(h.context,h.d);
 if(argc==1){normal(h);corrections(h);h.sample();
  std::cout<<"FOLD_PAYLOAD_PAIR_NORMAL_PASS aw=8 p=16 images=10 signed96_reads=2564 correction_images=8 dirty_read=1 consecutive_reads=3 special_sentinel=1 paired_edges=1 os_threads_peak="<<peak_os_threads<<"\n";return 0;}
 if(argc==2&&std::string(argv[1])=="--wrong-word"){normal(h);h.clear();h.d.read_req=1;h.d.read_address=0;h.edge();h.d.read_req=0;h.edge();h.word(0,0,true);
  throw std::runtime_error("FOLD_PAYLOAD_WRONG_WORD_MISSED");}
 need(argc==2&&std::string(argv[1])=="--bounds","FOLD_PAYLOAD_ARGUMENTS");bounds(h);return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
