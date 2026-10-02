#include "Vgenefer_mod27_pair_pipe.h"
#include "verilated.h"
#include <cstdint>
#include <deque>
#include <fstream>
#include <iostream>
#include <stdexcept>
#ifndef TEST_WORD_W
#define TEST_WORD_W 53
#endif
struct Pending{uint64_t due;uint32_t remainder,payload;};
int main(int argc,char** argv){try{
    Verilated::commandArgs(argc,argv);
    if(argc!=2)throw std::runtime_error("mod27 vectors required");
    std::ifstream input(argv[1]);if(!input)throw std::runtime_error("mod27 input open");
    Vgenefer_mod27_pair_pipe d;
    std::deque<Pending> pending;
    uint64_t clock=0,checked=0,canceled=0,word;uint32_t reset,valid,payload,remainder;
    while(input>>reset>>valid>>word>>payload>>remainder){
        d.clk=0;d.rst_n=reset;d.in_valid=valid;d.word_in=word;d.payload_in=payload;d.eval();
        if(!reset){canceled+=pending.size();pending.clear();}
        else if(valid)pending.push_back({clock+(TEST_WORD_W+1)/2-1,remainder,payload});
        d.clk=1;d.eval();bool expected=!pending.empty()&&pending.front().due==clock;
        if(bool(d.out_valid)!=expected)throw std::runtime_error("mod27 latency/reset mismatch");
        if(expected){auto item=pending.front();pending.pop_front();
            if(d.remainder!=item.remainder||d.payload_out!=item.payload)
                throw std::runtime_error("mod27 arithmetic/payload mismatch");
            checked++;
        }
        clock++;
    }
    if(!input.eof()||!pending.empty()||checked<1000)throw std::runtime_error("mod27 incomplete vectors");
    std::cout<<"PASS width="<<TEST_WORD_W<<" checked="<<checked<<" canceled="<<canceled<<" cycles="<<clock<<"\n";
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
