#include "Vsdp_ram27_residue_equivalence.h"
#include "verilated.h"
#include <cstdint>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>
#ifndef RAM_DEPTH
#define RAM_DEPTH 512
#endif
int main(int argc,char** argv) {
  try {
    Verilated::commandArgs(argc,argv); Vsdp_ram27_residue_equivalence d;
    constexpr unsigned n=RAM_DEPTH; std::vector<uint32_t> mem(n); std::mt19937 rng(20261001);
    auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();};
    d.rst_n=0;d.read_en=0;d.write_en=0;tick();d.rst_n=1;
    if(argc>1) {
      std::string mode=argv[1]; d.write_en=1;d.write_addr=0;d.write_data=1;
      if(mode=="high")d.write_data=0x80000001u;
      else if(mode=="bit27")d.write_data=0x08000001u;
      else if(mode=="collision"){d.read_en=1;d.read_addr=0;}
      else throw std::runtime_error("unknown negative mode");
      tick();throw std::runtime_error("missing RAM assertion");
    }
    for(unsigned i=0;i<n;++i){mem[i]=(i%3==0)?0x7ffffffu:rng()&0x7ffffffu;d.write_en=1;d.write_addr=i;d.write_data=mem[i];tick();}
    d.write_en=0;d.read_en=1;d.read_addr=0;tick();uint32_t expected=mem[0];
    for(unsigned i=0;i<100000;++i) {
      d.rst_n=i%103!=0;d.read_en=(rng()%4)!=0;d.write_en=(rng()%3)!=0;
      d.read_addr=rng()%n;d.write_addr=rng()%n;
      if(d.read_addr==d.write_addr)d.write_en=0;
      d.write_data=rng()&0x7ffffffu;
      // Writes while reset is asserted must not change memory, even for
      // noncanonical payloads: the RAM contract gates accesses on rst_n.
      if(!d.rst_n)d.write_data=0xffffffffu;
      if(d.rst_n && d.read_en)expected=mem[d.read_addr];
      if(d.rst_n && d.write_en)mem[d.write_addr]=d.write_data;
      tick();if(d.wide_q!=expected || d.narrow_q!=expected)
        throw std::runtime_error("RAM read/hold/reset/equivalence mismatch");
    }
    d.final();std::cout<<"PASS 100000 registered read/write/hold/reset equivalence checks depth="<<n<<"\n";
    return 0;
  } catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
