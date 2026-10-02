#include "Vtrack_a4_canonical_controller_probe_v1.h"
#include "verilated.h"
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#ifndef A4_CANON_AW
#error A4_CANON_AW must match -GAW
#endif
static_assert(A4_CANON_AW==5 || A4_CANON_AW==8,"small-N canonical controller");
static void need(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
int main(int argc,char** argv){
    try{
        VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
        Vtrack_a4_canonical_controller_probe_v1 d{&context};
        if(argc==2 && std::string(argv[1])=="--runtime-probe"){
            std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
            return context.threads()==1 && d.threads()==1?0:2;
        }
        need(argc==2,"usage: a4_canon vectors | --runtime-probe");
        std::ifstream input(argv[1]);need(bool(input),"A4_CANON_OPEN");
        std::string magic;unsigned aw,count;need(bool(input>>magic>>aw>>count),"A4_CANON_HEADER");
        need(magic=="A4CANON1" && aw==A4_CANON_AW && count>0 && count<1000,"A4_CANON_PROFILE");
        const unsigned n=1u<<aw;uint64_t normals=0,errors=0,resets=0,words=0;
        auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();};
        for(unsigned test=0;test<count;++test){
            uint64_t base;unsigned mode,age,code,clocks,passes,special,maximum;
            need(bool(input>>base>>mode>>age>>code>>clocks>>passes>>special>>maximum),"A4_CANON_CASE");
            need(base<=0xffffffffu && mode<=7 && clocks<100000 && special<=1,"A4_CANON_CASE_RANGE");
            std::vector<uint32_t> values(n),expected(n);
            for(auto& value:values){uint64_t x;need(bool(input>>x)&&x<=0xffffffffu,"A4_CANON_INPUT");value=uint32_t(x);}
            for(auto& value:expected){uint64_t x;need(bool(input>>x)&&x<=0xffffffffu,"A4_CANON_EXPECTED");value=uint32_t(x);}
            d.rst_n=0;d.cancel=0;d.begin_canonical=0;d.load_we=0;d.read_en=0;
            d.inject_drop=0;d.inject_tag=0;d.inject_generation=0;d.inject_mem_error=0;tick();
            d.rst_n=1;d.base=uint32_t(base);d.generation=test+1;
            d.load_we=1;
            for(unsigned i=0;i<n;++i){d.host_address=i;d.host_write_data=values[i];tick();}
            d.load_we=0;d.begin_canonical=1;tick();d.begin_canonical=0;
            bool stopped=false;
            if(mode==6){need(d.error && d.error_code==code,"A4_CANON_BAD_BASE");stopped=true;++errors;}
            for(unsigned cycle=1;cycle<=clocks+2 && !stopped;++cycle){
                const bool inject=cycle==age;
                d.inject_drop=mode==1 && inject;d.inject_tag=mode==2 && inject;
                d.inject_generation=mode==3 && inject;d.inject_mem_error=mode==4 && inject;
                d.rst_n=!(mode==5 && inject);tick();
                const auto at=" case="+std::to_string(test)+" cycle="+std::to_string(cycle);
                if(mode==5){need(!d.done && !d.error,"A4_CANON_RESET_LEAK"+at);if(cycle==clocks+2){++resets;stopped=true;}}
                else if(mode!=0){
                    if(d.error){need(d.error_code==code && !d.done,"A4_CANON_FAULT_CODE"+at);++errors;stopped=true;}
                    else need(!d.done,"A4_CANON_FAULT_MISSED"+at);
                }else{
                    need(!d.error,"A4_CANON_UNEXPECTED_ERROR"+at);
                    if(d.done){
                        need(cycle==clocks && d.passes==passes && d.minus_one==special && d.max_digit==maximum
                            && d.tail_checked && d.out_generation==test+1,"A4_CANON_LATENCY_OR_SUMMARY"+at);
                        ++normals;stopped=true;
                    }
                }
            }
            need(stopped,"A4_CANON_TIMEOUT case="+std::to_string(test));
            d.inject_drop=0;d.inject_tag=0;d.inject_generation=0;d.inject_mem_error=0;d.rst_n=1;
            if(mode==0){
                d.read_en=1;
                for(unsigned i=0;i<n;++i){d.host_address=i;tick();need(d.host_read_valid && uint32_t(d.host_read_data)==(special?0u:expected[i]),"A4_CANON_RAM_READBACK");++words;}
                d.read_en=0;
            }
        }
        std::string trailing;need(!(input>>trailing),"A4_CANON_TRAILING");
        need(context.threads()==1 && d.threads()==1,"A4_CANON_THREAD_DRIFT");
        std::cout<<"A4_CANON_CONTROLLER_PASS aw="<<aw<<" cases="<<count<<" normal="<<normals<<" errors="<<errors<<" resets="<<resets<<" words="<<words<<"\n";
        d.final();return 0;
    }catch(const std::exception& ex){std::cerr<<ex.what()<<"\n";return 1;}
}
