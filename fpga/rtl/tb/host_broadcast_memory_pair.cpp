// LOCAL PREPARATION ONLY. No transforms or correctness claims until executed.
#include "Vhost_broadcast_memory_pair.h"
#include "verilated.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#ifndef HOST_BROADCAST_AW
#define HOST_BROADCAST_AW 8
#endif
#ifndef HOST_BROADCAST_P
#define HOST_BROADCAST_P 104857601u
#endif
#ifndef HOST_BROADCAST_Q
#define HOST_BROADCAST_Q 4190109697u
#endif
constexpr unsigned AW=HOST_BROADCAST_AW,N=1u<<AW;
constexpr uint32_t P=HOST_BROADCAST_P;
static_assert(AW>=1 && AW<=16,"supported address width");
using DUT=Vhost_broadcast_memory_pair;
using Beat=std::array<uint32_t,16>;
void require(bool value,const std::string& message){if(!value)throw std::runtime_error(message);}
uint32_t rng(uint32_t& state){state^=state<<13;state^=state>>17;state^=state<<5;return state;}

struct Bench {
    DUT d;
    std::vector<uint32_t> memory=std::vector<uint32_t>(N);
    std::vector<bool> initialized=std::vector<bool>(N,false);
    uint64_t edges=0,reads=0,writes=0,clipped=0,masked_poison=0;
    uint64_t vector_reads=0,vector_writes=0,descriptor_errors=0,profile_checks=0,busy_checks=0;
    unsigned quarter_seen=0,half_seen=0;
    void clear(){d.load_we=0;d.read_en=0;d.vector_load_we=0;d.vector_read_en=0;d.start=0;
        d.profile_begin=0;d.profile_we=0;d.profile_commit=0;}
    void put(const Beat& words){for(unsigned i=0;i<16;++i)d.vector_write_data[i]=words[i];}
    void pair_flags(unsigned value,const char* name){require((value&1)==((value>>1)&1),std::string("pair flag ")+name);}
    void compare(){
        for(auto item:std::array<std::pair<unsigned,const char*>,10>{{
            {d.read_valid,"read_valid"},{d.vector_read_valid,"vector_read_valid"},{d.host_error,"host_error"},
            {d.profile_loaded,"profile_loaded"},{d.profile_loading,"profile_loading"},{d.profile_error,"profile_error"},
            {d.busy,"busy"},{d.done,"done"},{d.error,"error"},{unsigned(d.instance_enable),"instance_enable"}}})pair_flags(item.first,item.second);
        require((d.vector_read_mask&0xffffu)==(d.vector_read_mask>>16),"pair read mask");
        require((d.profile_loaded_size&31)==((d.profile_loaded_size>>5)&31),"pair profile size");
        require((d.profile_next_addr&0xffffu)==(d.profile_next_addr>>16),"pair profile next address");
        auto counter=[&](const auto& words){require(words[0]==words[2] && words[1]==words[3],"pair counter");};
        counter(d.seed_setup_cycles);counter(d.cycles);counter(d.butterflies);counter(d.data_reads);
        counter(d.data_writes);counter(d.root_reads);counter(d.wait_cycles);
        // Raw RAM outputs and unmasked lanes are intentionally NOT compared.
        // Neither reset nor an invalid read initializes their contents.
    }
    void edge(bool paired=true){d.clk=0;d.eval();d.clk=1;d.eval();++edges;if(paired)compare();}
    void reset(){
        clear();d.rst_n=0;edge();
        require(!d.read_valid&&!d.vector_read_valid&&!d.vector_read_mask&&!d.host_error&&!d.busy&&!d.done&&!d.error&&
                !d.profile_loaded&&!d.profile_loading&&!d.profile_error,"reset eligibility flags");
        // Conservatively invalidate the oracle after any reset; do not infer
        // RAM clearing, retention after aborted writes, or initialized zeros.
        std::fill(initialized.begin(),initialized.end(),false);
        d.rst_n=1;edge();
    }
    void ordinary(){
        require(d.rst_n && d.instance_enable==3 && !d.busy && !d.start && !d.profile_begin&&!d.profile_we&&!d.profile_commit,
                "ordinary transaction preconditions");
        const unsigned size=d.size_log2,extent=size>=1&&size<=AW ? 1u<<size:0;
        const unsigned address=d.vector_addr,scalar=d.host_addr;
        const bool request=d.vector_load_we||d.vector_read_en;
        const bool okay=extent && !(address&15) && address<extent;
        const bool vr=request&&okay&&d.vector_read_en&&!d.vector_load_we;
        const bool sr=!request&&d.read_en&&!d.load_we;
        uint16_t mask=0;
        for(unsigned i=0;i<16;++i)if((d.vector_lane_mask>>i&1) && address+i<extent)mask|=uint16_t(1u<<i);
        if(request&&okay&&d.vector_load_we){
            ++vector_writes;quarter_seen|=1u<<((address>>4)&3);half_seen|=1u<<((address>>6)&1);
            for(unsigned i=0;i<16;++i){
                if(mask>>i&1){require(d.vector_write_data[i]<P,"normal enabled payload noncanonical");
                    memory[address+i]=d.vector_write_data[i];initialized[address+i]=true;++writes;
                }else if(d.vector_write_data[i]>=P)++masked_poison;
                if((d.vector_lane_mask>>i&1) && address+i>=extent)++clipped;
            }
        }else if(!request&&d.load_we){
            require(d.write_data<P,"normal scalar payload noncanonical");memory[scalar]=d.write_data;initialized[scalar]=true;++writes;
        }
        // All intended valid reads must be initialized: skipping arbitrary
        // values could hide a test-coverage gap. Invalid/masked lanes are ignored.
        if(sr)require(initialized[scalar],"uninitialized scalar oracle read");
        if(vr)for(unsigned i=0;i<16;++i)if(mask>>i&1)require(initialized[address+i],"uninitialized vector oracle read");
        edge();
        require(d.host_error==(request&&!okay?3:0),"independent host error");
        require(d.read_valid==(sr?3:0)&&d.vector_read_valid==(vr?3:0),"independent read eligibility");
        require(d.vector_read_mask==(vr?uint32_t(mask)|(uint32_t(mask)<<16):0),"independent returned mask");
        require(!d.busy&&!d.done&&!d.error,"ordinary host changed arithmetic state");
        if(request&&!okay)++descriptor_errors;
        if(sr){require(uint32_t(d.read_data)==memory[scalar]&&uint32_t(d.read_data>>32)==memory[scalar],"independent scalar data");++reads;}
        if(vr){++vector_reads;for(unsigned i=0;i<16;++i)if(mask>>i&1){
            require(d.vector_read_data[i]==memory[address+i]&&d.vector_read_data[16+i]==memory[address+i],
                    "independent vector data index="+std::to_string(address+i));++reads;}}
    }
    void initialize(){clear();d.size_log2=AW;d.load_we=1;d.read_en=1;
        for(unsigned i=0;i<N;++i){d.host_addr=i;d.write_data=(uint64_t(i)*2654435761u+0x56789u)%P;ordinary();}clear();}
    void scan(){clear();d.read_en=1;d.size_log2=AW;
        for(unsigned i=0;i<N;++i){d.host_addr=i;ordinary();}clear();ordinary();}
    void normal(){
        d.instance_enable=3;d.rst_n=1;d.size_log2=AW;d.root_phase=0;d.op=1;d.inverse=0;d.dif=0;d.scale=0;
        d.host_addr=0;d.write_data=0;d.vector_addr=0;d.vector_lane_mask=0;put(Beat{});
        d.profile_modulus=P;d.profile_size_log2=AW;d.profile_format=2;d.profile_addr=0;d.profile_data=0;
        reset();initialize();
        // Every addressable host quarter/row, preserving neighboring quarters.
        const std::array<uint16_t,7> masks{{0,1,0x8000,0x8001,0x5555,0xaaaa,0xffff}};
        for(unsigned address=0;address<N;address+=16)for(unsigned mask:masks){
            clear();d.vector_load_we=1;d.vector_read_en=1;d.vector_addr=address;d.vector_lane_mask=mask;
            d.load_we=1;d.read_en=1;d.host_addr=(address+1)%N;d.write_data=P; // scalar must be suppressed
            Beat beat;for(unsigned i=0;i<16;++i)beat[i]=(mask>>i&1)&&address+i<N ? (address*31+i*127+mask)%P:0xffffffffu;
            put(beat);ordinary();
            clear();d.vector_read_en=1;d.vector_addr=address;d.vector_lane_mask=0xffff;ordinary();
            // Read adjacent word outside this host beat where available.
            if(N>16){clear();d.read_en=1;d.host_addr=(address+16)%N;ordinary();}
        }
        // Runtime short-N clipping; storage beyond N remains intact and is
        // checked by the later physical-address scan.
        for(unsigned lg=1;lg<=AW;++lg){
            const unsigned n=1u<<lg;d.size_log2=lg;
            for(unsigned address:std::array<unsigned,2>{{0,((n-1)/16)*16}}){
                clear();d.vector_addr=address;d.vector_load_we=1;d.vector_lane_mask=0xffff;
                Beat beat;for(unsigned i=0;i<16;++i)beat[i]=address+i<n ? (n+i+1)%P:0xffffffffu;
                put(beat);ordinary();clear();d.vector_read_en=1;ordinary();
            }
        }
        // Descriptor errors suppress simultaneous scalar access, including
        // poisoned scalar data and vector data. AW truncation is modeled by
        // assigning only representable addresses.
        for(unsigned size:std::array<unsigned,4>{{0,AW+1,31,1}}){
            clear();d.size_log2=size;d.vector_load_we=1;d.vector_read_en=1;d.vector_addr=1;
            d.vector_lane_mask=0xffff;Beat poison;poison.fill(0xffffffffu);put(poison);
            d.load_we=1;d.read_en=1;d.host_addr=0;d.write_data=P;ordinary();
        }
        if(AW>=5){clear();d.size_log2=4;d.vector_addr=16;d.vector_read_en=1;ordinary();}
        // Deterministic host-only transaction fuzz, independent flat memory.
        uint32_t random=0x91bb27u+AW;
        for(unsigned round=0;round<1200;++round){
            clear();unsigned sizes[5]={0,1,AW,AW+1,std::min(4u,AW)};d.size_log2=sizes[rng(random)%5];
            d.host_addr=rng(random)%N;d.vector_addr=rng(random)%N;if(round&1)d.vector_addr=unsigned(d.vector_addr)&~15u;
            d.load_we=rng(random)&1;d.read_en=rng(random)&1;d.vector_load_we=rng(random)&1;d.vector_read_en=rng(random)&1;
            d.write_data=rng(random)%P;d.vector_lane_mask=uint16_t(rng(random));
            Beat beat;for(auto& x:beat)x=rng(random)%P;put(beat);ordinary();
        }
        scan();
        // Malformed profile requests still suppress all ordinary host access.
        for(unsigned kind=0;kind<3;++kind){
            clear();d.profile_begin=kind==0;d.profile_we=kind==1;d.profile_commit=kind==2;
            d.profile_modulus=P+1;d.profile_size_log2=0;d.profile_format=2;d.profile_addr=0;d.profile_data=P;
            d.load_we=1;d.read_en=1;d.host_addr=0;d.write_data=P;
            d.vector_load_we=1;d.vector_read_en=1;d.vector_addr=1;d.vector_lane_mask=0xffff;edge();++profile_checks;
            require(d.profile_error==3&&!d.host_error&&!d.read_valid&&!d.vector_read_valid&&!d.vector_read_mask,"malformed profile priority");
            clear();ordinary();scan();
        }
        // Valid begin/write and failed partial commit, with host suppression.
        clear();d.size_log2=AW;d.profile_begin=1;d.profile_modulus=P;d.profile_size_log2=AW;d.profile_format=2;
        d.vector_load_we=1;d.vector_addr=0;d.vector_lane_mask=0;edge();++profile_checks;
        require(d.profile_loading==3&&!d.profile_loaded&&!d.profile_error&&!d.host_error,"valid profile begin");
        clear();d.profile_we=1;d.profile_addr=0;d.profile_data=P-1;d.load_we=1;d.host_addr=0;d.write_data=P;edge();++profile_checks;
        require(!d.profile_error&&d.profile_next_addr==0x00010001u,"profile word priority");
        clear();d.profile_commit=1;edge();++profile_checks;require(d.profile_error==3&&!d.profile_loaded,"partial commit");
        clear();ordinary();scan();
        // Start priority without executing a transform: start op=1 pointwise
        // square, inspect two live busy edges, reset before any result commits.
        clear();d.start=1;d.op=1;d.size_log2=AW;d.inverse=0;
        d.profile_begin=1;d.profile_we=1;d.profile_commit=1;d.profile_size_log2=0;
        d.vector_load_we=1;d.vector_read_en=1;d.vector_addr=1;d.vector_lane_mask=0xffff;
        d.load_we=1;d.read_en=1;d.write_data=P;edge();
        require(d.busy==3&&!d.done&&!d.error&&!d.profile_error&&!d.host_error&&!d.read_valid&&!d.vector_read_valid,"start priority");
        for(unsigned i=0;i<2;++i){
            d.start=i&1;d.profile_begin=i==0;d.profile_we=i==1;d.profile_commit=0;d.size_log2=0;
            edge();++busy_checks;require(d.busy==3&&d.profile_error==3&&!d.host_error&&!d.read_valid&&!d.vector_read_valid&&!d.vector_read_mask,"busy priority");
        }
        reset();for(unsigned i=0;i<12;++i){edge();require(!d.busy&&!d.done&&!d.error&&!d.read_valid&&!d.vector_read_valid,"late reset token");}
        initialize();scan();
        require(reads>0&&vector_reads>0&&vector_writes>0&&masked_poison>0&&descriptor_errors>0&&profile_checks==6&&busy_checks==2,"coverage counters");
        require(quarter_seen==(N<64 ? (1u<<std::min(4u,(N+15)/16))-1:15u),"all addressable quarters");
        require(half_seen==(N<=64?1u:3u),"both addressable bank halves");
        if(AW>=2)require(clipped>0,"small runtime clipping coverage");
        std::cout<<"PASS host_broadcast_memory_pair aw="<<AW<<" p="<<P<<" edges="<<edges<<" read_words="<<reads
            <<" written_words="<<writes<<" vector_reads="<<vector_reads<<" vector_writes="<<vector_writes
            <<" masked_poison="<<masked_poison<<" clipped="<<clipped<<" descriptor_errors="<<descriptor_errors
            <<" profile_checks="<<profile_checks<<" busy_checks="<<busy_checks<<" quarters="<<quarter_seen<<" halves="<<half_seen<<"\n";
    }
    int illegal(const std::string& instance,const std::string& kind,const std::string& payload,unsigned quarter){
        require(instance=="baseline"||instance=="candidate","assertion instance");
        require(kind=="scalar"||kind=="vector","assertion access");
        require(payload=="p"||payload=="highbit"||payload=="u32max","assertion payload");
        require(quarter<4&&quarter*16<N,"assertion quarter representable");
        d.instance_enable=instance=="baseline"?1:2;clear();d.rst_n=0;edge(false);d.rst_n=1;edge(false);
        d.size_log2=AW;d.host_addr=quarter*16;d.vector_addr=quarter*16;d.vector_lane_mask=1;
        uint32_t poison=payload=="p"?P:payload=="highbit"?0x80000000u:0xffffffffu;
        d.write_data=poison;Beat beat{};beat[0]=poison;put(beat);
        d.load_we=kind=="scalar";d.vector_load_we=kind=="vector";
        std::cout<<"EXPECT_CANONICAL_ASSERT instance="<<instance<<" kind="<<kind<<" payload="<<payload<<" quarter="<<quarter<<"\n"<<std::flush;
        edge(false);std::cerr<<"MISSING_CANONICAL_ASSERTION\n";return 3;
    }
};

int main(int argc,char** argv){
    try{
        Verilated::commandArgs(argc,argv);Verilated::threadContextp()->threads(1);Bench bench;
        bench.d.eval();
        require(bench.d.configured_aw==AW&&bench.d.configured_p==P&&bench.d.configured_q==HOST_BROADCAST_Q,"compiled parameter mismatch");
        require(Verilated::threadContextp()->threads()==1&&bench.d.threads()==1,"single-thread model/context required");
        if(argc==2&&std::string(argv[1])=="--runtime-probe"){
            std::cout<<"{\"context_threads\":1,\"model_threads\":1,\"aw\":"<<AW<<",\"p\":"<<P<<",\"q\":"<<HOST_BROADCAST_Q<<"}\n";return 0;
        }
        if(argc==6&&std::string(argv[1])=="--illegal")return bench.illegal(argv[2],argv[3],argv[4],std::stoul(argv[5]));
        require(argc==1,"normal: no args; focused fault: --illegal baseline|candidate scalar|vector p|highbit|u32max quarter");
        bench.normal();bench.d.final();return 0;
    }catch(const std::exception& e){std::cerr<<"FAIL host_broadcast_memory_pair: "<<e.what()<<"\n";return 2;}
}
