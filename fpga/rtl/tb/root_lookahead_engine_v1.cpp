#include "Vroot_lookahead_engine_pair_v1.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
static void require(bool value,const char* message){if(!value)throw std::runtime_error(message);}
int main(int argc,char**argv){try {
    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
    Vroot_lookahead_engine_pair_v1 d{&context};d.eval();
    if(argc==2&&std::string(argv[1])=="--runtime-probe") {
        std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
        return context.threads()==1&&d.threads()==1?0:2;
    }
    require(argc==2,"ROOT_LOOKAHEAD_AW5_ARGS");std::ifstream in(argv[1]);
    std::string magic;unsigned profile_words,cases;in>>magic>>profile_words>>cases;
    require(magic=="ROOTLOOKAW5"&&profile_words==3084&&cases==3,"ROOT_LOOKAHEAD_AW5_HEADER");
    std::vector<uint32_t> profile(profile_words);for(auto&x:profile)require(bool(in>>x),"ROOT_LOOKAHEAD_AW5_PROFILE_INPUT");
    auto compare=[&](){require(!d.pair_mismatch,"ROOT_LOOKAHEAD_AW5_PAIR_MISMATCH");};
    auto tick=[&](){d.clk=0;d.eval();compare();d.clk=1;d.eval();compare();};
    auto idle=[&](){d.load_we=0;d.read_en=0;d.vector_load_we=0;d.vector_read_en=0;
        d.profile_begin=0;d.profile_we=0;d.profile_commit=0;d.start=0;};
    auto reset=[&](){idle();d.rst_n=0;tick();d.rst_n=1;tick();
        require(!d.busy&&!d.done&&!d.error&&!d.profile_loaded,"ROOT_LOOKAHEAD_AW5_RESET");};
    unsigned operations=0,readbacks=0;
    for(unsigned c=0;c<cases;c++) {
        reset();d.size_log2=5;d.profile_begin=1;d.profile_size_log2=5;
        d.profile_modulus=104857601;d.profile_format=2;tick();idle();
        require(d.profile_loading&&!d.profile_error,"ROOT_LOOKAHEAD_AW5_PROFILE_BEGIN");
        for(unsigned i=0;i<profile_words;i++) {d.profile_we=1;d.profile_addr=i;d.profile_data=profile[i];tick();
            require(!d.profile_error&&d.profile_next_addr==i+1,"ROOT_LOOKAHEAD_AW5_PROFILE_WRITE");}
        idle();d.profile_commit=1;tick();idle();require(d.profile_loaded&&!d.profile_error,"ROOT_LOOKAHEAD_AW5_PROFILE_COMMIT");
        std::array<uint32_t,32> input{};for(auto&x:input)require(bool(in>>x),"ROOT_LOOKAHEAD_AW5_SHORT_INPUT");
        for(unsigned a=0;a<32;a++){d.load_we=1;d.host_addr=a;d.write_data=input[a];tick();}idle();
        for(unsigned step=0;step<5;step++) {
            d.root_phase=step==0?0:step==1?1:step==3?2:3;
            d.op=step==0||step==4?2:step==2?1:0;d.dif=step==1;d.inverse=0;d.scale=0;
            d.start=1;tick();idle();unsigned cycles=0;
            while(!d.done) {tick();require(++cycles<10000,"ROOT_LOOKAHEAD_AW5_TIMEOUT");}
            require(!d.error&&!d.busy,"ROOT_LOOKAHEAD_AW5_RUN");operations++;
            for(unsigned a=0;a<32;a++) {
                uint32_t expected;require(bool(in>>expected),"ROOT_LOOKAHEAD_AW5_SHORT_EXPECTED");
                d.read_en=1;d.host_addr=a;tick();require(d.read_valid&&d.read_data==expected,"ROOT_LOOKAHEAD_AW5_INTEGER_ORACLE");readbacks++;
            }
            idle();tick();
        }
    }
    std::string extra;require(!(in>>extra)&&in.eof(),"ROOT_LOOKAHEAD_AW5_TRAILING_INPUT");
    require(operations==15&&readbacks==480,"ROOT_LOOKAHEAD_AW5_COVERAGE");
    std::cout<<"ROOT_LOOKAHEAD_AW5_PASS cases=3 operations=15 readbacks=480\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
