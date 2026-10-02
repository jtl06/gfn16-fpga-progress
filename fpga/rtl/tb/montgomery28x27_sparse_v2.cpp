#include "Vgenefer_montgomery_mul28x27_sparse_pipe_v2.h"
#include "verilated.h"
#include <cstdint>
#include <deque>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

#ifndef TEST_P
#error TEST_P must match the source-bound RTL P parameter
#endif
static constexpr uint32_t P = TEST_P;
static uint64_t power(uint64_t a, uint64_t n) {
    uint64_t y=1;
    for(; n; n>>=1,a=a*a%P) if(n&1) y=y*a%P;
    return y;
}
struct Pending { uint64_t due; uint32_t expected; };
int main(int argc,char** argv) { try {
    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
    Vgenefer_montgomery_mul28x27_sparse_pipe_v2 d{&context};
    if(argc==2 && std::string(argv[1])=="--thread-probe") {
        std::cout<<"{\"context_threads\":"<<context.threads()
                 <<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
        return context.threads()==1 && d.threads()==1 ? 0 : 2;
    }
    if(argc!=1) throw std::runtime_error("unexpected arguments");
    if(P!=104857601 && P!=69206017 && P!=67239937)
        throw std::runtime_error("unsupported oracle modulus");
    const uint64_t inverse=power((uint64_t(1)<<32)%P,P-2);
    if(((uint64_t(1)<<32)%P)*inverse%P!=1)
        throw std::runtime_error("oracle inverse failure");
    std::deque<Pending> pending;
    uint64_t edge=0,checked=0,canceled=0,holds=0,high_inputs=0;
    uint32_t held=0;
    auto tick=[&](bool reset,bool valid,uint32_t lhs,uint32_t rhs) {
        d.clk=0;d.rst_n=reset;d.in_valid=valid;d.lhs=lhs;d.rhs=rhs;d.eval();
        if(!reset) { canceled+=pending.size();pending.clear();held=0; }
        else if(d.result!=held) throw std::runtime_error("COMBINATIONAL_OUTPUT");
        if(reset && valid) {
            if(lhs>=2*P || rhs>=P) throw std::runtime_error("BAD_TEST_VECTOR");
            // Independent modular arithmetic, not RTL's positive-inverse REDC.
            const uint64_t canonical=uint64_t(lhs)*rhs%P;
            pending.push_back({edge+3,uint32_t(canonical*inverse%P)});
            high_inputs+=lhs>=(uint32_t(1)<<27);
        }
        d.clk=1;d.eval();
        bool due=!pending.empty() && pending.front().due==edge;
        if(bool(d.out_valid)!=due) throw std::runtime_error("VALID_LATENCY_MISMATCH");
        if(due) {
            if(d.result!=pending.front().expected || d.result>=P)
                throw std::runtime_error("MONT28_ARITHMETIC_MISMATCH edge="+std::to_string(edge));
            pending.pop_front();held=d.result;checked++;
        } else {
            if(d.result!=held) throw std::runtime_error("INVALID_OUTPUT_HOLD");
            holds++;
        }
        edge++;
    };
    tick(false,false,0,0);
    const std::vector<uint32_t> lhs_edges={0,1,P-1,P,P+1,(1u<<27)-1,1u<<27,2*P-1};
    const std::vector<uint32_t> rhs_edges={0,1,P-1,uint32_t((uint64_t(1)<<32)%P)};
    for(auto x:lhs_edges) for(auto y:rhs_edges) tick(true,true,x,y);
    std::mt19937 rng(0x28270001);
    for(unsigned i=0;i<20000;i++)
        tick(i%251!=250,i%7!=6,rng()%(2*P),rng()%P);
    // Abort every possible pipeline occupancy, then require a clean refill.
    for(unsigned occupancy=1;occupancy<=4;occupancy++) {
        tick(false,false,0,0);
        for(unsigned j=0;j<occupancy;j++) tick(true,true,2*P-1-j,P-1-j);
        tick(false,true,2*P-1,P-1);
        for(unsigned j=0;j<8;j++) tick(true,true,rng()%(2*P),rng()%P);
    }
    for(unsigned i=0;i<8;i++) tick(true,false,0,0);
    if(!pending.empty() || checked<10000 || high_inputs==0 || canceled==0)
        throw std::runtime_error("INCOMPLETE_COVERAGE");
    std::cout<<"PASS_MONT28 P="<<P<<" checked="<<checked<<" canceled="<<canceled
             <<" holds="<<holds<<" high_inputs="<<high_inputs<<" edges="<<edge<<"\n";
    d.final();return 0;
} catch(const std::exception& error) { std::cerr<<error.what()<<"\n";return 1; } }
