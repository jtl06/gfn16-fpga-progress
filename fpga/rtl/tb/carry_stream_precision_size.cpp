#include "Vgenefer_carry_prefix_stream_precision.h"
#include "verilated.h"
#include <iostream>
#include <stdexcept>
int main(int argc,char** argv){try{
    Verilated::commandArgs(argc,argv);Vgenefer_carry_prefix_stream_precision d;
    auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();};
    d.start=0;d.load_we=0;d.read_en=0;d.vector_load_we=0;d.vector_read_en=0;d.stream_valid=0;
    d.rst_n=0;tick();d.rst_n=1;tick();d.base=1000000000;
    for(unsigned lg:{0u,17u,18u,31u}){
        d.size_log2=lg;d.start=1;tick();
        if(!d.done||!d.error||d.busy||d.cycles||d.stream_ready)throw std::runtime_error("size rejection failed");
        d.start=0;tick();
    }
    d.base=9;d.size_log2=1;d.start=1;tick();d.start=0;
    for(unsigned i=0;!d.stream_ready&&i<100;i++)tick();
    if(!d.stream_ready)throw std::runtime_error("post-size stream readiness failed");
    for(unsigned j=0;j<12;j++)d.stream_data[j]=0;
    d.stream_valid=1;d.stream_addr=0;d.stream_mask=3;tick();d.stream_valid=0;
    for(unsigned i=0;!d.done&&i<100;i++)tick();
    if(!d.done||d.error||d.busy||d.cycles!=143)throw std::runtime_error("post-size valid run failed");
    for(unsigned i=0;i<2;i++){d.host_addr=i;d.read_en=1;tick();
        if(!d.read_valid||d.read_data[0]||d.read_data[1]||d.read_data[2])throw std::runtime_error("post-size data failed");}
    std::cout<<"PASS AW17 rejects sizes0,17,18,31 and accepts N2 after failures\n";
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
