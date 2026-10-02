#include "Vtrack_a4_blockroute_probe_v1.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#ifndef A4_ROUTE_AW
#error A4_ROUTE_AW must match -GAW in the approved native compile
#endif
static_assert(A4_ROUTE_AW==5 || A4_ROUTE_AW==8,"explicit small-N route probe");
static void need(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
int main(int argc,char** argv){
    try{
        VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
        Vtrack_a4_blockroute_probe_v1 d{&context};
        if(argc==2 && std::string(argv[1])=="--runtime-probe"){
            std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
            return context.threads()==1 && d.threads()==1?0:2;
        }
        need(argc==2,"usage: a4_route vectors | --runtime-probe");
        std::ifstream input(argv[1]);need(bool(input),"A4_ROUTE_OPEN");
        std::string magic;unsigned aw;uint64_t count;
        need(bool(input>>magic>>aw>>count),"A4_ROUTE_HEADER");
        need(magic=="A4ROUTE1" && aw==A4_ROUTE_AW && count>0 && count<100000,"A4_ROUTE_PROFILE");
        d.clk=0;d.rst_n=0;d.read_en=0;d.write_en=0;d.eval();
        uint64_t responses=0,errors=0,checked=0;
        for(uint64_t edge=0;edge<count;++edge){
            unsigned rst,enable,re,we,ro,wo,rm,wm,error,valid,tag,mask;
            std::array<uint64_t,16> words,expected;
            need(bool(input>>rst>>enable>>re>>we>>ro>>wo>>rm>>wm),"A4_ROUTE_TRUNCATED");
            for(auto& word:words)need(bool(input>>word) && word<=0xffffffffu,"A4_ROUTE_WRITE_WORD");
            need(bool(input>>error>>valid>>tag>>mask),"A4_ROUTE_EXPECTED_HEADER");
            for(auto& word:expected)need(bool(input>>word) && word<=0xffffffffu,"A4_ROUTE_EXPECTED_WORD");
            need(rst<=1 && enable<=1 && re<=1 && we<=1 && ro<(1u<<aw) && wo<(1u<<aw)
                && rm<=65535 && wm<=65535 && error<=1 && valid<=1 && tag<(1u<<aw) && mask<=65535,"A4_ROUTE_PORT_RANGE");
            d.clk=0;d.eval();d.rst_n=rst;d.enable=enable;d.read_en=re;d.write_en=we;
            d.read_offset=ro;d.write_offset=wo;d.read_mask=rm;d.write_mask=wm;
            for(unsigned lane=0;lane<16;++lane)d.write_words[lane]=uint32_t(words[lane]);
            d.eval();if(!rst)need(!d.error && !d.read_valid && !d.read_mask_out,"A4_ROUTE_RESET_CANCEL");
            d.clk=1;d.eval();const auto at=" edge="+std::to_string(edge);
            need(d.request==unsigned(bool(re || we)),"A4_ROUTE_REQUEST"+at);
            need(d.error==error && d.read_valid==valid && d.read_mask_out==mask && d.read_offset_out==tag,"A4_ROUTE_VALID_OR_TAG"+at);
            for(unsigned lane=0;lane<16;++lane)if(valid && ((mask>>lane)&1)){
                need(d.read_words[lane]==expected[lane],"A4_ROUTE_WORD_OR_ALIGNMENT"+at+" lane="+std::to_string(lane));++checked;
            }
            responses+=valid;errors+=error;
        }
        std::string trailing;need(!(input>>trailing),"A4_ROUTE_TRAILING");
        need(context.threads()==1 && d.threads()==1,"A4_ROUTE_THREAD_DRIFT");
        std::cout<<"A4_ROUTE_PASS aw="<<aw<<" events="<<count<<" responses="<<responses<<" errors="<<errors<<" words="<<checked<<"\n";
        d.final();return 0;
    }catch(const std::exception& ex){std::cerr<<ex.what()<<"\n";return 1;}
}
