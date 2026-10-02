#include "Vgenefer_montgomery_mul27_pipe.h"
#include "verilated.h"
#include <cstdint>
#include <deque>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
struct Pending{uint64_t due;uint32_t expected;};
int main(int argc,char** argv){try{
    Verilated::commandArgs(argc,argv);if(argc<3)throw std::runtime_error("vector path and modulus required");
    uint32_t p=std::stoul(argv[2]);Vgenefer_montgomery_mul27_pipe d;
    if(std::string(argv[1])=="reject"){
        d.rst_n=0;d.in_valid=0;d.clk=0;d.eval();d.clk=1;d.eval();
        d.rst_n=1;d.in_valid=1;d.lhs=argc>3?std::stoul(argv[3]):p;d.rhs=argc>4?std::stoul(argv[4]):1;
        d.clk=0;d.eval();d.clk=1;d.eval();throw std::runtime_error("invalid input assertion missing");
    }
    std::ifstream f(argv[1]);if(!f)throw std::runtime_error("input open");
    std::deque<Pending> queue;uint64_t clock=0,checked=0,canceled=0,held_checks=0;
    uint32_t held=0,expected_value,lhs,rhs;unsigned reset,valid;
    while(f>>reset>>valid>>lhs>>rhs>>expected_value){
        d.clk=0;d.rst_n=reset;d.in_valid=valid;d.lhs=lhs;d.rhs=rhs;d.eval();
        if(!reset){canceled+=queue.size();queue.clear();held=0;}
        else if(d.result!=held)throw std::runtime_error("combinational result changed");
        if(reset&&valid)queue.push_back({clock+3,expected_value});
        d.clk=1;d.eval();bool expected=!queue.empty()&&queue.front().due==clock;
        if(bool(d.out_valid)!=expected)throw std::runtime_error("valid/latency mismatch cycle="+std::to_string(clock));
        if(expected){
            auto q=queue.front();queue.pop_front();
            if(d.result!=q.expected||d.result>=p)throw std::runtime_error("Montgomery arithmetic mismatch cycle="+std::to_string(clock));
            held=d.result;checked++;
        }else{
            if(d.result!=held)throw std::runtime_error("invalid-cycle result hold mismatch");
            held_checks++;
        }
        clock++;
    }
    if(!f.eof()||!queue.empty()||checked<1000)throw std::runtime_error("incomplete Montgomery vectors");
    std::cout<<"PASS P="<<p<<" checked="<<checked<<" canceled="<<canceled<<" hold_checks="<<held_checks<<" cycles="<<clock<<"\n";
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
