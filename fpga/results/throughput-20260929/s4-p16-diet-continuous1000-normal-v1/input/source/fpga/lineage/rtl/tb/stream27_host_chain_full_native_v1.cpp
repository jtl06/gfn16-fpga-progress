// Two bounded full-N host invocations: legacy1 then dependent mixed feed8.
// Actual paired T5b and independent NTT/CRT/integer reference; not full-N PRP.
#include "s4_host_chain_full_config_v1.h"
#include "stream27_host_chain_full_reference_v1.h"
#include "verilated.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
static_assert(AW==16 && P==8 && N==65536,"isolated exact full-N P8 host gate");
static void need(bool ok,const std::string& label){if(!ok)throw std::runtime_error(label);}
using Image=std::vector<int32_t>;
static void clear(DUT& d){d.load_we=0;d.read_en=0;d.start=0;d.host_addr=0;d.write_data=0;d.double_bit=0;d.batch_mode=0;d.warm_count=1;d.double_mask=0;d.feed_mode=0;d.command_valid=0;d.command_double=0;d.command_index=0;d.command_generation=0;d.t5b_load_we=0;d.t5b_read_en=0;d.t5b_start=0;d.t5b_host_addr=0;d.t5b_write_data=0;d.t5b_double_bit=0;d.base=BASE;}
static void edge(DUT& d){d.clk=0;d.eval();d.clk=1;d.eval();d.clk=0;d.eval();}
template<class Wide>static int32_t word(const Wide& x){uint32_t sign=x[0]&0x80000000u?0xffffffffu:0;need(x[1]==sign&&x[2]==sign,"S4_FULL_HOST_SIGNED96_ALL_BITS");return int32_t(x[0]);}
struct Counts{uint64_t jobs=0,operations=0,descriptors=0,reads=0,rows=0,copied=0,canonical=0,copy_cycles=0,cycles=0,backpressure=0,exchange=0,peak=0,t5b_wait=0,partial_reads=0;};
static Image initial(){Image x(N);uint32_t state=0x9135ba27u;for(unsigned j=0;j<N;++j){state^=state<<13;state^=state>>17;state^=state<<5;x[j]=state%BASE;}x[17]=-1;x[N-1]=-1;return x;}
static void reset_load(DUT& d,const Image& x,Counts& c){
    clear(d);d.rst_n=0;edge(d);need(!d.busy&&!d.error&&!d.done&&!d.read_valid&&!d.warm_done&&!d.canonical_ready&&!d.t5b_read_valid&&!d.t5b_done&&!d.t5b_busy,"S4_FULL_HOST_ONE_EDGE_RESET");d.rst_n=1;edge(d);need(!d.error&&!d.profile_cache_valid,"S4_FULL_HOST_RESET_CACHE");
    for(unsigned a=0;a<N;++a){clear(d);d.load_we=1;d.read_en=1;d.host_addr=a;d.write_data=uint32_t(x[a]);d.t5b_load_we=1;d.t5b_read_en=1;d.t5b_host_addr=a;d.t5b_write_data=uint32_t(x[a]);edge(d);need(!d.read_valid&&!d.t5b_read_valid&&!d.busy&&!d.error&&!d.t5b_error&&!d.canonical_ready,"S4_FULL_HOST_LOAD_WINS_READ");}
    // Same-value partial signed write then exact E0 immediate signed96 read.
    clear(d);d.load_we=1;d.read_en=1;d.host_addr=17;d.write_data=uint32_t(-1);d.t5b_load_we=1;d.t5b_read_en=1;d.t5b_host_addr=17;d.t5b_write_data=uint32_t(-1);edge(d);need(!d.read_valid&&!d.t5b_read_valid&&!d.canonical_ready,"S4_FULL_HOST_PARTIAL_WRITE_PRIORITY");
    clear(d);d.read_en=1;d.host_addr=17;d.t5b_read_en=1;d.t5b_host_addr=17;edge(d);need(d.read_valid&&d.t5b_read_valid&&word(d.read_data)==-1&&word(d.t5b_read_data)==-1,"S4_FULL_HOST_PARTIAL_SIGNED_READ_E0");++c.partial_reads;clear(d);edge(d);need(!d.read_valid&&!d.t5b_read_valid,"S4_FULL_HOST_READ_DRAIN");
}
static uint64_t finish(unsigned count,bool hit,bool special){return (hit?3u:102u)+uint64_t(count-1)*INTERVAL+CARRY_DONE+2+(special?7u:6u)*N+N+4;}
static void candidate(DUT& d,const std::vector<unsigned>& bits,bool feed,bool hit,bool special,Counts& c){
    unsigned count=bits.size();clear(d);d.batch_mode=feed;d.feed_mode=feed;d.warm_count=feed?count:33;d.double_mask=0xffffffffu;d.double_bit=bits[0];
    d.start=1;d.load_we=1;d.read_en=1;d.host_addr=17;d.write_data=uint32_t(-2);edge(d);need(d.busy&&!d.error&&!d.done&&!d.read_valid&&!d.canonical_ready&&d.feed_level==0,"S4_FULL_HOST_START_PRIORITY");
    uint64_t first=hit?3:102,last=finish(count,hit,special),warm=first+uint64_t(count-1)*INTERVAL+CARRY_DONE+1;unsigned next=1,popped=0;uint8_t generation=d.accepted_generation;
    for(uint64_t age=1;age<=last;++age){clear(d);
        if(feed&&next<count){d.command_valid=1;d.command_index=next;d.command_generation=generation;d.command_double=bits[next];}
        if(age>=10&&age<=20){d.load_we=1;d.read_en=1;d.start=1;d.host_addr=N-1;d.write_data=uint32_t(-2);d.base=BASE+1;d.batch_mode=1;d.warm_count=0;d.double_bit=1;}
        d.clk=0;d.eval();bool push=d.command_accept,pop=d.operation_accept;unsigned level=d.feed_level;
        need(level<=4,"S4_FULL_HOST_FIFO_WIDTH");c.peak=std::max(c.peak,uint64_t(level));if(d.command_valid&&!d.command_ready)++c.backpressure;if(push&&pop&&level==4)++c.exchange;
        if(pop){++popped;need(feed && age==first+uint64_t(popped)*INTERVAL,"S4_FULL_HOST_POP_EDGE");}
        edge(d);if(push)++next;
        need(!d.error,"S4_FULL_HOST_ARITHMETIC_OR_CONTROL_ERROR age="+std::to_string(age)+" code="+std::to_string(d.feed_error_code));
        need(bool(d.done)==(age==last)&&bool(d.busy)==(age!=last)&&!d.read_valid,"S4_FULL_HOST_EXACT_DONE_BUSY");
        need(bool(d.warm_done)==(age==warm),"S4_FULL_HOST_WARM_IS_NOT_HOST_DONE");
        need(d.feed_level<=4&&d.commands_enqueued==(feed?next-1:0)&&d.commands_consumed==popped,"S4_FULL_HOST_FIFO_ACCOUNTING");
        need(d.operations_started<=count&&(d.operations_started==0||d.completed_squares<=count),"S4_FULL_HOST_COLD_QUALIFIED_COMPLETION");
        if(age<first+uint64_t(count-1)*INTERVAL+FIRST_DIGIT+1)need(d.final_image_rows==0,"S4_FULL_HOST_TRUE_LAST_ONLY");
    }
    need(d.operations_started==count&&d.completed_squares==count&&d.final_image_rows==N/P&&d.cycles==last&&d.canonical_ready&&d.feed_level==0,"S4_FULL_HOST_CANONICAL_N_COPY_COMMIT");
    need(!feed||(next==count&&popped==count-1),"S4_FULL_HOST_ALL_DESCRIPTORS");
    need(d.canonical_cycles==(special?7u:6u)*N&&d.image_copy_cycles==N+3,"S4_FULL_HOST_FINALIZATION_EDGE_COST");
    need(bool(d.profile_hits)==hit&&bool(d.profile_loads)==!hit&&d.profile_cache_valid&&!d.profile_words_loaded,"S4_FULL_HOST_EXACT_SETUP_CACHE");
    need(d.root_cycles==(hit?0u:99u)&&d.conversion_cycles==N/P&&!d.crt_cycles&&d.cycles==d.root_cycles+d.conversion_cycles+d.ntt_cycles+d.carry_cycles,"S4_FULL_HOST_DISJOINT_PHASE_LEDGER");
    ++c.jobs;c.operations+=count;c.descriptors+=popped;c.rows+=d.final_image_rows;c.canonical+=d.canonical_cycles;c.copy_cycles+=d.image_copy_cycles;c.cycles+=d.cycles;
    clear(d);edge(d);need(!d.done&&!d.busy&&!d.error,"S4_FULL_HOST_SUCCESS_SINGLE_PULSE");
}
static void production(DUT& d,const std::vector<unsigned>& bits,Counts& c){
    for(unsigned bit:bits){clear(d);d.t5b_start=1;d.t5b_double_bit=bit;d.t5b_load_we=1;d.t5b_read_en=1;d.t5b_host_addr=17;d.t5b_write_data=uint32_t(-2);edge(d);need(d.t5b_busy&&!d.t5b_done&&!d.t5b_error&&!d.t5b_read_valid,"S4_FULL_HOST_REAL_T5B_START");
        uint64_t elapsed=0;while(!d.t5b_done&&elapsed<T5B_WAIT_LIMIT){clear(d);if(elapsed>=10&&elapsed<=20){d.t5b_load_we=1;d.t5b_read_en=1;d.t5b_start=1;d.t5b_host_addr=N-1;d.t5b_write_data=uint32_t(-2);d.t5b_double_bit=!bit;}edge(d);need(!d.t5b_error&&!d.error,"S4_FULL_HOST_REAL_T5B_ERROR");++elapsed;}
        need(d.t5b_done&&!d.t5b_busy&&!d.t5b_error,"S4_FULL_HOST_REAL_T5B_BOUNDED_DONE");c.t5b_wait+=elapsed;clear(d);edge(d);
    }
}
static void compare(DUT& d,const Image& expected,unsigned job,bool negative,Counts& c){
    for(unsigned address=0;address<N;++address){clear(d);d.read_en=1;d.host_addr=address;d.t5b_read_en=1;d.t5b_host_addr=address;edge(d);need(d.read_valid&&d.t5b_read_valid&&d.canonical_ready&&!d.error&&!d.t5b_error,"S4_FULL_HOST_PAIRED_E0_II1_READ");
        int32_t actual=word(d.read_data),old=word(d.t5b_read_data);need(actual==expected[address]&&old==expected[address],"S4_FULL_HOST_NTT_CRT_CANONICAL_WORD job="+std::to_string(job)+" address="+std::to_string(address));need(actual==old,"S4_FULL_HOST_EXACT_T5B_ALL_WORDS");
        if(negative&&job==0&&address==0){int32_t wrong=expected[address]^1;need(actual==wrong,"S4_FULL_HOST_AW16_P8_NEGATIVE_ORACLE_REJECT");}++c.reads;++c.copied;
    }clear(d);edge(d);need(!d.read_valid&&!d.t5b_read_valid,"S4_FULL_HOST_II1_REGISTER_CLEAR");
}
int main(int argc,char** argv){try{
    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);DUT d{&context};
    if(argc==2&&std::string(argv[1])=="--runtime-probe"){std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";return context.threads()==1&&d.threads()==1?0:2;}
    bool negative=argc==2&&std::string(argv[1])=="--negative-oracle";need(argc==1||negative,"S4_FULL_HOST_ARGUMENTS");s4_full_reference::self_check();Counts c;Image reference=initial();reset_load(d,reference,c);
    const std::vector<unsigned> legacy={0},feed={0,1,0,1,1,0,1,0};
    for(unsigned job=0;job<2;++job){const auto& bits=job?feed:legacy;for(unsigned bit:bits)reference=s4_full_reference::square(reference,BASE,bit);bool special=reference[0]==-1;need(!special,"S4_FULL_HOST_DENSE_ORDINARY_CASE");candidate(d,bits,bool(job),bool(job),special,c);production(d,bits,c);compare(d,reference,job,negative,c);}
    need(c.jobs==2&&c.operations==9&&c.descriptors==7&&c.rows==2*N/P&&c.reads==2*N&&c.copied==2*N&&c.partial_reads==1&&c.canonical==12*N&&c.copy_cycles==2*(N+3)&&c.cycles==EXPECTED_CYCLES&&c.peak==4&&c.exchange==3&&c.backpressure==3*INTERVAL-4,"S4_FULL_HOST_EXACT_COUNTS");
    need(!negative,"S4_FULL_HOST_NEGATIVE_MISSED");need(context.threads()==1&&d.threads()==1,"S4_FULL_HOST_THREAD_IDENTITY");
    std::cout<<"S4_FULL_HOST_PASS aw=16 p=8 jobs="<<c.jobs<<" operations="<<c.operations<<" feed_descriptors="<<c.descriptors<<" true_final_rows="<<c.rows<<" paired_reads="<<c.reads<<" copied_words="<<c.copied<<" partial_reads="<<c.partial_reads<<" canonical_cycles="<<c.canonical<<" image_copy_cycles="<<c.copy_cycles<<" candidate_cycles="<<c.cycles<<" fifo_peak="<<c.peak<<" full_exchanges="<<c.exchange<<" backpressure_edges="<<c.backpressure<<" t5b_wait_edges="<<c.t5b_wait<<"\n";d.final();return 0;
}catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}}
