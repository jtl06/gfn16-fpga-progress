#include "Vgenefer_sp_ram.h"
#include "verilated.h"
#include <cstdint>
#include <iostream>
#include <random>
#include <stdexcept>
#include <vector>
#ifndef TEST_WIDTH
#define TEST_WIDTH 96
#endif
#ifndef TEST_DEPTH
#define TEST_DEPTH 64
#endif
using U=__uint128_t;
int main(int argc,char** argv){try{
    Verilated::commandArgs(argc,argv);Vgenefer_sp_ram d;
    constexpr unsigned W=TEST_WIDTH,D=TEST_DEPTH;const U mask=(U(1)<<W)-1;
    std::vector<U> memory(D);U expected=0;bool known=false;unsigned checks=0;
    auto get=[&]()->U{
#if TEST_WIDTH<=64
        return U(d.read_data);
#else
        return U(d.read_data[0])|(U(d.read_data[1])<<32)|(U(d.read_data[2])<<64);
#endif
    };
    auto step=[&](bool reset,bool en,bool we,unsigned addr,U data){
        d.rst_n=reset;d.en=en;d.write_en=we;d.addr=addr;
#if TEST_WIDTH<=64
        d.write_data=uint64_t(data);
#else
        for(unsigned j=0;j<3;j++)d.write_data[j]=uint32_t(data>>(32*j));
#endif
        d.clk=0;d.eval();if(known&&get()!=expected)throw std::runtime_error("RAM combinational/reset hold mismatch");
        if(reset&&en){if(we)memory[addr]=data;else{expected=memory[addr];known=true;}}
        d.clk=1;d.eval();checks++;
        if(known&&get()!=expected)throw std::runtime_error("RAM registered data/hold mismatch");
    };
    std::mt19937_64 rng(0x9a7133);
    for(unsigned i=0;i<D;i++)step(true,true,true,i,(U(rng())|(U(rng())<<64))&mask);
    step(true,true,false,0,0);
    for(unsigned k=0;k<20000;k++)step(k%7!=0,rng()&1,rng()&1,rng()%D,(U(rng())|(U(rng())<<64))&mask);
    for(unsigned i=0;i<D;i++)step(true,true,false,i,0);
    std::cout<<"PASS width="<<W<<" depth="<<D<<" checks="<<checks<<"\n";
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
