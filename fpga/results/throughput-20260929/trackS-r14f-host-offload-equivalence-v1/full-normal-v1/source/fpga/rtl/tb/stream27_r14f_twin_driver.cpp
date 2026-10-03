// Native-only C2 context-alone versus joint full-image comparison.
// No simulated arithmetic or image overlay is substituted for real host RAM.
#include "s4_p16_two_context_full_config.h"
#include "stream27_host_chain_full_reference_v1.h"
#include "native_runtime_context_v1.h"
#include "verilated.h"
#include <array>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
static_assert(AW==16&&P==16&&N==65536,"R84 full P16 C2 only");
static void need(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
using Image=std::vector<int32_t>;
using Word=std::array<uint32_t,3>;
using WideImage=std::vector<Word>;
static uint32_t lane32(uint64_t data,unsigned ctx){return uint32_t(data>>(ctx*32));}
static uint64_t lane64(const VlWide<4>& data,unsigned ctx){return uint64_t(data[2*ctx])|(uint64_t(data[2*ctx+1])<<32);}
static uint64_t owner(unsigned ctx){return (uint64_t(COUNT-1)<<24)|(uint64_t(uint16_t(EPOCHS[ctx]+COUNT-1))<<8)|1u;}
static void clear(DUT& d){
 d.host_context=d.load_we=d.read_en=0;d.host_addr=d.write_data=0;
 d.start_contexts=d.batch_mode=d.feed_mode=d.double_bit=0;d.base=d.warm_count=d.double_mask=0;
 d.command_context=d.command_valid=d.command_double=0;d.command_index=d.command_generation=0;
 for(unsigned i=0;i<2*P;i++)d.initial_c0[i]=d.initial_c1[i]=0;
}
static void eq_pre(DUT& d);
static void eq_read(DUT& d,unsigned c,unsigned address);
static void edge(DUT& d){d.clk=0;d.eval();eq_pre(d);d.clk=1;d.eval();d.clk=0;d.eval();}
static Image initial(unsigned ctx){
 Image out(N);uint32_t state=SEEDS[ctx];
 for(unsigned j=0;j<N;j++){state^=state<<13;state^=state>>17;state^=state<<5;out[j]=int32_t(state%BASES[ctx]);}
 out[17]=-1;out[N-1]=-1;return out;
}
static Word read(DUT& d,unsigned ctx,unsigned address,const Image& reference){
 need(d.read_valid&&d.read_context==ctx&&uint64_t(d.read_owner)==owner(ctx),"R84_READ_CONTEXT_OWNER ctx="+std::to_string(ctx)+" address="+std::to_string(address));
 Word actual={d.read_data[0],d.read_data[1],d.read_data[2]};
 const int32_t expected=reference[address];const uint32_t sign=expected<0?0xffffffffu:0u;
 need(actual==Word{uint32_t(expected),sign,sign},"R84_FULL_SIGNED96_REFERENCE ctx="+std::to_string(ctx)+" address="+std::to_string(address));
 eq_read(d,ctx,address);
 return actual;
}
struct Result{
 std::array<WideImage,2> image;std::array<uint64_t,2> done{},warm{};
 std::array<uint64_t,2> setup{};
 std::array<std::vector<uint64_t>,2> launches;
 uint64_t cycles=0,reads=0,overlap=0,peer_reads=0;
};
static Result run(DUT& d,unsigned mask,const std::array<Image,2>& input,const std::array<Image,2>& reference){
 Result result;for(unsigned ctx=0;ctx<2;ctx++)if(mask&(1u<<ctx))result.image[ctx].resize(N);
 clear(d);d.rst_n=0;edge(d);need(!d.error&&!d.busy&&!d.done&&!d.read_valid&&!d.canonical_ready&&!d.operations_started&&!d.completed_squares,"R84_RESET_PUBLICATION");
 d.rst_n=1;clear(d);edge(d);
 for(unsigned ctx=0;ctx<2;ctx++)if(mask&(1u<<ctx))for(unsigned address=0;address<N;address++){
  clear(d);d.host_context=ctx;d.host_addr=address;d.write_data=uint32_t(input[ctx][address]);d.load_we=d.read_en=1;
  edge(d);need(!d.error&&!d.busy&&!d.read_valid&&!d.canonical_ready,"R84_COLD_LOAD_PRIORITY");
 }
 clear(d);d.start_contexts=d.batch_mode=mask;
 d.base=uint64_t(BASES[0])|(uint64_t(BASES[1])<<32);d.warm_count=uint64_t(COUNT)|(uint64_t(COUNT)<<32);
 d.double_bit=(BITS[0][0]?1u:0u)|(BITS[1][0]?2u:0u);
 d.double_mask=uint64_t(BITS[0][1]<<1)|(uint64_t(BITS[1][1]<<1)<<32);
 edge(d);need(d.busy==mask&&!d.error&&!d.canonical_ready&&!d.done,"R84_START_EXACT_CONTEXTS");
 std::array<unsigned,2> next_read{},done_count{},previous_started{},setup_count{};unsigned published=0;
 std::array<uint64_t,2> first{};
 for(uint64_t age=1;age<=MAX_EDGES;age++){
  clear(d);int selected=-1;unsigned address=0;
  for(unsigned ctx=0;ctx<2;ctx++)if((mask&(1u<<ctx))&&(d.canonical_ready&(1u<<ctx))&&next_read[ctx]<N){selected=int(ctx);address=next_read[ctx];break;}
  if(selected>=0){d.read_en=1;d.host_context=unsigned(selected);d.host_addr=address;}
  else if(d.busy){d.read_en=1;d.host_context=(d.busy&1u)?0:1;d.host_addr=unsigned(age%N);}
  const bool peer_live=selected>=0&&(d.busy&(1u<<(1-unsigned(selected))));
  edge(d);need(!d.error,"R84_ACTUAL_C2_ERROR age="+std::to_string(age));
  need(!d.command_accept&&!d.operation_accept&&!d.feed_level,"R84_MASK_MODE_NO_FEED");
  if(d.dbg_setup_done){unsigned ctx=d.dbg_setup_context;need(mask&(1u<<ctx),"R84_SETUP_CONTEXT");setup_count[ctx]++;result.setup[ctx]=age;}
  for(unsigned ctx=0;ctx<2;ctx++){
   const bool enabled=mask&(1u<<ctx);
   const unsigned started=lane32(d.operations_started,ctx);
   if(started&&!first[ctx]){first[ctx]=age;need(setup_count[ctx]==1&&age>result.setup[ctx],"R84_FIRST_AFTER_PROFILE");}
   const uint64_t begin=first[ctx];
   const unsigned launched=!enabled||!begin||age<begin?0:std::min(COUNT,1u+unsigned((age-begin)/INTERVAL));
   const unsigned completed=!enabled||!begin||age<begin+CARRY_DONE+1?0:std::min(COUNT,1u+unsigned((age-begin-CARRY_DONE-1)/INTERVAL));
   need(started==launched&&lane32(d.completed_squares,ctx)==completed,"R84_EXACT_CONTEXT_CALENDAR age="+std::to_string(age)+" ctx="+std::to_string(ctx));
   if(started!=previous_started[ctx]){need(started==previous_started[ctx]+1,"R84_SINGLE_CONTEXT_LAUNCH");result.launches[ctx].push_back(age);previous_started[ctx]=started;}
   const uint64_t digit=begin+uint64_t(COUNT-1)*INTERVAL+FIRST_DIGIT;
   const unsigned rows=enabled&&begin&&age>digit?std::min(T,unsigned(age-digit)):0;
   need(lane32(d.final_image_rows,ctx)==rows,"R84_TRUE_LAST_ROWS");
   const bool warm=enabled&&begin&&age==begin+uint64_t(COUNT-1)*INTERVAL+CARRY_DONE+1;
   need(bool(d.warm_done&(1u<<ctx))==warm,"R84_WARM_COMPLETION");
   if(warm){result.warm[ctx]=age;need(!(d.canonical_ready&(1u<<ctx)),"R84_WARM_NOT_PUBLISHED");}
   if(d.done&(1u<<ctx)){
    done_count[ctx]++;result.done[ctx]=age;
    need(enabled&&(d.canonical_ready&(1u<<ctx))&&!(d.busy&(1u<<ctx)),"R84_DONE_PUBLICATION");
    need(lane64(d.canonical_cycles,ctx)==9*N&&lane64(d.image_copy_cycles,ctx)==N+4,"R84_REAL_CANONICAL_COPY_COST");
    need(age>result.warm[ctx]+9*N+N,"R84_NO_SHORTCUT_PUBLICATION");
   }
   if(d.dbg_config_valid&(1u<<ctx)){
    need(lane32(d.dbg_base,ctx)==BASES[ctx]&&((d.dbg_generation>>(8*ctx))&255u)==1,"R84_PER_CONTEXT_BASE_GENERATION");
    // Observe wide payload at the actual setup edge and periodically thereafter.
    // The profile has no write path during this run; base/gen remain checked II1.
    if(d.dbg_setup_done||!(age&4095u)){
    const auto expected_recip=(s4_full_reference::U(1)<<96)/BASES[ctx];
    s4_full_reference::U reciprocal=0,limit=0;
    for(unsigned w=0;w<3;w++)reciprocal|=s4_full_reference::U(d.dbg_reciprocal[ctx*3+w])<<(32*w);
    // Limits have77 bits and are packed on77-bit boundaries.
    for(unsigned bit=0;bit<77;bit++)limit|=s4_full_reference::U((d.dbg_limit[(ctx*77+bit)/32]>>((ctx*77+bit)%32))&1u)<<bit;
    const s4_full_reference::U b=BASES[ctx]-1,k=2*N+24*P;
    const auto expected_limit=2*((N+3*P)*b*b+4*P*b*k+P*k*k);
    need(lane32(d.dbg_base,ctx)==BASES[ctx]&&reciprocal==expected_recip&&limit==expected_limit&&((d.dbg_generation>>(8*ctx))&255u)==1,"R84_PER_CONTEXT_PROFILE_SNAPSHOT");
    }
   }
  }
  if(d.busy==3)result.overlap++;
  need((published&unsigned(d.canonical_ready))==published&&!(d.canonical_ready&~mask),"R84_PUBLICATION_ISOLATION");published=d.canonical_ready;
  if(selected>=0){result.image[selected][address]=read(d,unsigned(selected),address,reference[selected]);next_read[selected]++;result.reads++;result.peer_reads+=peer_live;}
  else need(!d.read_valid,"R84_UNPUBLISHED_READ_KILL");
  if(published==mask&&((!(mask&1))||next_read[0]==N)&&((!(mask&2))||next_read[1]==N)){
   result.cycles=age;break;
  }
 }
 need(result.cycles>0&&!d.busy,"R84_BOUNDED_ACTUAL_COMPLETION");
 for(unsigned ctx=0;ctx<2;ctx++)need(done_count[ctx]==unsigned(bool(mask&(1u<<ctx))),"R84_ONE_DONE_PER_CONTEXT");
 if(mask==3){
  need(first[1]-first[0]==INTERVAL/2,"R84_BALANCED_FIRST_GAP");
  need(result.overlap>0&&result.peer_reads==N&&result.done[0]<result.done[1],"R84_ACTUAL_PEER_OVERLAP");
  for(unsigned address=0;address<N;address++)for(unsigned ctx=0;ctx<2;ctx++){
   clear(d);d.read_en=1;d.host_context=ctx;d.host_addr=address;edge(d);
   need(!d.error&&!d.busy&&!d.done&&d.canonical_ready==3,"R84_FINAL_IMAGES_STABLE");
   need(read(d,ctx,address,reference[ctx])==result.image[ctx][address],"R84_ALTERNATING_CONTEXT_READ");result.reads++;
  }
 }
 clear(d);edge(d);need(!d.read_valid&&!d.done&&!d.error,"R84_FINAL_READ_DRAIN");return result;
}
int main(int argc,char**argv){try{
 VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d{&context};
 if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
 need(argc==1&&gfn16_runtime::matches(context,d),"R84_ARGUMENTS_THREADS");
 auto begin=std::chrono::steady_clock::now();s4_full_reference::self_check();
 std::array<Image,2> input={initial(0),initial(1)},reference=input;
 for(unsigned ctx=0;ctx<2;ctx++)for(unsigned ordinal=0;ordinal<COUNT;ordinal++)reference[ctx]=s4_full_reference::square(reference[ctx],BASES[ctx],BITS[ctx][ordinal]);
 need(reference[0]!=reference[1]&&reference[0][0]!=-1&&reference[1][0]!=-1,"R84_DISTINCT_ORDINARY_REFERENCE");
 Result single0=run(d,1,input,reference),single1=run(d,2,input,reference),joint=run(d,3,input,reference);
 need(joint.image[0]==single0.image[0]&&joint.image[1]==single1.image[1],"R84_FULL_CONTEXT_ALONE_BIT_IDENTITY");
 need(joint.launches[0].size()==COUNT&&joint.launches[1].size()==COUNT,"R84_LAUNCH_COVERAGE");
 double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
 std::cout<<"R84_C2_FULL_PASS {\"aw\":16,\"p\":16,\"contexts\":2,\"bases\":["<<BASES[0]<<","<<BASES[1]<<"],\"squares\":8,\"reads\":"<<single0.reads+single1.reads+joint.reads
  <<",\"signed96\":true,\"context_alone_bit_identical\":true,\"independent_reference\":true,\"interval\":"<<INTERVAL
  <<",\"pair_launch_cycles\":"<<joint.launches[0][1]-joint.launches[0][0]<<",\"launches\":[["<<joint.launches[0][0]<<","<<joint.launches[0][1]<<"],["<<joint.launches[1][0]<<","<<joint.launches[1][1]<<"]]"
  <<",\"single_cycles\":["<<single0.cycles<<","<<single1.cycles<<"],\"joint_cycles\":"<<joint.cycles<<",\"overlap_edges\":"<<joint.overlap<<",\"peer_live_reads\":"<<joint.peer_reads
  <<",\"done_edges\":["<<joint.done[0]<<","<<joint.done[1]<<"],\"warm_edges\":["<<joint.warm[0]<<","<<joint.warm[1]<<"],\"setup_edges\":["<<joint.setup[0]<<","<<joint.setup[1]<<"],\"single_first\":["<<single0.launches[0][0]<<","<<single1.launches[1][0]<<"],\"model_threads\":"<<d.threads()<<",\"seconds\":"<<seconds<<"}\n";
 d.final();return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
