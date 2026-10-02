#include "Vgenefer_sdp_ram32.h"
#include "verilated.h"
#include <cstdint>
#include <iostream>
#include <random>
#include <stdexcept>
#include <vector>
int main(int argc,char** argv) {
  try {
    Verilated::commandArgs(argc,argv); Vgenefer_sdp_ram32 d;
    constexpr unsigned n=8192; std::vector<uint32_t> mem(n); std::mt19937 rng(20260929);
    auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();};
    d.rst_n=0;d.read_en=0;d.write_en=0;tick();d.rst_n=1;
    for(unsigned i=0;i<n;++i){mem[i]=rng();d.write_en=1;d.write_addr=i;d.write_data=mem[i];tick();}
    d.write_en=0;d.read_en=1;d.read_addr=0;tick();uint32_t expected=mem[0];
    for(unsigned i=0;i<100000;++i) {
      d.rst_n=i%103!=0;d.read_en=(rng()%4)!=0;d.write_en=(rng()%3)!=0;
      d.read_addr=rng()%n;d.write_addr=rng()%n;
      if(d.read_addr==d.write_addr)d.write_en=0;
      d.write_data=rng();
      if(d.rst_n && d.read_en)expected=mem[d.read_addr];
      if(d.rst_n && d.write_en)mem[d.write_addr]=d.write_data;
      tick();if(d.read_data!=expected)throw std::runtime_error("RAM read/hold/reset mismatch");
    }
    d.final();std::cout<<"PASS 100000 registered read/write/hold/reset checks\n";
    return 0;
  } catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
