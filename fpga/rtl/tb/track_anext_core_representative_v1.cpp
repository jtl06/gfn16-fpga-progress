#include "Vgenefer_anext_core_v1.h"
#include "verilated.h"
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#ifndef A4_CORE_AW
#error A4_CORE_AW must match -GAW
#endif
static_assert(A4_CORE_AW==5 || A4_CORE_AW==8 || A4_CORE_AW==16,"native representative whole-core gate");
#include "track_a4_representative_recipe_v1.hpp"
static void need(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
int main(int argc,char** argv){
    try{
        VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
        Vgenefer_anext_core_v1 d{&context};
        if(argc==2 && std::string(argv[1])=="--runtime-probe"){
            std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
            return context.threads()==1 && d.threads()==1?0:2;
        }
        need(argc==2 && std::string(argv[1])=="--representative","usage: a4_core --representative | --runtime-probe");
        std::istringstream input(a4_representative_vectors());need(bool(input),"A4_CORE_RECIPE");
        std::string magic;unsigned aw,count;need(bool(input>>magic>>aw>>count),"A4_CORE_HEADER");
        need(magic=="A4CORE1" && aw==A4_CORE_AW && count==12*(1u<<aw)+20,"A4_CORE_PROFILE");
        d.cmd_valid=0;d.rsp_ready=0;d.cmd_double=0;d.rst_n=0;d.clk=0;
        uint64_t ticks=0,readbacks=0,squares=0,cold_squares=0,loads=0,hold_checks=0,maximum_latency=0;
        auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();++ticks;};
        tick();d.rst_n=1;tick();
        for(unsigned index=0;index<count;++index){
            unsigned op,address,double_bit,expected_image,expected_prefill;int cold,load;
            uint64_t word,base,expected_word;
            need(bool(input>>op>>address>>word>>base>>double_bit>>expected_word>>expected_image>>expected_prefill>>cold>>load),"A4_CORE_TRUNCATED");
            need(op<=5 && address<(1u<<aw) && double_bit<2 && word<=0xffffffffu && base<=0xffffffffu && expected_word<=0xffffffffu,"A4_CORE_RANGE");
            need(d.cmd_ready && !d.rsp_valid,"A4_CORE_READY");
            d.cmd_opcode=op;d.cmd_address=address;d.cmd_word=uint32_t(word);d.cmd_base=uint32_t(base);d.cmd_double=double_bit;
            d.cmd_valid=1;tick();d.cmd_valid=0;d.cmd_opcode=7;d.cmd_base=0xffffffffu;d.cmd_word=0x80000000u;d.cmd_double=1-double_bit;
            uint64_t latency=0;
            while(!d.rsp_valid && latency<1000000){
                need(!d.cmd_ready,"A4_CORE_MISSING_BACKPRESSURE");
                d.cmd_valid=latency==2;tick();d.cmd_valid=0;++latency;
            }
            const auto at=" command="+std::to_string(index)+" opcode="+std::to_string(op)+" code="+std::to_string(d.rsp_error_code);
            need(d.rsp_valid,"A4_CORE_TIMEOUT"+at);
            need(d.rsp_opcode==op && !d.rsp_error && d.rsp_error_code==0,"A4_CORE_RESPONSE_ERROR"+at);
            need(uint32_t(d.rsp_word)==expected_word && d.image_valid==expected_image && !d.fault_sticky && d.prefill_valid==expected_prefill,"A4_CORE_WORD_OR_ELIGIBILITY"+at);
            if(op==5){
                need(cold>=0 && load>=0 && d.profile_loads==unsigned(load) && d.profile_hits==unsigned(1-load),"A4_CORE_PROFILE_METRICS"+at);
                need((d.prefill_cycles!=0)==bool(cold) && d.ntt_cycles>0 && d.post_cycles>0 && d.square_cycles>0,"A4_CORE_PHASE_METRICS"+at);
                std::cout<<"A4_CORE_SQUARE index="<<index<<" cold="<<cold<<" load="<<load<<" double="<<double_bit
                         <<" latency="<<latency<<" total="<<d.square_cycles<<" prefill="<<d.prefill_cycles
                         <<" root="<<d.root_cycles<<" ntt="<<d.ntt_cycles<<" post="<<d.post_cycles
                         <<" seed="<<d.seed_setup_cycles<<"\n";
                ++squares;cold_squares+=unsigned(cold);loads+=unsigned(load);
            }
            const auto generation=d.rsp_generation;
            for(unsigned hold=0;hold<2;++hold){
                tick();need(d.rsp_valid && d.rsp_generation==generation && d.rsp_opcode==op && uint32_t(d.rsp_word)==expected_word && !d.rsp_error,"A4_CORE_RESPONSE_HOLD"+at);++hold_checks;
            }
            if(latency>maximum_latency)maximum_latency=latency;
            readbacks+=op==2;
            d.rsp_ready=1;tick();d.rsp_ready=0;
        }
        // Reset an actual in-flight square; no stale completion or image.
        d.cmd_opcode=5;d.cmd_double=0;d.cmd_valid=1;tick();d.cmd_valid=0;
        for(unsigned i=0;i<10;++i)tick();
        d.rst_n=0;tick();d.rst_n=1;
        for(unsigned i=0;i<256;++i){tick();need(!d.rsp_valid && !d.busy && !d.image_valid && !d.prefill_valid,"A4_CORE_RESET_CANCEL");}
        std::string trailing;need(!(input>>trailing),"A4_CORE_TRAILING");
        need(context.threads()==1 && d.threads()==1,"A4_CORE_THREAD_DRIFT");
        std::cout<<"A4_CORE_PASS aw="<<aw<<" commands="<<count<<" squares="<<squares<<" cold_squares="<<cold_squares
                 <<" profile_loads="<<loads<<" readbacks="<<readbacks<<" hold_checks="<<hold_checks
                 <<" ticks="<<ticks<<" max_latency="<<maximum_latency<<"\n";
        d.final();return 0;
    }catch(const std::exception& ex){std::cerr<<ex.what()<<"\n";return 1;}
}
