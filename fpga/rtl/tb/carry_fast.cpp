#include <cstdint>
#include <fstream>
#include <iostream>
#include <string>
#include <stdexcept>
#include <vector>
#include "verilated.h"
#ifdef BASELINE
#include "Vgenefer_carry.h"
using DUT=Vgenefer_carry;
#else
#include "Vgenefer_carry_fast.h"
using DUT=Vgenefer_carry_fast;
#endif
using I=__int128_t;
static I parse(const std::string &s) {
    I x=0; size_t i=s[0]=='-' ? 1:0;
    for(;i<s.size();i++) x=x*10+(s[i]-'0');
    return s[0]=='-' ? -x:x;
}
template<class T> static void put(T &a,I x) {
    for(unsigned j=0;j<3;j++) a[j]=uint32_t(__uint128_t(x)>>(j*32));
}
template<class T> static I get(const T &a) {
    __uint128_t x=__uint128_t(a[0])|(__uint128_t(a[1])<<32)|(__uint128_t(a[2])<<64);
    return a[2]&0x80000000u ? I(x)- (I(1)<<96):I(x);
}
int main(int argc,char **argv) {
    Verilated::commandArgs(argc,argv);
    if(argc!=2 && argc!=3) return 2;
    bool chained=argc==3 && std::string(argv[2])=="--chain";
    if(argc==3 && !chained)return 2;
    std::ifstream f(argv[1]); DUT d;
    auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();};
    auto reset=[&](){d.rst_n=0;d.start=0;d.load_we=0;d.read_en=0;tick();d.rst_n=1;tick();
        if(d.busy||d.done||d.error||d.read_valid) throw std::runtime_error("reset mismatch");};
    reset(); unsigned cases=0,runs=0; std::string label;
    try {
        // Invalid commands terminate without setting busy.
        for(unsigned b:{0u,1u,1000000001u}) {
            d.base=b;d.size_log2=1;d.start=1;tick();
            if(!d.done||!d.error||d.busy) throw std::runtime_error("invalid base mismatch");
            d.start=0;tick();
        }
        while(f>>label) {
            unsigned lg,base; f>>lg>>base; unsigned n=1u<<lg; std::string s;
            if(!chained)reset();d.base=base;d.size_log2=lg;
            for(unsigned i=0;i<n;i++){
                f>>s;d.host_addr=i;put(d.write_data,parse(s));d.load_we=1;d.read_en=1;tick();
                if(d.read_valid)throw std::runtime_error("write/read priority mismatch");
            }
            std::vector<I> expected(n);
            for(unsigned i=0;i<n;i++){f>>s;expected[i]=parse(s);}
            for(unsigned repeat=0;repeat<(chained?3u:1u);repeat++) {
            d.load_we=0;d.read_en=0;d.start=1;tick();d.start=0;
            uint64_t elapsed=0;
            while(!d.done && elapsed<50000000){
                d.start=1;d.base=0;d.host_addr=0;d.load_we=1;d.read_en=1;put(d.write_data,0);
                tick();elapsed++;
                if(d.read_valid)throw std::runtime_error("busy read mismatch");
            }
            d.start=0;d.load_we=0;d.read_en=0;d.base=base;
            if(!d.done||d.error||d.busy||d.cycles!=elapsed) throw std::runtime_error("completion mismatch "+label);
            std::cout<<label<<" repeat="<<repeat<<" cycles="<<d.cycles<<" passes="<<unsigned(d.passes)<<"\n";
            for(unsigned i=0;i<n;i++){
                d.host_addr=i;d.read_en=1;tick();
                if(!d.read_valid||get(d.read_data)!=expected[i])
                    throw std::runtime_error("carry mismatch "+label+" index="+std::to_string(i));
            }
            d.read_en=0;tick();if(d.read_valid||d.done) throw std::runtime_error("valid pulse mismatch");
            runs++;
            }
            // Abort during reciprocal setup, then reset must make interface idle.
            if(!chained) {
                d.start=1;tick();d.start=0;for(unsigned k=0;k<5;k++)tick();reset();
                if(lg>=8){d.start=1;tick();d.start=0;for(unsigned k=0;k<110;k++)tick();reset();}
            }
            cases++;
        }
        std::cout<<"PASS "<<cases<<" carry cases runs="<<runs<<" chained="<<chained<<"\n";
    } catch(const std::exception &e){std::cerr<<e.what()<<"\n";return 1;}
    return 0;
}
