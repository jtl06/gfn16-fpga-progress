#include "Vtrack_a4_blockcarry_lane_probe_v1.h"
#include "verilated.h"
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

#ifndef A4_LANE_AW
#error A4_LANE_AW must match the explicit approved native compile parameter
#endif
static_assert(A4_LANE_AW==5 || A4_LANE_AW==8,"source-only small-N gate");
static void need(bool ok,const std::string& msg){if(!ok)throw std::runtime_error(msg);}
template<class Wide> static void word96(Wide& port,const std::string& text){
    need(text.size()==24,"A4_HEX_WIDTH");
    for(unsigned i=0;i<3;++i)port[i]=uint32_t(std::stoul(text.substr(16-8*i,8),nullptr,16));
}
int main(int argc,char** argv){
    try{
        VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
        Vtrack_a4_blockcarry_lane_probe_v1 d{&context};
        if(argc==2 && std::string(argv[1])=="--runtime-probe"){
            std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
            return context.threads()==1 && d.threads()==1?0:2;
        }
        need(argc==2,"usage: a4_lane vectors | --runtime-probe");
        std::ifstream input(argv[1]);need(bool(input),"A4_VECTOR_OPEN");
        std::string magic;unsigned aw;uint64_t count;
        need(bool(input>>magic>>aw>>count),"A4_HEADER");
        need(magic=="A4LANE1" && aw==A4_LANE_AW && count>0 && count<100000,"A4_PROFILE");
        d.clk=0;d.rst_n=0;d.begin_block=0;d.in_valid=0;d.eval();
        uint64_t digits=0,boundaries=0,done_count=0,error_edges=0;
        for(uint64_t edge=0;edge<count;++edge){
            unsigned rst,begin,valid,first,last,offset,busy,done,error,code,dv,tag,bv;
            uint64_t base,digit,low,high;std::string recip,limit,coefficient;
            need(bool(input>>rst>>begin>>valid>>first>>last>>base>>recip>>limit>>coefficient>>offset
                >>busy>>done>>error>>code>>dv>>digit>>tag>>bv>>low>>high),"A4_TRUNCATED");
            need(rst<=1 && begin<=1 && valid<=1 && first<=1 && last<=1 && offset<(1u<<aw)
                && base<=0xffffffffu && busy<=1 && done<=1 && error<=1 && code<=15
                && dv<=1 && bv<=1 && digit<=0xffffffffu && low<=0xffffffffu && high<=0xffffffffu,"A4_PORT_RANGE");
            d.clk=0;d.eval();
            d.rst_n=rst;d.begin_block=begin;d.in_valid=valid;d.block_start=first;d.block_end=last;
            d.base=uint32_t(base);d.offset=offset;
            need(limit.size()==24 && std::stoul(limit.substr(0,8),nullptr,16)<=0x1fffu,"A4_LIMIT_PORT_WIDTH");
            word96(d.reciprocal,recip);word96(d.coefficient_limit,limit);word96(d.coefficient,coefficient);
            d.eval();
            if(!rst)need(!d.digit_valid && !d.boundary_valid && !d.done && !d.error,"A4_RESET_CANCEL");
            d.clk=1;d.eval();
            const std::string at=" edge="+std::to_string(edge);
            need(d.busy==busy && d.done==done && d.error==error && d.error_code==code,"A4_STATE_OR_ERROR"+at);
            need(d.digit_valid==dv && d.boundary_valid==bv,"A4_VALID_OR_LATENCY"+at);
            if(dv)need(d.digit==digit && d.digit_offset==tag,"A4_DIGIT_OR_TAG"+at);
            if(bv)need(d.boundary_low==low && uint32_t(d.boundary_high)==high,"A4_BOUNDARY_PAIR"+at);
            digits+=dv;boundaries+=bv;done_count+=done;error_edges+=error;
        }
        std::string trailing;need(!(input>>trailing),"A4_TRAILING");
        need(context.threads()==1 && d.threads()==1,"A4_THREAD_DRIFT");
        std::cout<<"A4_LANE_PASS aw="<<aw<<" events="<<count<<" digits="<<digits
                 <<" boundaries="<<boundaries<<" completed="<<done_count<<" error_edges="<<error_edges<<"\n";
        d.final();return 0;
    }catch(const std::exception& ex){std::cerr<<ex.what()<<"\n";return 1;}
}
