#include "Vgenefer_square_core27_stream.h"
#include "verilated.h"
#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using I=__int128_t;
template<class T> static I signed96(const T& a) {
    __uint128_t x=__uint128_t(a[0])|(__uint128_t(a[1])<<32)|(__uint128_t(a[2])<<64);
    return a[2]&0x80000000u ? I(x)-(I(1)<<96) : I(x);
}
int main(int argc,char** argv) {
    try {
        Verilated::commandArgs(argc,argv);
        if(argc<2 || argc>3) throw std::runtime_error("usage: square_core vectors [cache]");
        const bool cached=argc==3 && std::string(argv[2])=="cache";
        std::ifstream f(argv[1]); if(!f) throw std::runtime_error("missing vectors");
        unsigned n; f>>n;
        Vgenefer_square_core27_stream d;
        auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();};
        auto idle=[&](){d.start=0;d.load_we=0;d.read_en=0;};
        auto reset=[&](){idle();d.rst_n=0;tick();d.rst_n=1;tick();
            if(d.busy||d.done||d.error||d.read_valid) throw std::runtime_error("reset mismatch");
            if(d.root_cache_valid)throw std::runtime_error("cache reset mismatch");};
        reset();
        std::string cmd,label; unsigned base=2,cases=0,aborts=0,readbacks=0,fault_errors=0;
        while(f>>cmd) {
            if(cmd=="LOAD" || cmd=="LOAD_KEEP") {
                f>>label>>base; if(cmd=="LOAD")reset(); d.base=base;
                for(unsigned i=0;i<n;++i) {
                    int64_t value;f>>value;
                    d.host_addr=i;d.write_data=uint32_t(value);d.load_we=1;d.read_en=1;tick();
                    if(d.read_valid) throw std::runtime_error("load/read priority mismatch");
                }
                idle();tick();
            } else if(cmd=="RUN" || cmd=="RUN_NOREAD" || cmd=="ABORT") {
                unsigned bit;f>>label>>bit;
                const bool verify=cmd=="RUN";
                std::vector<int64_t> expected;
                if(cmd!="ABORT") { expected.resize(n);for(auto& value:expected)f>>value; }
                const unsigned cache_before=d.root_cache_valid;
                d.base=base;d.double_bit=bit;d.start=1;
                d.load_we=1;d.read_en=1;d.host_addr=n-1;d.write_data=0xffffffffu;
                tick();d.start=0;
                if(!d.busy||d.done||d.error) throw std::runtime_error("start mismatch "+label);
                uint64_t elapsed=0;
                // Keep the broad full-size cap, but reject tiny-N deadlocks
                // without simulating fifty million clocks in a fault model.
                const uint64_t cycle_limit=std::min<uint64_t>(50000000,
                    std::max<uint64_t>(10000,uint64_t(n)*2048));
                while(!d.done && elapsed<cycle_limit) {
                    // All host requests and latched input mutations must be ignored while busy.
                    d.start=elapsed&1;d.load_we=1;d.read_en=1;d.host_addr=elapsed%n;d.write_data=123;
                    d.base=0;d.double_bit=!bit;tick();++elapsed;
                    if(d.read_valid)throw std::runtime_error("busy host read leaked "+label);
                    if(cmd=="ABORT") {
                        if(label=="convert-m1" || label=="convert-0" || label=="convert-p1") {
                            // Fixed atomic27 conversion: ceil(N/16)+9 clocks.
                            // Abort one edge before/on/after the final counted
                            // write that simultaneously starts streaming carry.
                            const unsigned commit=(n+15)/16+9;
                            const unsigned target=label=="convert-m1" ? commit-1 :
                                label=="convert-p1" ? commit+1 : commit;
                            if(elapsed>=target)break;
                            continue;
                        }
                        if(label=="crt-active") {
                            // This case is generated only at N32: cold roots
                            // alone cover the97-clock carry setup. With the
                            // frozen61-stage CRT, first coefficient acceptance
                            // is RESIDUES clock63; reset then cancels a live
                            // divider row before the remaining groups finish.
                            if(n<32)throw std::runtime_error("crt-active requires N>=32");
                            if(d.crt_cycles>=63)break;
                            continue;
                        }
                        if(label.size()==5 && label.substr(0,4)=="root") {
                            const unsigned phase=unsigned(label[4]-'0');
                            if(d.root_phases_loaded==phase && d.root_cycles>uint64_t(phase)*(n+2)+2)break;
                            continue;
                        }
                        uint64_t phase=label=="conversion"?d.conversion_cycles:label=="root"?d.root_cycles:
                            label=="ntt"?d.ntt_cycles:label=="crt"?d.crt_cycles:d.carry_cycles;
                        if(phase>=3)break;
                    }
                }
                idle();d.base=base;
                if(cmd=="ABORT") { reset();++aborts;continue; }
                if(!d.done||d.error||d.busy||d.cycles!=elapsed)
                    throw std::runtime_error("completion mismatch "+label+" cycles="+std::to_string(elapsed));
                if(d.cycles!=d.conversion_cycles+d.root_cycles+d.ntt_cycles+d.crt_cycles+d.carry_cycles)
                    throw std::runtime_error("phase cycle accounting mismatch");
                const unsigned expected_loads=cached && cache_before==15 ? 0 : 4;
                const unsigned expected_hits=cached && cache_before==15 ? 4 : 0;
                if(d.root_phases_loaded!=expected_loads || d.root_cache_hits!=expected_hits ||
                   d.root_cycles!=uint64_t(expected_loads)*(n+2) ||
                   d.root_cache_valid!=(cached?15:0))
                    throw std::runtime_error("cache contract mismatch "+label);
                // The fixed61-stage CRT and97-clock carry setup require an
                // explicit45-clock reservation wait after a52-clock warm N2 NTT.
                if(n==2 && cache_before==15 && d.crt_cycles!=108)
                    throw std::runtime_error("backpressure reservation mismatch");
                std::cout<<label<<" cycles="<<d.cycles<<" conversion="<<d.conversion_cycles
                    <<" roots="<<d.root_cycles<<" ntt="<<d.ntt_cycles<<" crt="<<d.crt_cycles
                    <<" carry="<<d.carry_cycles<<" passes="<<unsigned(d.carry_passes)<<" base="<<base
                    <<" cache_before="<<cache_before<<" root_loads="<<unsigned(d.root_phases_loaded)
                    <<" root_hits="<<unsigned(d.root_cache_hits)<<" readback="<<verify<<"\n";
                if(verify)for(unsigned i=0;i<n;++i) {
                    d.host_addr=i;d.read_en=1;tick();
                    if(!d.read_valid||signed96(d.read_data)!=I(expected[i]))
                        throw std::runtime_error("square mismatch "+label+" index="+std::to_string(i)+
                            " got_low="+std::to_string(d.read_data[0])+" expected="+std::to_string(expected[i]));
                }
                // Next start may immediately follow the final read edge, with
                // no extra idle clock to hide a stale carry-RAM read_valid.
                // NOREAD leaves done high here; the next start is accepted on
                // the very next edge, which must also clear the old done pulse.
                idle();if(verify && d.done)throw std::runtime_error("done pulse mismatch");
                if(verify)++readbacks;
                ++cases;
            } else if(cmd=="ERROR_RUN") {
                // Used only with a separate, explicitly fault-injected child
                // stream mask; production arithmetic vectors never use this.
                unsigned bit;f>>label>>bit;idle();d.base=base;d.double_bit=bit;d.start=1;tick();d.start=0;
                unsigned elapsed=0;while(!d.done && elapsed<10000){tick();++elapsed;}
                if(!d.done||!d.error||d.busy||d.root_cache_valid)
                    throw std::runtime_error("injected child error not reported");
                for(unsigned k=0;k<4;++k){
                    d.start=1;d.read_en=1;d.load_we=1;d.write_data=0;tick();
                    if(!d.error||d.done||d.busy||d.read_valid||d.root_cache_valid)
                        throw std::runtime_error("stream error quarantine mismatch");
                }
                ++fault_errors;reset();
            } else if(cmd=="BADBASE") {
                unsigned bad;f>>bad;reset();d.base=bad;d.start=1;tick();
                if(!d.error||!d.done||d.busy)throw std::runtime_error("invalid base accepted");
                reset();
            } else if(cmd=="BADDIGIT" || cmd=="BADDIGIT_AT") {
                unsigned valid_base;int64_t bad;f>>valid_base>>bad;reset();d.base=valid_base;
                unsigned bad_at=n/2;if(cmd=="BADDIGIT_AT")f>>bad_at;
                for(unsigned i=0;i<n;++i) {
                    d.host_addr=i;d.write_data=uint32_t(i==bad_at?bad:0);d.load_we=1;tick();
                }
                idle();d.start=1;tick();d.start=0;
                unsigned elapsed=0;while(!d.done && elapsed<n+20){tick();++elapsed;}
                if(!d.done||!d.error||d.busy)throw std::runtime_error("invalid digit accepted");
                d.start=1;d.read_en=1;tick();
                if(!d.error||d.busy||d.done||d.read_valid)throw std::runtime_error("error quarantine mismatch");
                reset();
            } else throw std::runtime_error("unknown command "+cmd);
        }
        if(!f.eof()||(!cases&&!fault_errors))throw std::runtime_error("incomplete input");
        idle();tick();if(d.read_valid||d.done)throw std::runtime_error("valid pulse mismatch");
        std::cout<<"PASS n="<<n<<" squares="<<cases<<" readbacks="<<readbacks<<" aborts="<<aborts<<"\n";
        if(fault_errors)std::cout<<"PASS fault_errors="<<fault_errors<<"\n";
        d.final();return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
