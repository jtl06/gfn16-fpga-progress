#include "Vgenefer_carry_prefix_wide_pipe.h"
#include "verilated.h"
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#ifndef TEST_LANES
#define TEST_LANES 4
#endif
using I=__int128_t;
static I parse(const std::string& s){I x=0;size_t i=s[0]=='-'?1:0;for(;i<s.size();i++)x=x*10+s[i]-'0';return s[0]=='-'?-x:x;}
template<class T>static void put(T& a,I x){for(unsigned j=0;j<3;j++)a[j]=uint32_t(__uint128_t(x)>>(32*j));}
template<class T>static I get(const T& a){__uint128_t x=__uint128_t(a[0])|(__uint128_t(a[1])<<32)|(__uint128_t(a[2])<<64);return a[2]&0x80000000u?I(x)-(I(1)<<96):I(x);}
int main(int argc,char** argv){
    try{
        Verilated::commandArgs(argc,argv);if(argc!=2)throw std::runtime_error("vectors required");
        std::ifstream f(argv[1]);if(!f)throw std::runtime_error("input open");
        Vgenefer_carry_prefix_wide_pipe d;
        auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();};
        auto idle=[&](){d.start=0;d.load_we=0;d.read_en=0;};
        auto reset=[&](){idle();d.rst_n=0;tick();d.rst_n=1;tick();if(d.busy||d.done||d.error||d.read_valid)throw std::runtime_error("reset mismatch");};
        reset();std::string mode,label,s;unsigned cases=0,runs=0,rejects=0,aborts=0;
        while(f>>mode>>label){
            unsigned lg,b;f>>lg>>b;unsigned n=1u<<lg;d.base=b;d.size_log2=lg;
            std::vector<I> a(n),expected(n);for(auto& x:a){f>>s;x=parse(s);}
            if(mode=="OK")for(auto& x:expected){f>>s;x=parse(s);}
            else if(mode!="BAD"&&mode!="ABORT")throw std::runtime_error("bad mode");
            // No reset between completed cases: also changes radix and N.
            for(unsigned i=0;i<n;i++){d.host_addr=i;put(d.write_data,a[i]);d.load_we=1;d.read_en=1;tick();if(d.read_valid)throw std::runtime_error("write/read priority");}
            idle();
            for(unsigned rep=0;rep<(mode=="OK"?3u:1u);rep++){
                d.base=b;d.start=1;tick();d.start=0;uint64_t elapsed=0;unsigned emit_ticks=0;
                while(!d.done&&elapsed<2*((n+TEST_LANES-1)/TEST_LANES)+150){
                    d.start=1;d.load_we=1;d.read_en=1;d.base=0;d.host_addr=0;put(d.write_data,0);
                    tick();elapsed++;if(d.read_valid)throw std::runtime_error("busy read leaked");
                    if(mode=="ABORT" && (label=="drain" ? elapsed>=2*((n+TEST_LANES-1)/TEST_LANES)+117 :
         label.rfind("emit",0)==0 ? d.passes==2 && ++emit_ticks>=(label=="emit"?3u:unsigned(std::stoul(label.substr(4)))) : elapsed>=std::stoul(label))){reset();aborts++;break;}
                }
                idle();d.base=b;
                if(mode=="ABORT")break;
                if(!d.done||d.busy||d.cycles!=elapsed)throw std::runtime_error("completion mismatch "+label);
                if(mode=="BAD"){
                    if(!d.error)throw std::runtime_error("domain rejection missing "+label);
                    rejects++;tick();break;
                }
                if(d.error||d.passes!=2)throw std::runtime_error("unexpected error "+label);
                if(d.cycles!=2*((n+TEST_LANES-1)/TEST_LANES)+118)throw std::runtime_error("carry cycle regression");
                std::cout<<label<<" repeat="<<rep<<" cycles="<<d.cycles<<"\n";
                for(unsigned i=0;i<n;i++){
                    d.host_addr=i;d.read_en=1;tick();
                    if(!d.read_valid||get(d.read_data)!=expected[i])throw std::runtime_error("carry mismatch "+label+" index="+std::to_string(i));
                }
                // Last read directly precedes the next start or next reload.
                idle();runs++;
            }
            cases++;
        }
        if(!f.eof()||!runs)throw std::runtime_error("incomplete vectors");
        std::cout<<"PASS cases="<<cases<<" completed="<<runs<<" rejected="<<rejects<<" aborted="<<aborts<<"\n";
    }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
