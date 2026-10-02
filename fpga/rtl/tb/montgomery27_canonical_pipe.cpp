#include "Vgenefer_montgomery_mul27_canonical_pipe.h"
#include "verilated.h"
#include <cstdint>
#include <deque>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

// Independent ordinary modular arithmetic; no sparse Montgomery identities.
static uint32_t power(uint64_t x,uint32_t exponent,uint32_t p) {
    uint64_t value=1;x%=p;
    while(exponent){if(exponent&1)value=value*x%p;x=x*x%p;exponent>>=1;}
    return uint32_t(value);
}
static uint32_t product(uint32_t a,uint32_t b,uint32_t p,uint32_t inverse) {
    return uint32_t((uint64_t(a)*b%p)*inverse%p);
}
struct Pending {uint64_t due;uint32_t expected;};

int main(int argc,char** argv) {try {
    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
    Vgenefer_montgomery_mul27_canonical_pipe d{&context};
    if(argc==2 && std::string(argv[1])=="--runtime-probe") {
        std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
        return context.threads()==1 && d.threads()==1 ? 0 : 2;
    }
    if(argc<3)throw std::runtime_error("vector path and modulus required");
    uint32_t p=uint32_t(std::stoul(argv[2]));
    if(std::string(argv[1])=="reject") {
        d.rst_n=0;d.in_valid=0;d.clk=0;d.eval();d.clk=1;d.eval();
        d.rst_n=1;d.in_valid=1;d.lhs=argc>3?std::stoul(argv[3]):p;d.rhs=argc>4?std::stoul(argv[4]):1;
        d.clk=0;d.eval();d.clk=1;d.eval();
        throw std::runtime_error("retained assertion missing");
    }
    if(p!=104857601u && p!=69206017u && p!=67239937u)throw std::runtime_error("unknown oracle field");
    uint32_t inverse=power((uint64_t(1)<<32)%p,p-2,p);
    if(((uint64_t(1)<<32)%p)*inverse%p!=1)throw std::runtime_error("oracle radix inverse");
    std::ifstream f(argv[1]);if(!f)throw std::runtime_error("input open");
    std::deque<Pending> queue;uint64_t clock=0,checked=0,canceled=0,held_checks=0;
    uint32_t held=0,expected_value,lhs,rhs;unsigned reset,valid;
    while(true) {
        if(!(f>>reset)) {if(f.eof())break;throw std::runtime_error("invalid vector control");}
        if(!(f>>valid>>lhs>>rhs>>expected_value))throw std::runtime_error("truncated vector row");
        if(reset>1||valid>1)throw std::runtime_error("nonboolean vector controls");
        if(reset&&valid && (lhs>=p||rhs>=p||expected_value!=product(lhs,rhs,p,inverse)))
            throw std::runtime_error("independent input vector oracle mismatch");
        d.clk=0;d.rst_n=reset;d.in_valid=valid;d.lhs=lhs;d.rhs=rhs;d.eval();
        if(!reset){canceled+=queue.size();queue.clear();held=0;}
        else if(d.result!=held)throw std::runtime_error("combinational result changed");
        if(reset&&valid)queue.push_back({clock+3,expected_value});
        d.clk=1;d.eval();bool expected=!queue.empty()&&queue.front().due==clock;
        if(bool(d.out_valid)!=expected)throw std::runtime_error("valid/latency mismatch cycle="+std::to_string(clock));
        if(d.result>>27)throw std::runtime_error("nonzero upper five result bits");
        if(expected) {
            auto q=queue.front();queue.pop_front();
            if(d.result!=q.expected||d.result>=p)throw std::runtime_error("Montgomery arithmetic mismatch cycle="+std::to_string(clock));
            held=d.result;++checked;
        } else {
            if(d.result!=held)throw std::runtime_error("invalid-cycle result hold mismatch");
            ++held_checks;
        }
        ++clock;
    }
    if(!f.eof()||!queue.empty()||checked<1000)throw std::runtime_error("incomplete Montgomery vectors");
    if(context.threads()!=1||d.threads()!=1)throw std::runtime_error("runtime thread identity changed");
    std::cout<<"PASS P="<<p<<" checked="<<checked<<" canceled="<<canceled<<" hold_checks="<<held_checks<<" cycles="<<clock<<"\n";
    d.final();return 0;
} catch(const std::exception& e) {std::cerr<<e.what()<<"\n";return 1;}}
