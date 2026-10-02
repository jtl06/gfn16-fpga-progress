#include "Vgenefer_crt3_pipe.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <deque>
#include <fstream>
#include <iostream>
#include <stdexcept>

struct Due { uint64_t cycle; std::array<uint32_t,3> value; };
int main(int argc,char** argv) {
    try {
        Verilated::commandArgs(argc,argv);
        if(argc!=2) throw std::runtime_error("usage: crt_stream vectors.txt");
        std::ifstream f(argv[1]);
        if(!f) throw std::runtime_error("cannot open vectors");
        Vgenefer_crt3_pipe d;
        std::deque<Due> queue;
        std::array<uint32_t,3> held{0,0,0};
        uint64_t cycle=0,accepted=0,checked=0,canceled=0,resets=0;
        unsigned reset,valid; uint32_t a,b,c,l,m,h;
        while(f>>reset>>valid>>a>>b>>c>>l>>m>>h) {
            d.clk=0; d.eval();
            d.rst_n=reset; d.in_valid=valid; d.r1=a; d.r2=b; d.r3=c;
            d.eval();
            if(!reset) {
                canceled+=queue.size(); queue.clear(); held={0,0,0}; ++resets;
                if(d.out_valid) throw std::runtime_error("async reset valid mismatch");
            } else if(valid) {
                queue.push_back({cycle+60,{l,m,h}}); ++accepted;
            }
            d.clk=1; d.eval();
            bool expected=!queue.empty() && queue.front().cycle==cycle;
            if(bool(d.out_valid)!=expected)
                throw std::runtime_error("valid/latency mismatch cycle "+std::to_string(cycle));
            if(expected) { held=queue.front().value; queue.pop_front(); ++checked; }
            for(int j=0;j<3;++j) if(d.coefficient[j]!=held[j])
                throw std::runtime_error("value/hold mismatch cycle "+std::to_string(cycle)+" limb "+std::to_string(j));
            if(!d.ready) throw std::runtime_error("II=1 ready mismatch");
            ++cycle;
        }
        if(!f.eof() || !queue.empty() || checked<10000 || accepted!=checked+canceled)
            throw std::runtime_error("incomplete vectors or accounting mismatch");
        d.final();
        std::cout<<"PASS cycles="<<cycle<<" accepted="<<accepted<<" checked="<<checked
                 <<" canceled="<<canceled<<" reset_edges="<<resets<<" stages=61 II=1\n";
        return 0;
    } catch(const std::exception& e) { std::cerr<<e.what()<<"\n"; return 1; }
}
