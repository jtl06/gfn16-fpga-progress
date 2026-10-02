#include "Vgenefer_stream27_fused_lazy28_butterfly_v1.h"
#include "verilated.h"
#include <cstdint>
#include <deque>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#ifndef TEST_P
#define TEST_P 104857601
#endif
static constexpr uint64_t P=TEST_P;
static void require(bool good,const char* message){if(!good)throw std::runtime_error(message);}
static uint64_t power(uint64_t x,uint64_t n){uint64_t y=1;while(n){if(n&1)y=y*x%P;x=x*x%P;n>>=1;}return y;}
struct Pending {uint64_t due;uint32_t y0,y1,tag;};
int main(int argc,char**argv){try{
    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
    Vgenefer_stream27_fused_lazy28_butterfly_v1 d{&context};d.eval();
    if(argc==2&&std::string(argv[1])=="--runtime-probe"){
        std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
        return context.threads()==1&&d.threads()==1?0:2;
    }
    require(argc==2,"LAZY_BFLY_ARGS");std::ifstream input(argv[1]);
    std::string magic;uint64_t field,events;input>>magic>>field>>events;
    require(magic=="LAZYBFLY1"&&field==P&&events>0,"LAZY_BFLY_HEADER");
    const uint64_t ri=power((uint64_t(1)<<32)%P,P-2);
    std::deque<Pending> pending;uint64_t checked=0,cancelled=0,high=0,ct=0,gs=0;
    uint32_t last0=0,last1=0,lasttag=0;bool lastvalid=false;
    for(uint64_t edge=0;edge<events;edge++){
        unsigned reset,valid,form;uint64_t u,v,w,tag;
        require(bool(input>>reset>>valid>>form>>u>>v>>w>>tag),"LAZY_BFLY_SHORT_INPUT");
        require(reset<2&&valid<2&&form<2&&u<2*P&&v<2*P&&w<P&&tag<(uint64_t(1)<<32),"LAZY_BFLY_INPUT_RANGE");
        d.clk=0;d.rst_n=reset;d.in_valid=valid;d.gs=form;d.u=u;d.v=v;d.w=w;d.in_tag=tag;d.eval();
        if(!reset){cancelled+=pending.size();pending.clear();lastvalid=false;last0=last1=lasttag=0;}
        require(bool(d.out_valid)==lastvalid&&d.y0==last0&&d.y1==last1&&d.out_tag==lasttag,"LAZY_BFLY_BEFORE_EDGE");
        if(reset&&valid){
            uint64_t a,b;
            if(form){a=(u+v)%(2*P);b=(((u+2*P-v)%(2*P))*w%P)*ri%P;gs++;}
            else {uint64_t uc=u%P,t=(v*w%P)*ri%P;a=uc+t;b=uc+P-t;ct++;}
            pending.push_back({edge+5,uint32_t(a),uint32_t(b),uint32_t(tag)});high+=bool((u|v)>>27);
        }
        bool due=!pending.empty()&&pending.front().due==edge;
        d.clk=1;d.eval();
        require(bool(d.out_valid)==due,"LAZY_BFLY_VALID_MISMATCH");
        if(due){
            Pending expected=pending.front();pending.pop_front();
            require(d.y0<2*P&&d.y1<2*P,"LAZY_BFLY_RANGE_MISMATCH");
            require(d.y0%P==expected.y0%P&&d.y1%P==expected.y1%P,"P5_BFLY_MODULAR_VALUE_MISMATCH");
            require(d.out_tag==expected.tag,"LAZY_BFLY_TAG_MISMATCH");
            last0=d.y0;last1=d.y1;lasttag=d.out_tag;checked++;
        }else require(d.y0==last0&&d.y1==last1&&d.out_tag==lasttag,"LAZY_BFLY_INVALID_HOLD");
        lastvalid=due;
    }
    std::string extra;require(!(input>>extra)&&input.eof()&&pending.empty(),"LAZY_BFLY_TAIL");
    std::cout<<"P5_FUSED_BFLY_PASS p="<<P<<" events="<<events<<" checked="<<checked<<" cancelled="<<cancelled
        <<" high_inputs="<<high<<" ct="<<ct<<" gs="<<gs<<"\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
