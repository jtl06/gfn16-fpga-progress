#include "Vgenefer_anext_control_fault_probe_v1.h"
#include "verilated.h"
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
static void need(bool x,const char* m){if(!x)throw std::runtime_error(m);}
int main(int argc,char** argv){try{
    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
    Vgenefer_anext_control_fault_probe_v1 d{&context};
    if(argc==2 && std::string(argv[1])=="--runtime-probe"){
        std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
        return context.threads()==1 && d.threads()==1?0:2;
    }
    need(argc==2,"ANEXT_CONTROL_ARGUMENT");const std::string mode=argv[1];
    const bool reset_case=mode=="reset-word3" || mode=="reset-commit" || mode=="reset-check";
    const bool header=mode=="header0" || mode=="header3";
    const bool done=mode=="done0" || mode=="done1" || mode=="done2";
    const bool error=mode=="error0" || mode=="error1" || mode=="error2";
    need(reset_case || header || done || error,"ANEXT_CONTROL_CASE");
    d.clk=0;d.rst_n=0;d.cmd_valid=0;d.rsp_ready=0;d.sim_header_corrupt=0;d.sim_drop_done=0;d.sim_child_error=0;
    d.cmd_base=300;d.cmd_opcode=0;d.cmd_address=0;d.cmd_word=0;d.cmd_double=0;uint64_t ticks=0;
    auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();++ticks;};
    auto start=[&](unsigned op,unsigned addr,int32_t word){need(d.cmd_ready && !d.rsp_valid,"ANEXT_CONTROL_READY");d.cmd_opcode=op;d.cmd_address=addr;d.cmd_word=word;d.cmd_valid=1;tick();d.cmd_valid=0;};
    auto finish=[&](bool expect_error){unsigned wait=0;while(!d.rsp_valid && wait++<10000)tick();need(d.rsp_valid && bool(d.rsp_error)==expect_error,"ANEXT_CONTROL_RESPONSE");const int32_t word=int32_t(d.rsp_word);d.rsp_ready=1;tick();d.rsp_ready=0;return word;};
    auto load_one=[&](){start(0,0,0);finish(false);for(unsigned i=0;i<32;++i){start(1,i,i==0);finish(false);}};
    tick();d.rst_n=1;tick();load_one();start(5,0,0);
    unsigned waited=0;
    for(;waited<10000;++waited){
        const unsigned target=(done || error)?unsigned(mode.back()-'0'):0;
        const bool hit=header?(d.monitor_state==3 && d.monitor_word_valid && d.monitor_word==unsigned(mode.back()-'0')):
            mode=="reset-word3"?(d.monitor_state==3 && d.monitor_word_valid && d.monitor_word==3):
            mode=="reset-commit"?d.monitor_state==4:mode=="reset-check"?d.monitor_state==5:
            (d.monitor_state==7 && d.monitor_step==target && d.monitor_child_done==7);
        if(hit)break;need(!d.rsp_valid,"ANEXT_CONTROL_MISSED_SEAM");tick();
    }
    need(waited<10000,"ANEXT_CONTROL_TARGET_TIMEOUT");
    if(reset_case){d.rst_n=0;tick();d.rst_n=1;tick();need(!d.rsp_valid && !d.image_valid && !d.prefill_valid && !d.monitor_cache,"ANEXT_CONTROL_RESET_FLUSH");}
    else{
        d.sim_header_corrupt=header;d.sim_drop_done=done;d.sim_child_error=error;tick();
        need(d.monitor_seq_error,"ANEXT_CONTROL_FIELD_FAULT_NOT_PROPAGATED");
        finish(true);need(d.fault_sticky && !d.image_valid && !d.prefill_valid && !d.monitor_cache,"ANEXT_CONTROL_FAILED_IMAGE_ELIGIBLE");
        d.sim_header_corrupt=0;d.sim_drop_done=0;d.sim_child_error=0;
    }
    for(unsigned i=0;i<12;++i){tick();need(!d.monitor_ram_read && !d.monitor_ram_write && !d.rsp_valid,"ANEXT_CONTROL_STALE_CHILD_OR_RESPONSE");}
    // Reset and fully reload a new base; stale four-word cache must not survive.
    d.rst_n=0;tick();d.rst_n=1;tick();d.cmd_base=317;load_one();start(5,0,0);finish(false);
    need(d.image_valid && d.prefill_valid && d.profile_loads && !d.profile_hits && d.root_cycles==9 && d.ntt_cycles==114,"ANEXT_CONTROL_RELOAD_CALENDAR");
    for(unsigned i=0;i<32;++i){start(2,i,0);need(finish(false)==int32_t(i==0),"ANEXT_CONTROL_RECOVERY_VALUE");}
    need(context.threads()==1 && d.threads()==1,"ANEXT_CONTROL_THREADS");
    std::cout<<"ANEXT_CONTROL_PASS case="<<mode<<" injected=1 errors="<<(!reset_case)<<" recovered=1 words=32 quiet=12 ticks="<<ticks<<"\n";
    d.final();return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
