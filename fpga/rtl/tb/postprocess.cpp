#include "Vgenefer_postprocess_top.h"
#include "verilated.h"
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using I=__int128_t; using U=__uint128_t;
I parse(const std::string& s) {
    bool neg=!s.empty() && s[0]=='-'; U v=0;
    for(size_t i=neg;i<s.size();++i) {if(s[i]<'0'||s[i]>'9') throw std::runtime_error("bad integer"); v=v*10+(s[i]-'0');}
    return neg?-I(v):I(v);
}
template<class T> I get(const T& a) {U v=U(a[0])|(U(a[1])<<32)|(U(a[2])<<64); return (a[2]&0x80000000u)?I(v)-I(U(1)<<96):I(v);}
template<class T> void put(T& a,I v) {U x=U(v); for(unsigned i=0;i<3;++i) a[i]=uint32_t(x>>(i*32));}
int main(int argc,char**argv) {
    try {
        if(argc!=2) throw std::runtime_error("input required"); std::ifstream in(argv[1]);
        if(!in) throw std::runtime_error("input open");
        Vgenefer_postprocess_top d;
        auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();};
        d.rst_n=0;tick();d.rst_n=1;tick();
        d.size_log2=1;d.base=0;d.start=1;tick();d.start=0;
        if(!d.done || !d.error || d.busy) throw std::runtime_error("invalid radix accepted");
        tick();d.rst_n=0;tick();d.rst_n=1;tick();
        d.r1=1;d.r2=2;d.r3=3;d.crt_valid=1;tick();d.crt_valid=0;tick();
        d.rst_n=0;tick();d.rst_n=1;
        for(unsigned k=0;k<8;++k) {tick();if(d.coefficient_valid || !d.crt_ready) throw std::runtime_error("CRT reset cancellation");}
        unsigned lg,base,bit; if(!(in>>lg>>base>>bit)||lg<1||lg>16||bit>1) throw std::runtime_error("bad header");
        unsigned n=1u<<lg;d.size_log2=lg;d.base=base;
        std::vector<I> loaded; uint64_t crt_cycles_total=0;
        for(unsigned i=0;i<n;++i) {
            uint32_t a,b,c; std::string expected;
            if(!(in>>a>>b>>c>>expected)) throw std::runtime_error("short CRT input");
            if(!d.crt_ready) throw std::runtime_error("CRT not ready");
            d.r1=a;d.r2=b;d.r3=c;d.crt_valid=1;tick();d.crt_valid=0;
            unsigned t=0;while(!d.coefficient_valid) {
                // Busy inputs, including spurious valid, must not change the accepted transaction.
                d.r1=0;d.r2=0;d.r3=0;d.crt_valid=1;
                tick();if(++t>64) throw std::runtime_error("CRT timeout");
            }
            d.crt_valid=0;
            if(t!=58 || !d.crt_ready) throw std::runtime_error("CRT latency/ready mismatch");
            crt_cycles_total+=t+1;
            if(get(d.coefficient)!=parse(expected)) throw std::runtime_error("CRT mismatch index="+std::to_string(i));
            loaded.push_back(get(d.coefficient)*(bit?2:1));
            d.host_addr=i;put(d.write_data,loaded.back());d.load_we=1;d.read_en=1;tick();
            if(d.read_valid) throw std::runtime_error("carry write/read priority");
            d.load_we=0;d.read_en=0;
        }
        // Abort a partially completed carry sweep, then reload all coefficients.
        d.start=1;tick();d.start=0;tick();tick();tick();d.rst_n=0;tick();d.rst_n=1;
        for(unsigned k=0;k<8;++k) {tick();if(d.busy || d.done) throw std::runtime_error("carry reset cancellation");}
        for(unsigned i=0;i<n;++i) {d.host_addr=i;put(d.write_data,loaded[i]);d.load_we=1;tick();}
        d.load_we=0;
        d.start=1;tick();d.start=0;unsigned ticks=0;
        while(!d.done) {
            d.load_we=1;d.start=1;d.base=0;d.host_addr=0;put(d.write_data,0);tick();++ticks;
            // 64 sweeps, each bounded by READ + DIV_START + 24 divide + SIGN + APPLY.
            if(ticks>1800ull*n+256) throw std::runtime_error("carry timeout");
        }
        d.load_we=0;d.start=0;
        if(d.error || d.busy || d.cycles!=ticks) throw std::runtime_error("carry status/cycles");
        auto cycles=d.cycles;auto passes=d.passes;
        tick();if(d.done) throw std::runtime_error("stale done");
        for(unsigned i=0;i<n;++i) {
            std::string expected;if(!(in>>expected)) throw std::runtime_error("short digits");
            d.read_en=1;d.host_addr=i;tick();
            if(!d.read_valid || get(d.read_data)!=parse(expected)) throw std::runtime_error("carry mismatch index="+std::to_string(i));
        }
        std::string extra;if(in>>extra) throw std::runtime_error("extra data");
        d.read_en=0;tick();if(d.read_valid) throw std::runtime_error("stale read");
        d.final();std::cout<<"PASS n="<<n<<" bit="<<bit<<" crt_cycles="<<crt_cycles_total<<" carry_cycles="<<cycles<<" passes="<<unsigned(passes)<<'\n';return 0;
    } catch(const std::exception&e) {std::cerr<<"FAIL: "<<e.what()<<'\n';return 1;}
}
