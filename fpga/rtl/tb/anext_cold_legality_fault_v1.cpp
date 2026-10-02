#include "Vgenefer_anext_coldleg_fault_probe_v1.h"
#include "verilated.h"
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#ifndef COLDLEG_AW
#error "COLDLEG_AW must be supplied by the source-bound role"
#endif
static constexpr unsigned AW=COLDLEG_AW,N=1u<<AW,T=N/16;
static_assert(AW==5 || AW==8,"bounded native geometry");
static void need(bool value,const char* message){if(!value)throw std::runtime_error(message);}
int main(int argc,char** argv){try{
    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
    Vgenefer_anext_coldleg_fault_probe_v1 d{&context};
    if(argc==2 && std::string(argv[1])=="--runtime-probe"){
        std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
        return context.threads()==1 && d.threads()==1?0:2;
    }
    need(argc==2,"COLDLEG_ARGUMENT");std::string mode=argv[1];
    const bool negative=mode=="negative-edge";if(negative)mode="numeric-first";
    const bool cancelled=mode.rfind("cancel-",0)==0;
    const bool delayed=mode=="numeric-first" || mode=="numeric-final" || mode=="upper33-final" || mode=="cancel-after-source";
    need(mode=="numeric-first" || mode=="numeric-final" || mode=="upper33-final" || mode=="double-meta" ||
        mode=="double-image" || mode=="double-transfer" || mode=="cancel-on-response" || mode=="cancel-after-source" ||
        mode=="cancel-pending","COLDLEG_CASE");
    uint64_t ticks=0;bool observation=false,bad_active=false;unsigned bad_reducer=0,bad_RAM=0;
    d.clk=0;d.rst_n=0;d.cmd_valid=0;d.rsp_ready=0;d.sim_cancel=0;d.sim_fault_mode=0;
    d.sim_fault_offset=mode=="numeric-first"?0:T-1;d.sim_fault_lane=15;d.sim_fault_word=1000;
    d.cmd_base=1000;d.cmd_opcode=0;d.cmd_address=0;d.cmd_word=0;d.cmd_double=0;
    auto eval=[&](){d.clk=0;d.eval();};
    auto tick=[&](){eval();
        if(observation){
            need(!d.monitor_start && !d.monitor_prefill_done && !d.monitor_cache && !d.image_valid && !d.prefill_valid,"COLDLEG_FAILED_PUBLICATION");
            if(bad_active){bad_reducer+=d.monitor_bad_reducer;bad_RAM+=d.monitor_bad_field_write;
                need(!d.monitor_bad_reducer,"COLDLEG_BAD_TOKEN_IN_REDUCER");need(!d.monitor_bad_field_write,"COLDLEG_BAD_TOKEN_IN_RAM");}
            if(d.sim_cancel)need(!d.monitor_read && !d.monitor_write && !d.monitor_image_write,"COLDLEG_RAW_CANCEL_KILL");
        }
        d.clk=1;d.eval();++ticks;};
    auto start=[&](unsigned op,unsigned addr,int32_t word){eval();need(d.cmd_ready && !d.rsp_valid,"COLDLEG_READY");
        d.cmd_opcode=op;d.cmd_address=addr;d.cmd_word=word;d.cmd_valid=1;tick();d.cmd_valid=0;};
    auto finish=[&](bool expect_error=false){unsigned waited=0;while(!d.rsp_valid && waited++<10000)tick();
        need(d.rsp_valid && bool(d.rsp_error)==expect_error,"COLDLEG_RESPONSE");int32_t result=int32_t(d.rsp_word);
        d.rsp_ready=1;tick();d.rsp_ready=0;return result;};
    auto reload=[&](){start(0,0,0);finish();for(unsigned i=0;i<N;++i){start(1,i,i==0?9:0);finish();}};
    tick();d.rst_n=1;tick();reload();start(5,0,0);observation=true;
    unsigned waited=0;
    if(mode=="cancel-pending"){
        while(!d.monitor_transfer_pending && waited++<1000)tick();need(d.monitor_transfer_pending,"COLDLEG_PENDING_WITNESS");
        d.sim_cancel=1;eval();tick();d.sim_cancel=0;
    }else{
        eval();while(!d.monitor_match && waited++<1000){tick();eval();}need(d.monitor_match,"COLDLEG_RESPONSE_WITNESS");
        if(mode=="upper33-final")d.sim_fault_word=(uint64_t(1)<<32)+7;
        else if(mode=="numeric-first")d.sim_fault_word=(uint64_t(1)<<33)-2;
        d.sim_fault_mode=mode=="double-meta"?2:mode=="double-image"?3:mode=="double-transfer"?4:1;
        if(mode=="cancel-on-response")d.sim_cancel=1;
        bad_active=true;eval();const bool immediate=bool(d.monitor_fault);
        if(!cancelled)need(immediate==!delayed,"COLDLEG_IMMEDIATE_FAULT_CLASS");
        if(negative){tick();d.sim_fault_mode=0;eval();need(!d.monitor_fault,"COLDLEG_NUMERIC_EDGE_CONTRACT");}
        tick();d.sim_fault_mode=0;
        if(mode=="cancel-after-source")d.sim_cancel=1;
        eval();if(!cancelled)need(d.monitor_fault && bool(d.monitor_prefill_error)==!delayed,"COLDLEG_NUMERIC_EDGE_CONTRACT");
        if(mode=="cancel-after-source" || mode=="cancel-on-response"){tick();d.sim_cancel=0;}
    }
    if(!cancelled){finish(true);need(d.fault_sticky && !d.image_valid && !d.prefill_valid,"COLDLEG_QUARANTINE");
        for(unsigned i=0;i<16;++i){tick();need(!d.monitor_read && !d.monitor_write && !d.monitor_image_write && !d.monitor_cache,"COLDLEG_QUIET_TAIL");}
        observation=false;bad_active=false;start(5,0,0);finish(true);need(!d.image_valid && !d.prefill_valid,"COLDLEG_RELOAD_REQUIRED");
    }else{
        for(unsigned i=0;i<16;++i){tick();need(!d.monitor_read && !d.monitor_write && !d.monitor_image_write && !d.monitor_cache && !d.rsp_valid,"COLDLEG_CANCEL_TAIL");}
        observation=false;bad_active=false;d.rst_n=0;tick();d.rst_n=1;tick();
    }
    reload();start(5,0,0);finish();
    const uint64_t groups=N<128?1:N/128,ntt=2*AW*(groups+10)+(N+63)/64+15;
    need(d.image_valid && d.prefill_valid && d.profile_loads && !d.profile_hits && d.root_cycles==9 && d.ntt_cycles==ntt,"COLDLEG_RECOVERY_CALENDAR");
    for(unsigned i=0;i<N;++i){start(2,i,0);need(finish()==int32_t(i==0?81:0),"COLDLEG_RECOVERY_VALUE");}
    need(context.threads()==1 && d.threads()==1,"COLDLEG_THREADS");
    std::cout<<"COLDLEG_FAULT_PASS aw="<<AW<<" case="<<mode<<" fields=3 raw_delta="<<unsigned(delayed)
        <<" invalid_reducer="<<bad_reducer<<" invalid_ram="<<bad_RAM<<" quiet=16 reload_words="<<N
        <<" recovery_ntt="<<ntt<<" ticks="<<ticks<<"\n";
    d.final();return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
