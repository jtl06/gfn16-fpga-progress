// Private healthy PRP/twin evidence. No protected-detector test expectation.
#include "stream27_context_lean_prp_config.h"
#include "native_runtime_context_v1.h"
#include "verilated.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
static_assert(N==256&&P==16,"Supported own N256 C2 PRP only");
static bool negative_comparator=false,negative_schedule=false;
static void need(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
static unsigned count(unsigned ci){return ci<8?COUNTS[ci]:1u;}
static unsigned base(unsigned ci){return BASES[ci<8?ci:ci-8];}
static unsigned bit(unsigned ci,unsigned step){unsigned b=ci<8?unsigned(BITS[ci][step]-'0'):0u;return b^(negative_schedule&&ci==0&&step==count(ci)-1);}
static uint32_t lane32(uint64_t v,unsigned c){return uint32_t(v>>(32*c));}
static uint64_t lane64(const VlWide<4>& v,unsigned c){return uint64_t(v[2*c])|(uint64_t(v[2*c+1])<<32);}
static uint64_t owner(unsigned ci,unsigned c){return (uint64_t(count(ci)-1)<<24)|(uint64_t(uint16_t(EPOCHS[c]+count(ci)-1))<<8)|1u;}
static void clear(DUT& d){d.host_context=d.load_we=d.read_en=0;d.host_addr=d.write_data=0;d.start_contexts=d.batch_mode=d.feed_mode=d.double_bit=0;d.base=d.warm_count=d.double_mask=0;d.command_context=d.command_valid=d.command_double=0;d.command_index=d.command_generation=0;for(unsigned i=0;i<2*P;i++)d.initial_c0[i]=d.initial_c1[i]=0;}
static void edge(DUT& d){d.clk=0;d.eval();d.clk=1;d.eval();d.clk=0;d.eval();}
static unsigned total_squares=0,total_doubles=0,total_reads=0;
static void pair(DUT& d,unsigned first,bool sentinel){
 std::array<unsigned,2> ids={first,first+1},counts={count(first),count(first+1)};
 clear(d);d.rst_n=0;edge(d);need(!d.error&&!d.busy&&!d.done&&!d.canonical_ready&&!d.read_valid,"A_PRP_RESET");d.rst_n=1;edge(d);
 for(unsigned c=0;c<2;c++)for(unsigned a=0;a<N;a++){clear(d);d.host_context=c;d.host_addr=a;d.load_we=1;d.write_data=(a==(sentinel?N/2:0))?1u:0u;edge(d);need(!d.error&&!d.read_valid&&!d.canonical_ready,"A_PRP_COLD_LOAD");}
 clear(d);d.start_contexts=d.batch_mode=d.feed_mode=3;d.base=uint64_t(base(first))|(uint64_t(base(first+1))<<32);d.warm_count=uint64_t(counts[0])|(uint64_t(counts[1])<<32);d.double_bit=bit(first,0)|(bit(first+1,0)<<1);edge(d);need(d.busy==3&&!d.error,"A_PRP_START");
 std::array<unsigned,2> next={1,1},read{},done_count{};std::array<uint64_t,2> done_edges{};
 std::array<std::vector<int32_t>,2> actual={std::vector<int32_t>(N),std::vector<int32_t>(N)};
 unsigned published=0;uint64_t end=0;const uint64_t limit=uint64_t(std::max(counts[0],counts[1]))*INTERVAL+33*N+10000;
 for(uint64_t age=1;age<limit;age++){
  clear(d);const unsigned offer=unsigned(age&1u);if(next[offer]<counts[offer]){d.command_context=offer;d.command_valid=1;d.command_generation=1;d.command_index=next[offer];d.command_double=bit(ids[offer],next[offer]);}
  int selected=-1;for(unsigned c=0;c<2;c++)if((d.canonical_ready&(1u<<c))&&read[c]<N){selected=int(c);break;}
  const unsigned address=selected>=0?read[selected]:unsigned(age%N);
  if(selected>=0){d.read_en=1;d.host_context=unsigned(selected);d.host_addr=address;}else if(d.busy){d.read_en=1;d.host_context=(d.busy&1u)?0u:1u;d.host_addr=address;}
  d.clk=0;d.eval();const bool accepted=d.command_accept;d.clk=1;d.eval();d.clk=0;d.eval();if(accepted)next[offer]++;
  need(!d.error,"A_PRP_HEALTHY_ERROR age="+std::to_string(age));need((d.feed_level&7u)<=4&&((d.feed_level>>3)&7u)<=4,"A_PRP_FIFO_CAPACITY");
  for(unsigned c=0;c<2;c++){
   const uint64_t begin=FIRST[c];unsigned launched=age<begin?0u:std::min(counts[c],1u+unsigned((age-begin)/INTERVAL));unsigned completed=age<begin+CARRY_DONE+1?0u:std::min(counts[c],1u+unsigned((age-begin-CARRY_DONE-1)/INTERVAL));
   need(lane32(d.operations_started,c)==launched&&lane32(d.completed_squares,c)==completed,"A_PRP_COMPLETE_BIT_CALENDAR");
   const bool warm=age==begin+uint64_t(counts[c]-1)*INTERVAL+CARRY_DONE+1;need(bool(d.warm_done&(1u<<c))==warm,"A_PRP_WARM_EDGE");
   if(d.done&(1u<<c)){done_count[c]++;done_edges[c]=age;need(d.canonical_ready&(1u<<c),"A_PRP_ATOMIC_PUBLICATION");need(!(d.busy&(1u<<c)),"A_PRP_DONE_IDLE");
    const uint64_t canon=lane64(d.canonical_cycles,c);need(canon==(sentinel?10u:9u)*N&&lane64(d.image_copy_cycles,c)==N+4,"A_PRP_CANONICAL_COPY_LEDGER");}
  }
  need((published&unsigned(d.canonical_ready))==published,"A_PRP_PUBLICATION_STABLE");published=d.canonical_ready;
  if(selected>=0){const unsigned c=unsigned(selected),ci=ids[c];need(d.read_valid&&d.read_context==c&&uint64_t(d.read_owner)==owner(ci,c),"A_PRP_FULL56_OWNER");
   int32_t expected=sentinel?(address==0?-1:0):EXPECTED[ci][address];if(negative_comparator&&ci==0&&address==0)expected++;
   const uint32_t sign=expected<0?0xffffffffu:0u;need(d.read_data[0]==uint32_t(expected)&&d.read_data[1]==sign&&d.read_data[2]==sign,"A_PRP_RESIDUE_MISMATCH case="+std::to_string(ci)+" digit="+std::to_string(address));actual[c][address]=int32_t(d.read_data[0]);read[c]++;total_reads++;
  }else need(!d.read_valid,"A_PRP_UNPUBLISHED_READ");
  if(published==3&&read[0]==N&&read[1]==N){end=age;break;}
 }
 need(end>0&&!d.busy&&!d.feed_level&&next==counts&&done_count==std::array<unsigned,2>{1,1},"A_PRP_FINITE_RETIREMENT");
 for(unsigned c=0;c<2;c++){const unsigned ci=ids[c];unsigned doubles=0;for(unsigned k=0;k<counts[c];k++)doubles+=bit(ci,k);total_squares+=counts[c];total_doubles+=doubles;
  std::cout<<"A_CONTEXT_PRP_RESULT {\"case\":"<<ci<<",\"base\":"<<base(ci)<<",\"steps\":"<<counts[c]<<",\"doubles\":"<<doubles<<",\"done_edge\":"<<done_edges[c]<<",\"sentinel\":"<<(sentinel?"true":"false")<<",\"digits\":[";for(unsigned a=0;a<N;a++)std::cout<<(a?",":"")<<actual[c][a];std::cout<<"]}\n";}
}
int main(int argc,char** argv){try{VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d(&context);if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
 negative_comparator=argc==2&&std::string(argv[1])=="--negative-comparator";negative_schedule=argc==2&&std::string(argv[1])=="--negative-schedule";need((argc==1||negative_comparator||negative_schedule)&&gfn16_runtime::matches(context,d),"A_PRP_ARGUMENTS_THREADS");
 std::cout<<BUILD_LABEL<<"\n";for(unsigned first=0;first<8;first+=2)pair(d,first,false);pair(d,8,true);
 std::cout<<"A_CONTEXT_PRP_PASS cases=8 sentinel_cases=2 squares="<<total_squares<<" doubles="<<total_doubles<<" signed96_words="<<total_reads<<" interval="<<INTERVAL<<"\n";return 0;
 }catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}}
