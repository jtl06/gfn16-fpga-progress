// Private paired canonical interface. Latency differs; published payload does not.
#include "Vgenefer_stream27_r15_canonical_foldstage_pair_v1.h"
#include "native_runtime_context_v1.h"
#include "stream27_host_chain_full_reference_v1.h"
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>

#ifndef GFN16_CANON_AW
#define GFN16_CANON_AW 8
#endif
namespace {
constexpr unsigned AW=GFN16_CANON_AW,N=1u<<AW,P=16,T=N/P,K=2*N+24*P;
constexpr uint32_t MINBASE=(2*N+5)>((2*K+2)/3+1)?(2*N+5):((2*K+2)/3+1);
using Image=std::vector<int32_t>;
void need(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
struct Runtime:VerilatedContext{Runtime(int argc,char** argv){gfn16_runtime::configure(*this,argc,argv);}};
class H {
public:
 Runtime context;Vgenefer_stream27_r15_canonical_foldstage_pair_v1 d;
 unsigned images=0,reads=0;uint64_t old_total=0,new_total=0;
 H(int argc,char** argv):context(argc,argv),d(&context){
  need(gfn16_runtime::matches(context,d),"FOLDSTAGE_RUNTIME");
  unsigned threads=0;for(const auto& task:std::filesystem::directory_iterator("/proc/self/task")){(void)task;++threads;}
  need(threads==1,"FOLDSTAGE_OS_THREADS");d.clk=1;d.rst_n=0;clear();d.base=MINBASE;
  d.load_row=d.read_address=0;for(unsigned b=0;b<P;++b)d.load_data[b]=d.c0[b]=d.c1[b]=0;d.eval();
 }
 void clear(){d.load_valid=d.begin_canonical=d.read_req=0;}
 void edge(){d.eval();d.clk=0;context.timeInc(1);d.eval();d.clk=1;context.timeInc(1);d.eval();}
 void quiet(){need(!d.parent_busy&&!d.local_busy&&!d.parent_done&&!d.local_done&&!d.parent_error&&!d.local_error&&
  !d.parent_image_valid&&!d.local_image_valid&&!d.parent_read_valid&&!d.local_read_valid,"FOLDSTAGE_RESET_ELIGIBILITY");}
 void reset(){clear();d.rst_n=0;d.eval();quiet();edge();quiet();d.rst_n=1;d.base=MINBASE;
  for(unsigned b=0;b<P;++b)d.c0[b]=d.c1[b]=0;edge();quiet();}
 void load(const Image& x,uint32_t base){clear();d.base=base;for(unsigned r=0;r<T;++r){
  d.load_valid=1;d.load_row=r;for(unsigned b=0;b<P;++b)d.load_data[b]=uint32_t(x[b*T+r]);edge();
  need(!d.parent_error&&!d.local_error&&!d.parent_busy&&!d.local_busy,"FOLDSTAGE_LOAD");}clear();}
 void begin(uint32_t base,const Image& q0,const Image& q1){clear();d.base=base;
  for(unsigned b=0;b<P;++b){d.c0[b]=uint32_t(q0[b]);d.c1[b]=uint32_t(q1[b]);}
  d.begin_canonical=1;edge();clear();need(d.parent_busy&&d.local_busy&&!d.parent_error&&!d.local_error&&
   d.parent_cycles==0&&d.local_cycles==0,"FOLDSTAGE_BEGIN");}
 void run(bool special){uint64_t old_count=(9u+unsigned(special))*N,new_count=(12u+unsigned(special))*N;
  // Active processing must use the accepted profile, never these dirty pins.
  clear();d.base=0;for(unsigned b=0;b<P;++b)d.c0[b]=d.c1[b]=0x7fffffffu;
  for(uint64_t age=1;age<=new_count;++age){edge();
   need(!d.parent_error&&!d.local_error,"FOLDSTAGE_SERVICE_ERROR");
   need(d.parent_cycles==std::min(age,old_count)&&d.local_cycles==age,"FOLDSTAGE_SERVICE_CYCLES");
   need(bool(d.parent_done)==(age==old_count)&&bool(d.local_done)==(age==new_count),"FOLDSTAGE_DONE_PULSE");
   need(bool(d.parent_image_valid)==(age>=old_count)&&bool(d.local_image_valid)==(age>=new_count),"FOLDSTAGE_IMAGE_ELIGIBILITY");
   need(bool(d.parent_busy)==(age<old_count)&&bool(d.local_busy)==(age<new_count),"FOLDSTAGE_BUSY");
  }old_total+=old_count;new_total+=new_count;++images;
 }
 void word(unsigned addr,int32_t value,bool wrong=false){need(d.parent_read_valid&&d.local_read_valid&&
  d.parent_read_address_out==addr&&d.local_read_address_out==addr,"FOLDSTAGE_READ_E1_ADDRESS");
  uint32_t sign=value<0?0xffffffffu:0u;
  for(unsigned k=0;k<3;++k){uint32_t expected=k?sign:uint32_t(value);
   if(d.parent_read_data[k]!=expected||d.local_read_data[k]!=expected)
    throw std::runtime_error(wrong?"FOLDSTAGE_WRONG_WORD":"FOLDSTAGE_SIGNED96_ORACLE");}++reads;
 }
 void all(const Image& expected){clear();d.read_req=1;d.read_address=0;edge();
  need(!d.parent_read_valid&&!d.local_read_valid,"FOLDSTAGE_READ_E0");
  for(unsigned a=1;a<N;++a){d.read_address=a;edge();word(a-1,expected[a-1]);}clear();edge();word(N-1,expected[N-1]);}
 void image(const Image& x,uint32_t base,const Image& q0,const Image& q1){
  std::vector<s4_full_reference::I> represented(x.begin(),x.end());
  for(unsigned b=0;b<P;++b){represented[b*T]+=q0[b];represented[b*T+1]+=q1[b];}
  auto gold=s4_full_reference::canonical(represented,base);
  if(N<=256)need(gold==s4_full_reference::small_whole_integer(represented,base),"FOLDSTAGE_SMALL_INTEGER_SELF_CHECK");
  bool special=gold[0]==-1;if(special)for(unsigned a=1;a<N;++a)need(gold[a]==0,"FOLDSTAGE_SENTINEL_ORACLE");
  reset();load(x,base);begin(base,q0,q1);run(special);all(gold);
 }
 void sticky(unsigned code){need(d.parent_error&&d.local_error&&d.parent_error_code==code&&d.local_error_code==code&&
  !d.parent_busy&&!d.local_busy&&!d.parent_image_valid&&!d.local_image_valid&&!d.parent_read_valid&&!d.local_read_valid,"FOLDSTAGE_FAULT_CODE");
  for(unsigned k=0;k<4;++k){d.load_valid=d.begin_canonical=d.read_req=1;edge();need(d.parent_error&&d.local_error&&
    d.parent_error_code==code&&d.local_error_code==code&&!d.parent_image_valid&&!d.local_image_valid,"FOLDSTAGE_STICKY");}clear();}
};
Image pattern(uint32_t base,unsigned salt=0){Image x(N);for(unsigned a=0;a<N;++a)x[a]=int32_t((uint64_t(a)*771+37+salt)%base);return x;}
void normal(H& h){Image q0(P),q1(P),zero(N);h.image(pattern(MINBASE),MINBASE,q0,q1);
 q0[0]=-1;h.image(zero,MINBASE,q0,q1);q0[0]=0;
 for(uint32_t base:{MINBASE,604832956u,1000000000u}){
  for(unsigned b=0;b<P;++b){q0[b]=(b&1)?int32_t(base-1):-int32_t(base-1);q1[b]=(b&2)?int32_t(K):-int32_t(K);}
  h.image(pattern(base,9),base,q0,q1);
 }
 // Published reads remain independent of unrelated malformed live inputs.
 h.clear();h.d.base=0;for(unsigned b=0;b<P;++b)h.d.c0[b]=h.d.c1[b]=0x7fffffffu;
 auto x=pattern(1000000000u,9);std::vector<s4_full_reference::I> v(x.begin(),x.end());
 for(unsigned b=0;b<P;++b){v[b*T]+=q0[b];v[b*T+1]+=q1[b];}auto gold=s4_full_reference::canonical(v,1000000000u);
 h.d.read_req=1;h.d.read_address=17;h.edge();need(!h.d.parent_read_valid&&!h.d.local_read_valid,"FOLDSTAGE_DIRTY_READ_E0");
 h.clear();h.edge();h.word(17,gold[17]);h.d.read_req=1;h.d.read_address=31;h.edge();
 for(unsigned a=32;a<=33;++a){h.d.read_address=a;h.edge();h.word(a-1,gold[a-1]);}h.clear();h.edge();h.word(33,gold[33]);
 need(h.images==5&&h.reads==5*N+4&&h.new_total-h.old_total==15ull*N,"FOLDSTAGE_NORMAL_COUNTS");
 std::cout<<"R15_FOLDSTAGE_NORMAL_PASS aw="<<AW<<" p=16 images=5 signed96_reads="<<h.reads
  <<" delta_per_image="<<3*N<<" normal_parent="<<9*N<<" normal_candidate="<<12*N
  <<" special_parent="<<10*N<<" special_candidate="<<13*N
  <<" independent_integer=1 dirty_read=1 II1_read=1 runtime_threads=1\n";
}
void faults(H& h){Image q0(P),q1(P),x=pattern(MINBASE);unsigned cases=0;
 h.reset();h.d.read_req=1;h.edge();h.sticky(5);++cases;
 h.reset();h.load(x,MINBASE);h.d.begin_canonical=1;h.d.c0[0]=MINBASE;h.edge();h.sticky(4);++cases;
 h.reset();h.d.load_valid=h.d.begin_canonical=1;h.d.base=0;h.edge();h.sticky(1);++cases;
 // Genuine two-fault protocol: legal load under larger base then legal begin
 // under MINBASE. DIGIT has priority over out-of-fold INTERNAL at PROCESS.
 Image bad(N);bad[0]=int32_t(4*MINBASE);h.reset();h.load(bad,1000000000u);q0[0]=int32_t(MINBASE-1);
 h.begin(MINBASE,q0,q1);for(unsigned age=1;age<=4;++age){h.edge();
  need(bool(h.d.parent_error)==(age>=3)&&bool(h.d.local_error)==(age>=4),"FOLDSTAGE_PROCESS_FAULT_EDGE");
  if(age>=3)need(h.d.parent_error_code==6,"FOLDSTAGE_PARENT_DIGIT_PRIORITY");
  if(age>=4)need(h.d.local_error_code==6,"FOLDSTAGE_LOCAL_DIGIT_PRIORITY");}h.sticky(6);++cases;
 q0[0]=0;
 // First and final READ/VALUE/FOLD/PROCESS eligibility windows; no payload
 // zero assumption. Reset kills all pending authority, then full recovery.
 for(unsigned phase=0;phase<4;++phase){h.reset();h.load(x,MINBASE);h.begin(MINBASE,q0,q1);
  for(unsigned k=0;k<phase;++k)h.edge();h.reset();for(unsigned k=0;k<5;++k){h.edge();h.quiet();}
  h.image(x,MINBASE,q0,q1);++cases;}
 for(unsigned phase=0;phase<4;++phase){h.reset();h.load(x,MINBASE);h.begin(MINBASE,q0,q1);
  for(unsigned k=0;k<12*N-4+phase;++k)h.edge();h.reset();for(unsigned k=0;k<5;++k){h.edge();h.quiet();}
  h.image(x,MINBASE,q0,q1);++cases;}
 need(cases==12&&h.images==8&&h.reads==8*N,"FOLDSTAGE_FAULT_COUNTS");
 std::cout<<"R15_FOLDSTAGE_FAULT_PASS aw="<<AW<<" cases=12 phase_resets=8 recovery_reads="<<h.reads
  <<" digit_internal_priority=1 parent_fault_age=3 candidate_fault_age=4 payload_zero_assumed=0 runtime_threads=1\n";
}
}
int main(int argc,char** argv){try{H h(argc,argv);
 if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(h.context,h.d);
 if(argc==1){normal(h);return 0;}
 if(argc==2&&std::string(argv[1])=="--fault"){faults(h);return 0;}
 if(argc==2&&std::string(argv[1])=="--wrong-word"){Image x=pattern(MINBASE),q(P);h.image(x,MINBASE,q,q);
  h.clear();h.d.read_req=1;h.d.read_address=0;h.edge();h.clear();h.edge();h.word(0,x[0]+1,true);
  throw std::runtime_error("FOLDSTAGE_WRONG_WORD_MISSED");}
 throw std::runtime_error("FOLDSTAGE_ARGUMENTS");
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
