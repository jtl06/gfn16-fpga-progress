// Private R14-F ON-only continuous source pilot. No twin, reload or checkpoint.
#include "s4_p16_two_context_full_config.h"
#include "stream27_host_chain_full_reference_v1.h"
#include "stream27_host_offload_host_v2.h"
#include "native_runtime_context_v1.h"
#include "verilated.h"
#include <array>
#include <chrono>
#include <iostream>
#include <stdexcept>
#include <vector>
using Image=std::vector<int32_t>;
using Bytes=std::vector<uint8_t>;
static_assert(AW==16&&P==16&&N==65536,"R14-F full P16 only");
static void need(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
static uint32_t lane32(uint64_t v,unsigned c){return uint32_t(v>>(32*c));}
static uint64_t owner(unsigned c){return (uint64_t(COUNT-1)<<24)|(uint64_t(uint16_t(EPOCHS[c]+COUNT-1))<<8)|1u;}
static void put(Bytes& b,uint32_t v){size_t p=b.size();b.resize(p+4);gfn16_b_store32(b.data()+p,v);}
static Image initial(unsigned c){Image x(N);uint32_t s=SEEDS[c];for(auto& v:x){s^=s<<13;s^=s>>17;s^=s<<5;v=int32_t(s%BASES[c]);}x[17]=x[N-1]=-1;return x;}
static void clear(DUT& d){
 d.host_context=d.load_we=d.read_en=0;d.host_addr=d.write_data=0;
 d.start_contexts=d.batch_mode=d.feed_mode=d.double_bit=0;d.base=d.warm_count=d.double_mask=0;
 d.command_context=d.command_valid=d.command_double=0;d.command_index=d.command_generation=0;
 for(unsigned i=0;i<2*P;i++)d.initial_c0[i]=d.initial_c1[i]=0;
 d.off_begin=d.off_write=d.off_commit=d.off_context=0;d.off_index=d.off_word=d.off_base=d.off_generation=d.off_epoch=0;
 for(unsigned i=0;i<3;i++)d.off_reciprocal[i]=d.off_limit[i]=0;
 d.off_raw_ready=d.off_boundary_ready=1;
}
static std::array<Bytes,2> raw;
static std::array<unsigned,2> rows{},boundaries{};
static bool capture=false;
static void edge(DUT& d){
 d.clk=0;d.eval();
 if(capture&&d.off_raw_valid){unsigned c=d.off_raw_context;
  need(c<2&&d.off_raw_ready&&d.off_raw_owner==owner(c)&&rows[c]<T&&d.off_raw_row==rows[c]&&!boundaries[c],"R14F_LONG_RAW_OWNER_ORDER");
  for(unsigned l=0;l<P;l++)put(raw[c],d.off_raw_data[l]);rows[c]++;
 }
 if(capture&&d.off_boundary_valid){unsigned c=d.off_boundary_context;
  need(c<2&&d.off_boundary_ready&&rows[c]==T&&!boundaries[c]&&d.off_boundary_owner==owner(c),"R14F_LONG_BOUNDARY_OWNER");
  for(unsigned l=0;l<P;l++)put(raw[c],d.off_c0[l]);for(unsigned l=0;l<P;l++)put(raw[c],d.off_c1[l]);boundaries[c]++;
 }
 d.clk=1;d.eval();d.clk=0;d.eval();
}
int main(int argc,char** argv){try{
 VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d(&context);
 if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
 need(argc==1&&gfn16_runtime::matches(context,d),"R14F_LONG_ARGUMENTS_RUNTIME");
 using Clock=std::chrono::steady_clock;auto begin=Clock::now();
 s4_full_reference::self_check();std::array<Image,2> input={initial(0),initial(1)},expected=input;
 for(unsigned c=0;c<2;c++)for(unsigned k=0;k<COUNT;k++)expected[c]=s4_full_reference::square(expected[c],BASES[c],BITS[c][k]);
 auto reference_end=Clock::now();
 std::array<Bytes,2> profile,cold;
 clear(d);d.rst_n=0;edge(d);need(!d.error&&!d.off_error&&!d.off_loaded&&!d.off_done&&!d.off_raw_valid&&!d.off_boundary_valid,"R14F_LONG_RESET");
 d.rst_n=1;edge(d);
 for(unsigned c=0;c<2;c++){
  Bytes digits,correction(128,0);for(auto v:input[c])put(digits,uint32_t(v));
  profile[c].resize(32);cold[c].resize(4*(3*N+96));uint64_t own=(uint64_t(EPOCHS[c])<<8)|1u;
  need(!gfn16_b_profile_make(N,BASES[c],1,profile[c].data(),32),"R14F_LONG_PROFILE_C");
  need(!gfn16_b_cold_write(N,profile[c].data(),32,c,c,own,own,digits.data(),digits.size(),correction.data(),correction.size(),cold[c].data(),cold[c].size()),"R14F_LONG_COLD_C");
  clear(d);d.off_begin=1;d.off_context=c;d.off_base=BASES[c];d.off_generation=1;d.off_epoch=EPOCHS[c];
  for(unsigned i=0;i<3;i++){d.off_reciprocal[i]=gfn16_b_load32(profile[c].data()+8+4*i);d.off_limit[i]=gfn16_b_load32(profile[c].data()+20+4*i);}edge(d);
  for(unsigned j=0;j<3*N+96;j++){clear(d);d.off_write=1;d.off_context=c;d.off_index=j;d.off_word=gfn16_b_load32(cold[c].data()+4*j);edge(d);
   need(!d.error&&!d.off_error&&!(d.off_loaded&(1u<<c))&&!d.off_done,"R14F_LONG_PARTIAL_INPUT");}
  clear(d);d.off_commit=1;d.off_context=c;edge(d);need(!d.error&&!d.off_error&&(d.off_loaded&(1u<<c)),"R14F_LONG_INPUT_COMMIT");
 }
 clear(d);d.start_contexts=d.batch_mode=d.feed_mode=3;
 d.base=uint64_t(BASES[0])|(uint64_t(BASES[1])<<32);d.warm_count=uint64_t(COUNT)|(uint64_t(COUNT)<<32);
 d.double_bit=BITS[0][0]|(BITS[1][0]<<1);edge(d);
 need(!d.error&&!d.off_error&&d.busy==3&&d.accepted_generation==0x0101,"R14F_LONG_JOINT_START");
 std::array<unsigned,2> next{1,1},warm{},done{},launches{};uint64_t overlap=0,cycles=0;capture=true;
 for(uint64_t age=1;age<MAX_EDGES;age++){
  clear(d);unsigned c=unsigned(age&1u);
  if(next[c]<COUNT){d.command_valid=1;d.command_context=c;d.command_generation=1;d.command_index=next[c];d.command_double=BITS[c][next[c]];}
  d.clk=0;d.eval();bool accepted=d.command_accept;edge(d);if(accepted)next[c]++;
  need(!d.error&&!d.off_error&&!d.canonical_ready&&!d.read_valid,"R14F_LONG_NO_FAULT_OR_CANONICAL");
  need((d.feed_level&7u)<=4&&((d.feed_level>>3)&7u)<=4,"R14F_LONG_DESCRIPTOR_CAPACITY");
  if(d.busy==3)overlap++;
  for(unsigned q=0;q<2;q++){
   uint64_t first=204+q*(INTERVAL/2),last=first+uint64_t(COUNT-1)*INTERVAL;
   unsigned launched=age<first?0:unsigned(std::min<uint64_t>(COUNT,1+(age-first)/INTERVAL));
   unsigned completed=age<first+CARRY_DONE+1?0:unsigned(std::min<uint64_t>(COUNT,1+(age-first-CARRY_DONE-1)/INTERVAL));
   need(lane32(d.operations_started,q)==launched&&lane32(d.completed_squares,q)==completed,"R14F_LONG_EVERY_EDGE_CALENDAR");
   if(launched>launches[q]){need(launched==launches[q]+1&&age==first+uint64_t(launches[q])*INTERVAL,"R14F_LONG_LAUNCH_EDGE");launches[q]++;}
   if(d.warm_done&(1u<<q)){need(!warm[q]&&age==last+CARRY_DONE+1,"R14F_LONG_WARM_EDGE");warm[q]=unsigned(age);}
   if(d.off_done&(1u<<q)){need(!done[q]&&warm[q]&&age==uint64_t(warm[q])+2&&rows[q]==T&&boundaries[q]==1&&!(d.busy&(1u<<q)),"R14F_LONG_RAW_DONE_W_PLUS_TWO");done[q]=unsigned(age);}
  }
  if(done[0]&&done[1]){cycles=age;break;}
 }
 need(cycles&&next==std::array<unsigned,2>{COUNT,COUNT}&&launches==next&&!d.busy&&!d.feed_level,"R14F_LONG_FINITE_NO_RELOAD");capture=false;
 for(unsigned c=0;c<2;c++){
  Bytes canonical(4*N);gfn16_b_final_info info{};
  need(raw[c].size()==4*(N+32)&&!gfn16_b_final_decode(N,profile[c].data(),32,c,c,owner(c),owner(c),raw[c].data(),raw[c].size(),canonical.data(),canonical.size(),&info),"R14F_LONG_FINAL_HOST_C");
  for(unsigned a=0;a<N;a++)need(gfn16_b_load32(canonical.data()+4*a)==uint32_t(expected[c][a]),"R14F_LONG_ALL_N_REFERENCE");
 }
 clear(d);edge(d);need(!d.off_done&&!d.off_raw_valid&&!d.off_boundary_valid&&!d.error&&!d.off_error,"R14F_LONG_FINAL_DRAIN");
 auto end=Clock::now();double ref=std::chrono::duration<double>(reference_end-begin).count(),model=std::chrono::duration<double>(end-reference_end).count();
 unsigned doubles=0;for(auto& r:BITS)for(auto b:r)doubles+=b;
 std::cout<<"R14F_LONG_PASS {\"count\":"<<COUNT<<",\"squares\":"<<2*COUNT<<",\"descriptors\":"<<2*(COUNT-1)<<",\"doubles\":"<<doubles
  <<",\"input_words\":"<<2*(3*N+96)<<",\"raw_words\":"<<2*(N+32)<<",\"checked_words\":"<<2*N<<",\"initial_resets\":1,\"model_threads\":"<<d.threads()
  <<",\"cycles\":"<<cycles<<",\"overlap_edges\":"<<overlap<<",\"warm_edges\":["<<warm[0]<<","<<warm[1]<<"],\"done_edges\":["<<done[0]<<","<<done[1]
  <<"],\"reference_seconds\":"<<ref<<",\"model_seconds\":"<<model<<",\"seconds\":"<<ref+model<<"}\n";
 d.final();return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
