#include "s4_host_contexts_config_v1.h"
#include "verilated.h"
#include "native_runtime_context_v1.h"
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
static void need(bool ok,const std::string& s){if(!ok)throw std::runtime_error(s);}
static bool oracle_negative=false;
static uint32_t lane32(uint64_t data,unsigned ctx){return uint32_t(data>>(ctx*32));}
static uint64_t lane64(const VlWide<4>& data,unsigned ctx){return uint64_t(data[2*ctx])|(uint64_t(data[2*ctx+1])<<32);}
static uint64_t owner(unsigned ctx){return (uint64_t(COUNTS[ctx]-1)<<24)|(uint64_t(uint16_t(EPOCHS[ctx]+COUNTS[ctx]-1))<<8)|1u;}
static void clear(DUT& d){d.host_context=d.load_we=d.read_en=0;d.host_addr=d.write_data=0;d.start_contexts=d.batch_mode=d.feed_mode=d.double_bit=0;d.base=d.warm_count=d.double_mask=0;d.command_context=d.command_valid=d.command_double=0;d.command_index=d.command_generation=0;for(unsigned i=0;i<2*P;i++)d.initial_c0[i]=d.initial_c1[i]=0;}
static void edge(DUT& d){d.clk=0;d.eval();d.clk=1;d.eval();}
static void read_word(DUT& d,unsigned ctx,unsigned address){
    need(d.read_valid&&d.read_context==ctx&&uint64_t(d.read_owner)==owner(ctx),"S4_HOST_CONTEXT_READ_FULL_OWNER ctx="+std::to_string(ctx)+" address="+std::to_string(address));
    int32_t expected=EXPECTED[ctx][address];if(oracle_negative&&ctx==0&&address==0)expected++;uint32_t high=expected<0?0xffffffffu:0;
    need(d.read_data[0]==uint32_t(expected)&&d.read_data[1]==high&&d.read_data[2]==high,"S4_HOST_CONTEXT_SIGNED96_VALUE ctx="+std::to_string(ctx)+" address="+std::to_string(address));
}
static unsigned launched(unsigned age,unsigned ctx){if(age<FIRST[ctx])return 0;return std::min(COUNTS[ctx],1u+(age-FIRST[ctx])/INTERVAL);}
static unsigned completed(unsigned age,unsigned ctx){if(age<FIRST[ctx]+CARRY_DONE+1)return 0;return std::min(COUNTS[ctx],1u+(age-FIRST[ctx]-CARRY_DONE-1)/INTERVAL);}
static void run(DUT& d){
    clear(d);d.clk=0;d.rst_n=0;d.eval();edge(d);need(!d.busy&&!d.done&&!d.canonical_ready&&!d.read_valid&&!d.error&&!d.operations_started&&!d.completed_squares,"S4_HOST_CONTEXT_RESET");d.clk=0;d.rst_n=1;d.eval();
    for(unsigned ctx=0;ctx<2;ctx++)for(unsigned address=0;address<N;address++){clear(d);d.host_context=ctx;d.host_addr=address;d.load_we=1;d.write_data=INITIAL[ctx][address];edge(d);need(!d.error&&!d.read_valid&&!d.canonical_ready,"S4_HOST_CONTEXT_COLD_LOAD");}
    clear(d);d.start_contexts=d.batch_mode=3;d.base=uint64_t(BASES[0])|(uint64_t(BASES[1])<<32);d.warm_count=uint64_t(COUNTS[0])|(uint64_t(COUNTS[1])<<32);
    for(unsigned ctx=0;ctx<2;ctx++)for(unsigned b=0;b<P;b++){d.initial_c0[ctx*P+b]=uint32_t(C0[ctx][b]);d.initial_c1[ctx*P+b]=uint32_t(C1[ctx][b]);}
    edge(d);need(d.busy==3&&!d.done&&!d.canonical_ready&&!d.error&&d.accepted_generation==0x0101,"S4_HOST_CONTEXT_JOINT_START");
    std::array<unsigned,2> next_read{},done_count{},done_edge{};unsigned reads=0,peer_reads=0,previous_ready=0,previous_raw_b=0;
    bool waiting_b=false,capture_during_copy=false,canonical_while_peer_arithmetic=false;
    unsigned age=1;
    for(;age<20000;age++){
        clear(d);int selected=-1;unsigned address=0;
        if(d.canonical_ready&1u && next_read[0]<N){selected=0;address=next_read[0];}
        else if(d.canonical_ready&2u && next_read[1]<N){selected=1;address=next_read[1];}
        if(selected>=0){d.read_en=1;d.host_context=unsigned(selected);d.host_addr=address;}
        else if(d.busy){d.read_en=1;d.host_context=(d.busy&2u)?1:0;d.host_addr=age%N;}
        bool peer_busy=selected==0&&(d.busy&2u);
        edge(d);need(!d.error,"S4_HOST_CONTEXT_MODEL_ERROR age="+std::to_string(age));
        need(unsigned(d.accepted_generation)==0x0101&&!d.command_accept&&!d.operation_accept&&!d.feed_level,"S4_HOST_CONTEXT_MASK_MODE_NO_DESCRIPTORS");
        for(unsigned ctx=0;ctx<2;ctx++){
            need(lane32(d.operations_started,ctx)==launched(age,ctx)&&lane32(d.completed_squares,ctx)==completed(age,ctx),"S4_HOST_CONTEXT_ACTUAL_FULL_CHAINS age="+std::to_string(age)+" ctx="+std::to_string(ctx));
            unsigned final_digit=FIRST[ctx]+(COUNTS[ctx]-1)*INTERVAL+FIRST_DIGIT;
            unsigned raw=age>final_digit?std::min(T,age-final_digit):0;
            need(lane32(d.final_image_rows,ctx)==raw,"S4_HOST_CONTEXT_ORDERED_FINAL_CAPTURE age="+std::to_string(age));
            bool warm=age==FIRST[ctx]+(COUNTS[ctx]-1)*INTERVAL+CARRY_DONE+1;
            need(bool(d.warm_done&(1u<<ctx))==warm,"S4_HOST_CONTEXT_WARM_CALENDAR");
            if(warm)need(!(d.canonical_ready&(1u<<ctx)),"S4_HOST_CONTEXT_WARM_NOT_PUBLICATION");
            if(d.done&(1u<<ctx)){done_count[ctx]++;done_edge[ctx]=age;need(d.canonical_ready&(1u<<ctx),"S4_HOST_CONTEXT_DONE_READY_ATOMIC");need(!(d.busy&(1u<<ctx)),"S4_HOST_CONTEXT_DONE_IDLE");
                need(lane64(d.canonical_cycles,ctx)==CANON_PASSES*N&&lane64(d.image_copy_cycles,ctx)==N+4,"S4_HOST_CONTEXT_CANONICAL_COPY_COST");}
        }
        need((previous_ready&unsigned(d.canonical_ready))==previous_ready,"S4_HOST_CONTEXT_NO_PUBLICATION_REGRESSION");previous_ready=d.canonical_ready;
        if(d.waiting_final&2u)waiting_b=true;
        unsigned raw_b=lane32(d.final_image_rows,1);if(raw_b>previous_raw_b&&lane64(d.image_copy_cycles,0)>0&&(d.busy&1u))capture_during_copy=true;previous_raw_b=raw_b;
        if(lane64(d.canonical_cycles,0)>0&&lane32(d.completed_squares,1)<COUNTS[1]&&(d.busy&2u))canonical_while_peer_arithmetic=true;
        if(std::string(KIND)=="sentinel"&&lane32(d.final_image_rows,0)==T&&lane32(d.completed_squares,0)==COUNTS[0]&&
           !(d.waiting_final&1u)&&(d.busy&1u)&&!lane64(d.image_copy_cycles,0)&&lane32(d.completed_squares,1)<COUNTS[1]&&(d.busy&2u))canonical_while_peer_arithmetic=true;
        if(selected>=0){read_word(d,unsigned(selected),address);next_read[selected]++;reads++;if(peer_busy)peer_reads++;}
        else need(!d.read_valid,"S4_HOST_CONTEXT_BUSY_READ_SUPPRESSED");
        if(d.canonical_ready==3&&next_read[0]==N&&next_read[1]==N)break;
    }
    need(age<20000&&done_count[0]==1&&done_count[1]==1&&done_edge[0]<done_edge[1]&&!d.busy&&waiting_b&&
         capture_during_copy==EXPECT_CAPTURE_COPY&&canonical_while_peer_arithmetic&&peer_reads==N,"S4_HOST_CONTEXT_FULL_PUBLICATION_INTERLEAVE");
    // Alternating contexts stresses actual synchronous response selectors/owners.
    for(unsigned address=0;address<N;address++)for(unsigned ctx=0;ctx<2;ctx++){clear(d);d.read_en=1;d.host_context=ctx;d.host_addr=address;edge(d);need(!d.error&&d.canonical_ready==3&&!d.done&&!d.busy,"S4_HOST_CONTEXT_PUBLISHED_STABLE");read_word(d,ctx,address);reads++;}
    clear(d);edge(d);need(!d.read_valid&&!d.done&&!d.error&&d.canonical_ready==3,"S4_HOST_CONTEXT_READ_DRAIN");need(reads==4*N,"S4_HOST_CONTEXT_READ_LEDGER");
    std::cout<<"S4_HOST_CONTEXTS_PASS kind="<<KIND<<" aw="<<AW<<" p="<<P<<" counts="<<COUNTS[0]<<"/"<<COUNTS[1]<<" chains=2 squares="<<COUNTS[0]+COUNTS[1]<<" reads="<<reads<<" peer_live_reads="<<peer_reads<<" waiting_b=1 capture_during_copy="<<capture_during_copy<<" canonical_peer_arithmetic=1 owner_bits=56 signed96=1 canonical_host=1\n";
}
int main(int argc,char** argv){try{VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d(&context);if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);oracle_negative=argc==2&&std::string(argv[1])=="--oracle-negative";need((argc==1||oracle_negative)&&gfn16_runtime::matches(context,d),"S4_HOST_CONTEXT_ARGUMENTS_THREADS");run(d);return 0;}catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}}
