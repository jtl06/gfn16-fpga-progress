#include "Vgenefer_stream27_blockcarry_small_cell.h"
#include "verilated.h"
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

#ifndef SCELL_AW
#error SCELL_AW must be fixed by approved compile command
#endif
static_assert(SCELL_AW==5 || SCELL_AW==16,"explicit native small-cell profile");
static void need(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
static int signed3(unsigned x){x&=7;return x&4?int(x)-8:int(x);}
struct Sample{unsigned valid,error,digit,carry,payload;};
static Sample sample(const Vgenefer_stream27_blockcarry_small_cell& d){
    return {unsigned(d.out_valid),unsigned(d.out_error),uint32_t(d.digit),unsigned(d.carry_out),unsigned(d.payload_out)};
}
static bool equal(const Sample& a,const Sample& b){
    return a.valid==b.valid && a.error==b.error && a.digit==b.digit && a.carry==b.carry && a.payload==b.payload;
}
int main(int argc,char** argv){
    try{
        VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
        Vgenefer_stream27_blockcarry_small_cell d{&context};
        if(argc==2 && std::string(argv[1])=="--runtime-probe"){
            std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
            return context.threads()==1 && d.threads()==1?0:2;
        }
        need(argc==2,"usage: stream27_small_carry vectors | --runtime-probe");
        std::ifstream input(argv[1]);need(bool(input),"SCELL_VECTOR_OPEN");
        std::string magic;unsigned aw,p,pw;uint64_t count;
        need(bool(input>>magic>>aw>>p>>pw>>count),"SCELL_VECTOR_HEADER");
        need(magic=="SCELL1" && aw==SCELL_AW && p==8 && pw==16 && count>0 && count<100000,"SCELL_VECTOR_PROFILE");
        uint64_t good=0,errors=0,bubbles=0,resets=0,feedbacks=0,carry_mask=0;
        d.clk=1;d.rst_n=0;d.in_valid=0;d.eval();
        for(uint64_t index=0;index<count;++index){
            unsigned rst,valid,start,feedback,tag,ev,ee;uint64_t base;int64_t y,carry,ed,ec,ep;
            need(bool(input>>rst>>valid>>start>>base>>y>>carry>>feedback>>tag>>ev>>ee>>ed>>ec>>ep),"SCELL_VECTOR_TRUNCATED");
            need(rst<=1 && valid<=1 && start<=1 && feedback<=1 && ev<=1 && ee<=1 && base<=0xffffffffu &&
                 y>=-(int64_t(1)<<32) && y<(int64_t(1)<<32) && carry>=-4 && carry<=3 && tag<=65535,
                 "SCELL_VECTOR_PORT_RANGE");
            need(ec>=-2 && ec<=3 && (ed==-1 || (ed>=0 && ed<1000000000)) &&
                 (ep==-1 || (ep>=0 && ep<=65535)),"SCELL_VECTOR_EXPECTED_RANGE");
            const Sample previous=sample(d);
            if(feedback){need(signed3(d.carry_out)==carry,"SCELL_EXTERNAL_FEEDBACK_BEFORE_EDGE");++feedbacks;}
            d.rst_n=rst;d.in_valid=valid;d.block_start=start;d.base=uint32_t(base);
            d.y=uint64_t(y)&((uint64_t(1)<<33)-1);
            d.carry_in=feedback?(unsigned(d.carry_out)&7):(unsigned(carry)&7);d.payload_in=tag;
            // Clock held high: only asynchronous reset may alter flags/carry.
            d.eval();Sample before=previous;
            if(!rst){before.valid=0;before.error=0;before.carry=0;}
            need(equal(sample(d),before),"SCELL_ASYNC_OR_COMBINATIONAL_LEAK index="+std::to_string(index));
            d.clk=0;d.eval();need(equal(sample(d),before),"SCELL_FALLING_EDGE_LEAK");
            d.clk=1;d.eval();
            need(d.out_valid==ev && d.out_error==ee && signed3(d.carry_out)==ec &&
                 (ed<0 || uint64_t(d.digit)==uint64_t(ed)) && (ep<0 || uint64_t(d.payload_out)==uint64_t(ep)),
                 "SCELL_INTEGER_OR_EDGE_MISMATCH index="+std::to_string(index));
            if(!rst)++resets;else if(!valid)++bubbles;else if(ev){++good;carry_mask|=uint64_t(1)<<(ec+2);}else ++errors;
        }
        std::string trailing;need(!(input>>trailing),"SCELL_VECTOR_TRAILING");
        need(context.threads()==1 && d.threads()==1,"SCELL_THREAD_DRIFT");
        std::cout<<"SMALL_CARRY_PASS aw="<<aw<<" p="<<p<<" events="<<count<<" good="<<good<<" errors="<<errors
                 <<" bubbles="<<bubbles<<" resets="<<resets<<" feedback="<<feedbacks<<" carry_mask="<<carry_mask
                 <<" before_checks="<<2*count<<" edge_checks="<<count<<"\n";
        d.final();return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}
}
