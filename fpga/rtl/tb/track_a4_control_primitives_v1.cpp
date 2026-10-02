#include "Vtrack_a4_control_primitives_probe_v1.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#ifndef A4_CONTROL_AW
#error A4_CONTROL_AW must match -GAW in the approved compile
#endif
static_assert(A4_CONTROL_AW==5 || A4_CONTROL_AW==16,"explicit scalar control primitives");
static void need(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
static std::array<uint32_t,3> word96(const std::string& text){
    need(text.size()==24,"A4_CONTROL_HEX");std::array<uint32_t,3> words{};
    for(unsigned i=0;i<3;++i)words[i]=uint32_t(std::stoul(text.substr(16-8*i,8),nullptr,16));
    return words;
}
int main(int argc,char** argv){
    try{
        VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
        Vtrack_a4_control_primitives_probe_v1 d{&context};
        if(argc==2 && std::string(argv[1])=="--runtime-probe"){
            std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
            return context.threads()==1 && d.threads()==1?0:2;
        }
        need(argc==2,"usage: a4_control vectors | --runtime-probe");
        std::ifstream input(argv[1]);need(bool(input),"A4_CONTROL_OPEN");
        std::string magic;unsigned aw;uint64_t count;
        need(bool(input>>magic>>aw>>count),"A4_CONTROL_HEADER");
        need(magic=="A4CONTROL1" && aw==A4_CONTROL_AW && count>0 && count<100000,"A4_CONTROL_PROFILE");
        d.clk=0;d.rst_n=0;d.setup_begin=0;d.cell_in_valid=0;d.cancel=0;d.eval();
        uint64_t successes=0,setup_errors=0,cell_valid=0,cell_errors=0;
        for(uint64_t edge=0;edge<count;++edge){
            unsigned rst,cancel,begin,cv,carry,tag,busy,done,error,cfg,ov,oe,oc,ot;
            uint64_t base,gen,cb,y,ab,og,digit;std::string limit,reciprocal;
            need(bool(input>>rst>>cancel>>begin>>base>>gen>>cv>>cb>>y>>carry>>tag
                >>busy>>done>>error>>cfg>>ab>>og>>limit>>reciprocal>>ov>>oe>>digit>>oc>>ot),"A4_CONTROL_TRUNCATED");
            need(rst<=1 && cancel<=1 && begin<=1 && cv<=1 && busy<=1 && done<=1 && error<=1 && cfg<=1
                && ov<=1 && oe<=1 && carry<=7 && oc<=7 && tag<=65535 && ot<=65535 && y<(uint64_t(1)<<33)
                && base<=0xffffffffu && gen<=0xffffffffu && cb<=0xffffffffu && ab<=0xffffffffu && og<=0xffffffffu
                && digit<=0xffffffffu,"A4_CONTROL_PORT_RANGE");
            auto expected_limit=word96(limit),expected_reciprocal=word96(reciprocal);
            d.clk=0;d.eval();d.rst_n=rst;d.cancel=cancel;d.setup_begin=begin;
            d.setup_base=uint32_t(base);d.setup_generation=uint32_t(gen);
            d.cell_in_valid=cv;d.cell_base=uint32_t(cb);d.cell_value=y;d.cell_carry_in=carry;d.cell_tag=tag;
            d.eval();d.clk=1;d.eval();const auto at=" edge="+std::to_string(edge);
            need(d.setup_busy==busy && d.setup_done==done && d.setup_error==error && d.config_valid==cfg
                && d.accepted_base==ab && d.out_generation==og,"A4_SETUP_CONTROL"+at);
            for(unsigned i=0;i<3;++i)need(d.coefficient_limit[i]==expected_limit[i] && d.reciprocal[i]==expected_reciprocal[i],"A4_SETUP_EXACT_INTEGER"+at);
            need(d.cell_valid==ov && d.cell_error==oe && d.cell_digit==digit && d.cell_carry==oc && d.cell_tag_out==ot,"A4_CANON_CELL_EXACT_OR_HOLD"+at);
            successes+=done && !error;setup_errors+=error;cell_valid+=ov;cell_errors+=oe;
        }
        std::string trailing;need(!(input>>trailing),"A4_CONTROL_TRAILING");
        need(context.threads()==1 && d.threads()==1,"A4_CONTROL_THREAD_DRIFT");
        std::cout<<"A4_CONTROL_PRIMITIVES_PASS aw="<<aw<<" events="<<count<<" setup_success="<<successes
                 <<" setup_errors="<<setup_errors<<" cell_valid="<<cell_valid<<" cell_errors="<<cell_errors<<"\n";
        d.final();return 0;
    }catch(const std::exception& ex){std::cerr<<ex.what()<<"\n";return 1;}
}
