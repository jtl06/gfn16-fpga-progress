#include "Vgenefer_root_stream32.h"
#include "verilated.h"
#include <cstdint>
#include <iostream>
#include <stdexcept>

uint32_t power(uint32_t a,uint32_t e,uint32_t p) {
    uint64_t r=1,x=a;
    while(e) {if(e&1) r=r*x%p;x=x*x%p;e>>=1;}
    return uint32_t(r);
}
int main(int argc,char**argv) {
    try {
        if(argc!=4) throw std::runtime_error("prime generator log2N required");
        uint32_t p=std::stoul(argv[1]),g=std::stoul(argv[2]);
        unsigned lg=std::stoul(argv[3]),n=1u<<lg;
        uint32_t psi=power(g,(p-1)/(2*n),p),omega=uint64_t(psi)*psi%p;
        Vgenefer_root_stream32 d;
        auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();};
        auto reset=[&](){d.start=0;d.rst_n=0;tick();d.rst_n=1;tick();
            if(d.busy||d.done||d.root_valid) throw std::runtime_error("reset flags");};
        reset();
        unsigned checked=0;
        for(unsigned repeat=0;repeat<3;++repeat) for(unsigned phase=0;phase<4;++phase) {
            if(repeat==0) {
                d.phase=phase;d.start=1;tick();d.start=0;
                for(unsigned k=0;k<(n<11?n:11);++k) tick();
                reset(); // Abort, including partially occupied feedback pipeline.
            }
            d.phase=phase;d.start=1;tick();d.start=0;
            if(!d.busy||d.root_valid||d.done) throw std::runtime_error("start contract");
            uint32_t step=phase==0?psi:phase==1?omega:phase==2?power(omega,p-2,p):power(psi,p-2,p);
            uint32_t want=phase==3?power(n,p-2,p):uint64_t(1ull<<32)%p;
            for(unsigned i=0;i<n;++i) {
                d.phase=(phase+1)%4;d.start=1;tick(); // Busy input changes ignored.
                if(!d.root_valid||d.error||d.root_addr!=i||d.root_data!=want)
                    throw std::runtime_error("root mismatch i="+std::to_string(i));
                if(bool(d.done)!=(i==n-1)||bool(d.busy)!=(i!=n-1)) throw std::runtime_error("done cycle");
                want=uint64_t(want)*step%p;++checked;
            }
            d.start=0;
            if(repeat==0 || (repeat==2 && phase==3)) {
                tick();
                if(d.root_valid||d.done||d.busy) throw std::runtime_error("stale valid");
            }
            // Repeats1/2 immediately start the next phase after done, no reset
            // or idle bubble, exercising complete-to-complete pipeline draining.
        }
        d.final();std::cout<<"PASS N="<<n<<" checked="<<checked<<" cycles_per_table="<<n<<"\n";
    } catch(const std::exception&e) {std::cerr<<"FAIL "<<e.what()<<"\n";return 1;}
}
