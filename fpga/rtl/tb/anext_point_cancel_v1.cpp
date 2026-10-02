#include "Vgenefer_anext_point_cancel_probe_v1.h"
#include "verilated.h"
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
static void need(bool value,const char* message){if(!value)throw std::runtime_error(message);}
int main(int argc,char** argv){try{
    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
    Vgenefer_anext_point_cancel_probe_v1 d{&context};
    if(argc==2 && std::string(argv[1])=="--runtime-probe"){
        std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
        return context.threads()==1 && d.threads()==1?0:2;
    }
    need(argc==2,"ANEXT_POINT_ARGUMENT");const std::string mode=argv[1];
    const bool reset=mode=="reset0" || mode=="reset1" || mode=="reset3";
    need(reset || mode=="cancel0" || mode=="cancel1" || mode=="cancel3","ANEXT_POINT_CASE");
    const unsigned age=unsigned(mode.back()-'0');uint64_t ticks=0;
    d.clk=0;d.rst_n=0;d.cmd_valid=0;d.rsp_ready=0;d.sim_cancel=0;
    d.cmd_base=300;d.cmd_opcode=0;d.cmd_address=0;d.cmd_word=0;d.cmd_double=0;
    auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();++ticks;};
    auto start=[&](unsigned op,unsigned addr,int32_t word){need(d.cmd_ready && !d.rsp_valid,"ANEXT_POINT_READY");d.cmd_opcode=op;d.cmd_address=addr;d.cmd_word=word;d.cmd_valid=1;tick();d.cmd_valid=0;};
    auto finish=[&](){unsigned waited=0;while(!d.rsp_valid && waited++<2000)tick();need(d.rsp_valid && !d.rsp_error,"ANEXT_POINT_RESPONSE");int32_t word=int32_t(d.rsp_word);d.rsp_ready=1;tick();d.rsp_ready=0;return word;};
    auto load=[&](){start(0,0,0);finish();for(unsigned i=0;i<32;++i){start(1,i,i==0?3:0);finish();}};
    tick();d.rst_n=1;tick();load();start(5,0,0);
    unsigned waited=0;while(d.monitor_point!=7 && waited++<2000){need(!d.rsp_valid,"ANEXT_POINT_MISSED_LAUNCH");tick();}
    need(d.monitor_point==7,"ANEXT_POINT_ALL_FIELDS_LAUNCH");
    for(unsigned i=0;i<age;++i){tick();need(!d.rsp_valid && !d.monitor_done,"ANEXT_POINT_EARLY_PUBLICATION");}
    if(reset)d.rst_n=0;else d.sim_cancel=1;
    tick();d.rst_n=1;d.sim_cancel=0;
    for(unsigned i=0;i<16;++i){tick();need(!d.monitor_point && !d.monitor_read && !d.monitor_write && !d.monitor_done && !d.monitor_image_write && !d.rsp_valid && !d.monitor_cache,"ANEXT_POINT_STALE_TAIL");}
    // Backend cancel is a simulation seam, not a public command. Reset and
    // complete reload is required before reusing the host image.
    d.rst_n=0;tick();d.rst_n=1;tick();d.cmd_base=317;load();start(5,0,0);finish();
    need(d.image_valid && d.prefill_valid && d.profile_loads && !d.profile_hits && d.root_cycles==9 && d.ntt_cycles==115,"ANEXT_POINT_RELOAD_CALENDAR");
    for(unsigned i=0;i<32;++i){start(2,i,0);need(finish()==int32_t(i==0?9:0),"ANEXT_POINT_RECOVERY_VALUE");}
    need(context.threads()==1 && d.threads()==1,"ANEXT_POINT_THREADS");
    std::cout<<"ANEXT_POINT_CANCEL_PASS case="<<mode<<" fields=3 captured=1 quiet=16 recovered=32 ntt=115 ticks="<<ticks<<"\n";
    d.final();return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
