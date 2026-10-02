#include "Vgenefer_crt3_27_pair_pipe.h"
#include "verilated.h"
#include <cstdint>
#include <deque>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
using I=__int128_t;
static I parse(const std::string& s){I x=0;size_t i=s[0]=='-'?1:0;for(;i<s.size();i++)x=x*10+s[i]-'0';return s[0]=='-'?-x:x;}
template<class T>static I get(const T& a){__uint128_t x=__uint128_t(a[0])|(__uint128_t(a[1])<<32)|(__uint128_t(a[2])<<64);return a[2]&0x80000000u?I(x)-(I(1)<<96):I(x);}
struct Pending{uint64_t due;I expected;};
int main(int argc,char** argv){try{
    Verilated::commandArgs(argc,argv);if(argc<2)throw std::runtime_error("vectors required");
    Vgenefer_crt3_27_pair_pipe d;
    if(std::string(argv[1])=="reject"){
        if(argc!=5)throw std::runtime_error("reject residues required");
        d.rst_n=0;d.in_valid=0;d.clk=0;d.eval();d.clk=1;d.eval();
        d.rst_n=1;d.in_valid=1;d.r1=std::stoul(argv[2]);d.r2=std::stoul(argv[3]);d.r3=std::stoul(argv[4]);
        d.clk=0;d.eval();d.clk=1;d.eval();throw std::runtime_error("CRT27 input assertion missing");
    }
    std::ifstream f(argv[1]);if(!f)throw std::runtime_error("input open");
    std::deque<Pending> queue;uint64_t clock=0,checked=0,canceled=0,hold_checks=0;I held=0;
    const I half=parse("243972611374018097905664");
    unsigned reset,valid,r1,r2,r3;std::string coefficient;
    while(f>>reset>>valid>>r1>>r2>>r3>>coefficient){
        d.clk=0;d.rst_n=reset;d.in_valid=valid;d.r1=r1;d.r2=r2;d.r3=r3;d.eval();
        if(!reset){canceled+=queue.size();queue.clear();held=0;}
        else if(get(d.coefficient)!=held)throw std::runtime_error("CRT27 combinational output changed");
        if(reset&&valid)queue.push_back({clock+95,parse(coefficient)});
        d.clk=1;d.eval();bool expected=!queue.empty()&&queue.front().due==clock;
        if(!d.ready||bool(d.out_valid)!=expected)throw std::runtime_error("CRT27 ready/latency mismatch cycle="+std::to_string(clock));
        if(expected){
            auto q=queue.front();queue.pop_front();I actual=get(d.coefficient);
            if(actual!=q.expected||actual < -half||actual>half)throw std::runtime_error("CRT27 arithmetic/sign/tag mismatch cycle="+std::to_string(clock));
            held=actual;checked++;
        }else{if(get(d.coefficient)!=held)throw std::runtime_error("CRT27 invalid-cycle hold mismatch");hold_checks++;}
        clock++;
    }
    if(!f.eof()||!queue.empty()||checked<1000)throw std::runtime_error("CRT27 incomplete vectors");
    std::cout<<"PASS checked="<<checked<<" canceled="<<canceled<<" hold_checks="<<hold_checks<<" cycles="<<clock<<"\n";
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
