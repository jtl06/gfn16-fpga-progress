// One source-selected dependent P8/P16 FIFO job: no per-square stop/read/reload.
// Full-size arithmetic runs only natively on an admitted Linux worker.
#include "stream27_s4_continuous_config_v1.h"
#include "stream27_host_chain_full_reference_v1.h"
#include "native_runtime_context_v1.h"
#include "verilated.h"
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
static_assert(AW==16 && (P==8 || P==16) && N==65536 && BASE==604832956,"exact source-selected record sample");
static_assert(CANONICAL_PIPE_STAGES<=1,"explicit final canonical source selection");
using Image=std::vector<int32_t>;
static void need(bool value,const std::string& why){if(!value)throw std::runtime_error(why);}
static void clear(DUT& d){d.load_we=0;d.read_en=0;d.start=0;d.host_addr=0;d.write_data=0;d.double_bit=0;d.batch_mode=0;d.warm_count=1;d.double_mask=0;d.feed_mode=0;d.command_valid=0;d.command_double=0;d.command_index=0;d.command_generation=0;d.t5b_load_we=0;d.t5b_read_en=0;d.t5b_start=0;d.t5b_host_addr=0;d.t5b_write_data=0;d.t5b_double_bit=0;d.base=BASE;}
static void edge(DUT& d){d.clk=0;d.eval();d.clk=1;d.eval();d.clk=0;d.eval();}
template<class Wide>static int32_t word(const Wide& x){uint32_t sign=x[0]&0x80000000u?0xffffffffu:0;need(x[1]==sign&&x[2]==sign,"S4_CONTINUOUS_SIGNED96_ALL_BITS");return int32_t(x[0]);}
template<class Action>static uint64_t ms(Action action){auto begin=std::chrono::steady_clock::now();action();return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-begin).count();}
static unsigned bit(unsigned index){constexpr unsigned pattern[8]={0,1,0,1,1,0,1,0};return pattern[index%8];}
static Image initial(){Image x(N);uint32_t state=0x9135ba27u;for(unsigned j=0;j<N;++j){state^=state<<13;state^=state>>17;state^=state<<5;x[j]=state%BASE;}x[17]=-1;x[N-1]=-1;return x;}
static void reset_load(DUT& d,const Image& input){clear(d);d.rst_n=0;edge(d);need(!d.busy&&!d.error&&!d.done&&!d.read_valid&&!d.warm_done&&!d.canonical_ready,"S4_CONTINUOUS_ONE_RESET");d.rst_n=1;edge(d);need(!d.error&&!d.profile_cache_valid,"S4_CONTINUOUS_COLD_CACHE");
    for(unsigned a=0;a<N;++a){clear(d);d.load_we=1;d.host_addr=a;d.write_data=uint32_t(input[a]);edge(d);need(!d.read_valid&&!d.busy&&!d.error&&!d.canonical_ready,"S4_CONTINUOUS_EXACT_INITIAL_LOAD");}
    clear(d);edge(d);
}
struct Counts{uint64_t descriptors=0,peak=0,exchange=0,backpressure=0,cycles=0,canonical=0,copy=0,rows=0;};
static void candidate(DUT& d,unsigned operations,bool special,bool quiet,Counts& c){clear(d);d.batch_mode=1;d.feed_mode=1;d.warm_count=operations;d.double_bit=bit(0);d.start=1;edge(d);need(d.busy&&!d.error&&!d.done&&!d.read_valid&&!d.canonical_ready&&d.feed_level==0,"S4_CONTINUOUS_ONE_START");
    const uint64_t first=102,warm=first+uint64_t(operations-1)*INTERVAL+CARRY_DONE+1;
    const uint64_t canonical_passes=6u+3u*CANONICAL_PIPE_STAGES+unsigned(special);
    const uint64_t last=warm+1+canonical_passes*N+N+4;
    unsigned next=1,popped=0;uint16_t generation=d.accepted_generation;
    for(uint64_t age=1;age<=last;++age){clear(d);
        if(next<operations){d.command_valid=1;d.command_index=next;d.command_generation=generation;d.command_double=bit(next);}
        d.clk=0;d.eval();bool push=d.command_accept,pop=d.operation_accept;unsigned level=d.feed_level;
        need(level<=4,"S4_CONTINUOUS_FIFO_WIDTH");c.peak=std::max(c.peak,uint64_t(level));if(d.command_valid&&!d.command_ready)++c.backpressure;if(push&&pop&&level==4)++c.exchange;
        if(pop){++popped;need(age==first+uint64_t(popped)*INTERVAL,"S4_CONTINUOUS_POP_EDGE");if(!quiet)std::cout<<"S4_CONTINUOUS_POP {\"index\":"<<popped<<",\"age\":"<<age<<",\"bit\":"<<bit(popped)<<"}\n";}
        edge(d);if(push)++next;
        need(!d.error,"S4_CONTINUOUS_NATIVE_ERROR age="+std::to_string(age)+" code="+std::to_string(d.feed_error_code));
        need(bool(d.done)==(age==last)&&bool(d.busy)==(age!=last)&&!d.read_valid,"S4_CONTINUOUS_EXACT_DONE_BUSY_NO_BARRIER");
        need(bool(d.warm_done)==(age==warm),"S4_CONTINUOUS_ONE_FINAL_WARM_DONE");
        need(d.feed_level<=4&&d.commands_enqueued==next-1&&d.commands_consumed==popped,"S4_CONTINUOUS_FIFO_ACCOUNTING");
        need(d.operations_started<=operations&&d.completed_squares<=operations,"S4_CONTINUOUS_OPERATION_BOUND");
        if(age<first+uint64_t(operations-1)*INTERVAL+FIRST_DIGIT+1)need(d.final_image_rows==0,"S4_CONTINUOUS_TRUE_LAST_ONLY");
    }
    need(next==operations&&popped==operations-1&&d.operations_started==operations&&d.completed_squares==operations,"S4_CONTINUOUS_ALL_OPERATIONS");
    need(d.final_image_rows==N/P&&d.cycles==last&&d.canonical_ready&&d.feed_level==0,"S4_CONTINUOUS_FINAL_COPY_COMMIT");
    need(d.canonical_cycles==canonical_passes*N&&d.image_copy_cycles==N+3,"S4_CONTINUOUS_EXACT_FINAL_COST");
    need(d.profile_hits==0&&d.profile_loads==1&&d.profile_cache_valid&&!d.profile_words_loaded&&d.root_cycles==99&&d.conversion_cycles==N/P&&!d.crt_cycles,"S4_CONTINUOUS_ONE_COLD_SETUP");
    need(d.cycles==d.root_cycles+d.conversion_cycles+d.ntt_cycles+d.carry_cycles,"S4_CONTINUOUS_DISJOINT_PHASES");
    c.descriptors=popped;c.cycles=d.cycles;c.canonical=d.canonical_cycles;c.copy=d.image_copy_cycles;c.rows=d.final_image_rows;
    clear(d);edge(d);need(!d.done&&!d.busy&&!d.error,"S4_CONTINUOUS_DONE_PULSE");
}
static Image read(DUT& d,const Image& expected,bool negative){Image actual(N);
    for(unsigned a=0;a<N;++a){clear(d);d.read_en=1;d.host_addr=a;edge(d);need(d.read_valid&&d.canonical_ready&&!d.error,"S4_CONTINUOUS_FINAL_E0_II1_READ");actual[a]=word(d.read_data);
        need(actual[a]==expected[a],"S4_CONTINUOUS_INDEPENDENT_REFERENCE_WORD address="+std::to_string(a));
        if(negative&&a==0)need(actual[a]==(expected[a]^1),"S4_CONTINUOUS_NEGATIVE_ORACLE_REJECT");
    }clear(d);edge(d);need(!d.read_valid,"S4_CONTINUOUS_READ_DRAIN");return actual;
}
static void image(const Image& actual,const Image& expected){std::cout<<"S4_CONTINUOUS_IMAGE {\"actual\":[";for(unsigned i=0;i<N;++i){if(i)std::cout<<',';std::cout<<actual[i];}std::cout<<"],\"expected\":[";for(unsigned i=0;i<N;++i){if(i)std::cout<<',';std::cout<<expected[i];}std::cout<<"]}\n";}
int main(int argc,char** argv){try{
    VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d{&context};
    if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
    need(argc==2||argc==3,"S4_CONTINUOUS_ARGUMENTS");std::string arg=argv[1];need(arg=="1"||arg=="100"||arg=="1000","S4_CONTINUOUS_FINITE_COUNT");unsigned count=std::stoul(arg);
    bool negative=argc==3&&std::string(argv[2])=="--negative-oracle";need(argc!=3||negative,"S4_CONTINUOUS_TYPED_MODE");need(!negative||count==1,"S4_CONTINUOUS_SMALL_SEPARATE_FAULT");
    s4_full_reference::self_check();Image expected=initial();reset_load(d,expected);unsigned doubles=0;
    uint64_t reference_ms=ms([&](){for(unsigned i=0;i<count;++i){doubles+=bit(i);expected=s4_full_reference::square(expected,BASE,bit(i));}});
    bool special=expected[0]==-1;Counts c;uint64_t candidate_ms=ms([&](){candidate(d,count,special,negative,c);});Image actual;
    uint64_t read_ms=ms([&](){actual=read(d,expected,negative);});need(!negative,"S4_CONTINUOUS_NEGATIVE_MISSED");image(actual,expected);
    need(gfn16_runtime::matches(context,d),"S4_CONTINUOUS_RUNTIME_MATCH");
    std::cout<<"S4_CONTINUOUS_PASS {\"case_id\":\""<<CASE_ID<<"\",\"operations\":"<<count<<",\"doubles\":"<<doubles<<",\"resets\":1,\"loads\":1,\"loaded_digits\":"<<N<<",\"starts\":1,\"readbacks\":1,\"words\":"<<N<<",\"signed96_words\":"<<N<<",\"feed_descriptors\":"<<c.descriptors<<",\"fifo_peak\":"<<c.peak<<",\"full_exchanges\":"<<c.exchange<<",\"backpressure_edges\":"<<c.backpressure<<",\"final_rows\":"<<c.rows<<",\"canonical_cycles\":"<<c.canonical<<",\"copy_cycles\":"<<c.copy<<",\"candidate_cycles\":"<<c.cycles<<",\"profile_loads\":1,\"profile_hits\":0,\"root_cycles\":99,\"conversion_cycles\":"<<N/P<<",\"special\":"<<unsigned(special)<<",\"reference_ms\":"<<reference_ms<<",\"candidate_ms\":"<<candidate_ms<<",\"read_ms\":"<<read_ms<<"}\n";d.final();return 0;
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
