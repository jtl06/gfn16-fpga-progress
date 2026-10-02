#include "Vgenefer_ntt_banked_modulemem_engine.h"
#include "verilated.h"
#include <fstream>
#include <algorithm>
#ifndef NTT_LANES
#define NTT_LANES 4
#endif
#include <iostream>
#include <stdexcept>
#include <string>

int main(int argc, char** argv) {
    try {
        if(argc!=3) throw std::runtime_error("command-file output-file required");
        std::ifstream in(argv[1]); std::ofstream out(argv[2]);
        if(!in || !out) throw std::runtime_error("file open failed");
        Vgenefer_ntt_banked_modulemem_engine d;
        const auto tick=[&]() {d.clk=0;d.eval();d.clk=1;d.eval();};
        const auto reset=[&]() {
            d.start=0;d.load_we=0;d.root_we=0;d.read_en=0;d.root_phase=0;d.rst_n=0;tick();
            if(d.busy || d.done || d.read_valid) throw std::runtime_error("reset flags");
            d.rst_n=1;tick();
        };
        reset();
        for(unsigned bad:{0u,17u,31u}) {
            d.size_log2=bad;d.start=1;tick();d.start=0;
            if(!d.done || !d.error || d.busy) throw std::runtime_error("invalid size accepted");
            tick();reset();
        }
        for(unsigned phase:{1u,2u}) {
            d.root_phase=phase;d.op=2;d.size_log2=1;d.start=1;tick();d.start=0;
            if(!d.done || !d.error || d.busy) throw std::runtime_error("half-table vector request accepted");
            tick();reset();
        }
        unsigned lg;if(!(in>>lg) || lg<1 || lg>16) throw std::runtime_error("bad size");
        unsigned n=1u<<lg;d.size_log2=lg;
        std::string cmd;unsigned runs=0,checks=0,resets=0,order=0,phase=0;
        while(in>>cmd) {
            if(cmd=="PHASE") {
                if(!(in>>phase) || phase>3) throw std::runtime_error("bad phase");
            } else if(cmd=="POISON_HALF") {
                d.root_phase=phase;d.root_we=1;d.write_data=0;
                for(unsigned i=n/2;i<n;++i) {d.host_addr=i;tick();}
                d.root_we=0;tick();
            } else if(cmd=="ORDER") {
                if(!(in>>order) || order>1) throw std::runtime_error("bad order");
            } else if(cmd=="LOAD" || cmd=="ROOTS" || cmd=="ROOTS_HALF") {
                for(unsigned i=0;i<(cmd=="ROOTS_HALF"?n/2:n);++i) {
                    uint32_t value;if(!(in>>value)) throw std::runtime_error("short load");
                    d.root_phase=phase;d.host_addr=i;d.write_data=value;d.load_we=cmd=="LOAD";d.root_we=cmd!="LOAD";
                    d.read_en=d.load_we;tick();
                    if(d.load_we && d.read_valid) throw std::runtime_error("write/read priority");
                    d.read_en=0;
                }
                d.load_we=0;d.root_we=0;tick();
            } else if(cmd=="RUN" || cmd=="ABORT" || cmd=="ABORT_AT") {
                unsigned op,inv,abort_at=13;uint32_t scale;
                if(!(in>>op>>inv>>scale) || op>3 || inv>1) throw std::runtime_error("bad run");
                if(cmd=="ABORT_AT" && !(in>>abort_at)) throw std::runtime_error("missing abort time");
                d.root_phase=phase;d.dif=order;d.op=op;d.inverse=inv;d.scale=scale;d.start=1;tick();d.start=0;
                unsigned ticks=0;
                while(!d.done) {
                    d.load_we=1;d.root_we=1;d.read_en=1;d.write_data=0;d.host_addr=ticks%n;
                    d.root_phase=(phase+1)%4;d.start=1;d.op=3;d.scale=0;d.inverse=!inv;d.dif=!order;d.size_log2=1;
                    tick();++ticks;
                    if(d.read_valid) throw std::runtime_error("busy host read accepted");
                    if(cmd!="RUN" && ticks==abort_at) {
                        reset();++resets;
                        for(unsigned j=0;j<12;++j) {tick();if(d.done || d.busy || d.read_valid) throw std::runtime_error("late reset result");}
                        break;
                    }
                    if(ticks>12ull*n*(lg+2)) throw std::runtime_error("NTT timeout");
                }
                d.start=0;d.load_we=0;d.root_we=0;d.read_en=0;d.size_log2=lg;
                if(cmd=="RUN") {
                    if(d.error || d.busy) throw std::runtime_error("NTT status");
                    if(d.cycles!=ticks) throw std::runtime_error("cycle counter mismatch");
                    uint64_t bf=op==0 ? uint64_t(n/2)*lg : 0;
                    uint64_t swaps=0;
                    uint64_t mul=(op!=0 || inv) ? n : 0;
                    uint64_t drain=(op==0?7*lg:0)+(mul?5:0);
                    uint64_t groups=(uint64_t(n)+2*NTT_LANES-1)/(2*NTT_LANES);
                    uint64_t expected_cycles=(op==0?groups*lg:0)+(mul?(n+NTT_LANES-1)/NTT_LANES:0)+drain;
                    uint64_t roots=0;
                    if(op==0) for(unsigned s=0;s<lg;++s) roots+=groups*std::min(unsigned(NTT_LANES),1u<<s);
                    if(op==2) roots=n;
                    if(d.cycles!=expected_cycles || d.butterflies!=bf ||
                       d.data_reads!=2*swaps+2*bf+mul || d.data_writes!=2*swaps+2*bf+mul ||
                       d.root_reads!=roots || d.wait_cycles!=drain)
                        throw std::runtime_error("operation accounting mismatch cycles="+std::to_string(d.cycles)+" expected="+std::to_string(expected_cycles)+" waits="+std::to_string(d.wait_cycles));
                    std::cout<<"RUN phase="<<phase<<" dif="<<order<<" op="<<op<<" inv="<<inv<<" n="<<n<<" cycles="<<d.cycles
                             <<" butterflies="<<d.butterflies<<" reads="<<d.data_reads
                             <<" writes="<<d.data_writes<<" roots="<<d.root_reads<<" waits="<<d.wait_cycles<<'\n';
                    ++runs;
                } else if(ticks!=abort_at) throw std::runtime_error("operation ended before reset injection");
                tick();if(d.done) throw std::runtime_error("done not a pulse");
            } else if(cmd=="CHECK" || cmd=="DUMP") {
                for(unsigned i=0;i<n;++i) {
                    d.host_addr=i;d.read_en=1;tick();
                    if(!d.read_valid) throw std::runtime_error("read valid missing");
                    if(cmd=="CHECK") {
                        uint32_t expected;if(!(in>>expected)) throw std::runtime_error("short check");
                        if(d.read_data!=expected) throw std::runtime_error("NTT mismatch index="+std::to_string(i)+" got="+std::to_string(d.read_data)+" expected="+std::to_string(expected));
                        ++checks;
                    } else out<<d.read_data<<'\n';
                }
                d.read_en=0;tick();if(d.read_valid) throw std::runtime_error("stale read valid");
            } else throw std::runtime_error("unknown command");
        }
        if(!in.eof() || runs==0 || checks==0) throw std::runtime_error("incomplete test");
        d.final();std::cout<<"PASS runs="<<runs<<" checks="<<checks<<" aborts="<<resets<<'\n';
        return 0;
    } catch(const std::exception& e) {std::cerr<<"FAIL: "<<e.what()<<'\n';return 1;}
}
