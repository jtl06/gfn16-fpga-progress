#include "Vgenefer_div96_recip_prefix.h"
#include "verilated.h"
#include <cstdint>
#include <deque>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
using I=__int128_t;
static I parse(const std::string& s){I x=0;size_t i=s[0]=='-'?1:0;for(;i<s.size();i++)x=x*10+s[i]-'0';return s[0]=='-'?-x:x;}
template<class T>static void put(T& a,I x){for(unsigned j=0;j<3;j++)a[j]=uint32_t(__uint128_t(x)>>(32*j));}
template<class T>static I get(const T& a){__uint128_t x=__uint128_t(a[0])|(__uint128_t(a[1])<<32)|(__uint128_t(a[2])<<64);return a[2]&0x80000000u?I(x)-(I(1)<<96):I(x);}
struct Pending{uint64_t due;I q;uint32_t r,tag;};
int main(int argc,char** argv){
    try{
        Verilated::commandArgs(argc,argv);if(argc!=2)throw std::runtime_error("vectors required");
        std::ifstream f(argv[1]);Vgenefer_div96_recip_prefix d;std::deque<Pending> queue;
        uint64_t clock=0,checked=0,canceled=0;unsigned reset,valid,b,tag,rem;std::string x,q,recip;
        while(f>>reset>>valid>>b>>recip>>x>>q>>rem>>tag){
            d.clk=0;d.rst_n=reset;d.in_valid=valid;d.base=b;put(d.reciprocal,parse(recip));put(d.value,parse(x));d.payload_in=tag;d.eval();
            if(!reset){canceled+=queue.size();queue.clear();}
            else if(valid)queue.push_back({clock+6,parse(q),rem,tag});
            d.clk=1;d.eval();bool expected=!queue.empty()&&queue.front().due==clock;
            if(bool(d.out_valid)!=expected)throw std::runtime_error("divider valid mismatch");
            if(expected){auto p=queue.front();queue.pop_front();if(get(d.quotient)!=p.q||d.remainder!=p.r||d.payload_out!=p.tag)throw std::runtime_error("divider arithmetic/payload mismatch cycle="+std::to_string(clock));checked++;}
            clock++;
        }
        if(!queue.empty()||checked<1000)throw std::runtime_error("divider unfinished");
        std::cout<<"PASS divider checked="<<checked<<" canceled="<<canceled<<" cycles="<<clock<<"\n";
    }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
