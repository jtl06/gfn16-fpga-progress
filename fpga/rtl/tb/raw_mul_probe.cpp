#include "Vgenefer_raw_mul_probe.h"
#include "verilated.h"
#include <cstdint>
#include <deque>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
struct Row {uint64_t a,b; uint32_t lo,mid,hi;};
int main(int argc,char**argv){
  Verilated::commandArgs(argc,argv);
  try {
    if(argc==4 && std::string(argv[1])=="reject") {
      Vgenefer_raw_mul_probe d;d.clk=0;d.rst_n=0;d.in_valid=0;d.lhs=0;d.rhs=0;d.eval();
      d.clk=1;d.eval();d.clk=0;d.rst_n=1;d.in_valid=1;
      d.lhs=std::stoull(argv[2]);d.rhs=std::stoull(argv[3]);d.eval();d.clk=1;d.eval();
      throw std::runtime_error("raw input assertion missing");
    }
    if(argc!=2) throw std::runtime_error("vector path required");
    std::ifstream f(argv[1]); std::vector<Row> rows; Row r;
    while(f>>r.a>>r.b>>r.lo>>r.mid>>r.hi) rows.push_back(r);
    if(rows.empty()) throw std::runtime_error("empty vectors");
    Vgenefer_raw_mul_probe d; d.clk=0;d.rst_n=0;d.in_valid=0;d.lhs=0;d.rhs=0;
    auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();};
    tick(); d.rst_n=1;
    struct Due {uint64_t cycle; Row row;}; std::deque<Due> q;
    uint64_t cycle=0,accepted=0,checked=0,canceled=0,holds=0;
    uint32_t last[3]={0,0,0}; size_t next=0;
    // First pass guarantees every vector reaches an output. Second pass stresses
    // cancellation; delay its resets until the last first-pass result has drained.
    while(next<2*rows.size() || !q.empty()) {
      bool reset=(next>=rows.size()+2 && cycle%337==211);
      bool valid=!reset && next<2*rows.size() && (cycle%11!=3 && cycle%11!=4);
      d.rst_n=!reset; d.in_valid=valid;
      if(reset){canceled+=q.size();q.clear();last[0]=last[1]=last[2]=0;}
      if(valid){r=rows[next++%rows.size()];d.lhs=r.a;d.rhs=r.b;q.push_back({cycle+2,r});++accepted;}
      else {d.lhs=(1ULL<<36)-1;d.rhs=(1ULL<<36)-1;}
      tick(); bool expect=!q.empty() && q.front().cycle==cycle;
      if(bool(d.out_valid)!=expect) throw std::runtime_error("raw valid/latency mismatch");
      if(expect){
        Row x=q.front().row; q.pop_front();
        if(d.result[0]!=x.lo || d.result[1]!=x.mid || d.result[2]!=x.hi)
          throw std::runtime_error("raw multiplication mismatch");
        last[0]=x.lo;last[1]=x.mid;last[2]=x.hi;++checked;
      } else {
        if(d.result[0]!=last[0] || d.result[1]!=last[1] || d.result[2]!=last[2])
          throw std::runtime_error("raw invalid/reset hold mismatch");
        ++holds;
      }
      ++cycle;
    }
    if(accepted!=checked+canceled) throw std::runtime_error("raw accounting mismatch");
    std::cout<<"PASS accepted="<<accepted<<" checked="<<checked<<" canceled="<<canceled
             <<" invalid_hold="<<holds<<" latency=3_registered_stages II=1\n";
    return 0;
  }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}
}
