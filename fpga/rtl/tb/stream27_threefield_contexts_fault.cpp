#define main frozen_threefield_main
#include "stream27_threefield_contexts.cpp"
#undef main
static void propose(DUT& d,const Frame& f){
    clear(d);d.clk=0;d.in_slot_valid=d.frame_start=d.correction_valid=1;
    d.context_in=d.correction_context=f.context;d.generation_in=d.correction_generation=f.generation;
    d.epoch_in=d.correction_epoch=f.epoch;d.base_in=f.base;
    for(unsigned b=0;b<P;b++){d.data_in[b]=f.input.digits[reverse_lane(b)*T];d.c0_in[b]=uint32_t(f.input.c0[b]);d.c1_in[b]=uint32_t(f.input.c1[b]);}
}
static void other_stopped(DUT& d,const Frame& other){
    propose(d,other);d.eval();need(d.out_error&&!d.frame_accept&&!d.correction_accept&&!d.digit_eligible&&!d.boundary_eligible,"S4_THREE_CTX_FAULT_OTHER_PRE");
    d.clk=1;d.eval();need(d.out_error&&!d.frame_accept&&!d.correction_accept&&!d.digit_eligible&&!d.boundary_eligible,"S4_THREE_CTX_FAULT_OTHER_POST");
}
static void faults(DUT& d){
    auto plan=frames();const Frame& a=plan[0];const Frame& b=plan[1];
    for(unsigned mode=0;mode<2;mode++){
        setup(d);propose(d,a);
        if(mode==0)d.base_in=a.base+1;
        if(mode==1)d.generation_in=d.correction_generation=a.generation+1;
        d.eval();need(d.fault_pending&&!d.frame_accept,"S4_THREE_CTX_DENIED_PRE mode="+std::to_string(mode));
        d.clk=1;d.eval();need(d.out_error&&!d.frame_accept&&!d.correction_accept,"S4_THREE_CTX_DENIED_REGISTERED mode="+std::to_string(mode));
        other_stopped(d,b);
    }
    setup(d);propose(d,a);d.eval();need(!d.fault_pending&&d.frame_accept&&d.correction_accept,"S4_THREE_CTX_DUPLICATE_FIRST");
    d.clk=1;d.eval();need(!d.out_error&&d.fault_pending,"S4_THREE_CTX_DUPLICATE_PROSPECTIVE");
    d.clk=0;d.eval();d.clk=1;d.eval();need(d.out_error&&!d.frame_accept&&!d.correction_accept,"S4_THREE_CTX_DUPLICATE_SECOND");
    other_stopped(d,b);
}
static void cancelled_tail(DUT& d,bool live_mismatch){
    setup(d);const Frame f=frames()[0];unsigned words=0,pairs=0,done=0;
    for(unsigned tick=0;tick<DONE+2;tick++){
        d.clk=0;clear(d);
        if(live_mismatch)d.live_generation=(23u<<8)|12;else d.context_enabled=2;
        if(tick<T){d.in_slot_valid=1;d.frame_start=tick==0;d.epoch_in=f.epoch;
            for(unsigned lane=0;lane<P;lane++)d.data_in[lane]=f.input.digits[reverse_lane(lane)*T+tick];}
        if(tick==0){d.correction_valid=1;d.correction_epoch=f.epoch;
            for(unsigned block=0;block<P;block++){d.c0_in[block]=uint32_t(f.input.c0[block]);d.c1_in[block]=uint32_t(f.input.c1[block]);}}
        d.eval();need(!d.out_error&&!d.fault_pending&&bool(d.frame_accept)==(tick==0)&&bool(d.correction_accept)==(tick==0),"S4_THREE_CTX_CANCEL_RAW_ADMISSION");
        d.clk=1;d.eval();need(!d.out_error,"S4_THREE_CTX_CANCEL_NO_GLOBAL_FAULT");
        d.frame_start=d.correction_valid=0;d.in_slot_valid=tick+1<T;d.eval();need(!d.fault_pending,"S4_THREE_CTX_CANCEL_SETTLED");
        bool digit=tick>=DIGIT&&tick<DIGIT+T,boundary=tick==BOUNDARY;
        need(bool(d.digit_valid)==digit&&bool(d.boundary_valid)==boundary&&bool(d.frame_done)==(tick==DONE),"S4_THREE_CTX_CANCEL_DRAIN_CALENDAR");
        if(digit){unsigned row=tick-DIGIT;need(!d.digit_eligible&&d.digit_context==0&&d.digit_epoch==f.epoch&&d.digit_generation==f.generation,"S4_THREE_CTX_CANCEL_NO_DIGIT_PUBLICATION");for(unsigned block=0;block<P;block++)need(d.digit_data[block]==f.expected.digits[block*T+row],"S4_THREE_CTX_CANCEL_RAW_VALUE");words+=P;}
        if(boundary){need(!d.boundary_eligible&&d.boundary_context==0&&d.next_epoch==uint16_t(f.epoch+1)&&d.next_generation==f.generation,"S4_THREE_CTX_CANCEL_NO_BOUNDARY_PUBLICATION");for(unsigned block=0;block<P;block++)need(int32_t(d.next_c0[block])==f.expected.c0[block]&&int32_t(d.next_c1[block])==f.expected.c1[block],"S4_THREE_CTX_CANCEL_BOUNDARY_VALUE");pairs+=P;}
        if(tick==DONE){need(d.done_context==0&&d.done_epoch==f.epoch,"S4_THREE_CTX_CANCEL_DONE");done++;}
    }
    need(words==N&&pairs==P&&done==1,"S4_THREE_CTX_CANCEL_LEDGER");
}
int main(int argc,char** argv){try{VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d(&context);if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);need(argc==1&&gfn16_runtime::matches(context,d),"S4_THREE_CTX_FAULT_ARGUMENTS");faults(d);cancelled_tail(d,false);cancelled_tail(d,true);std::cout<<"S4_THREE_CONTEXTS_FAULT_PASS base_denial=1 profile_generation_denial=1 held_second_edge=1 global_other_stop=3 cancellation_tails=2 cancellation_global_fault=0\n";return 0;}catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}}
