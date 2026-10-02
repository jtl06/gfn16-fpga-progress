#define main arithmetic_unused_main
#include "stream27_threefield_contexts.cpp"
#undef main
static void clear_warm(DUT& d){clear(d);d.square_count=d.double_mask=d.feed_mode=d.command_valid=d.command_double=0;d.command_index=d.command_generation=0;}
static uint64_t packed_counts(const std::array<unsigned,2>& counts){return uint64_t(counts[0])|(uint64_t(counts[1])<<32);}
static void warm(DUT& d){
    clear_warm(d);setup(d);auto plan=frames();std::array<unsigned,2> started{},completed{};
    unsigned coefficients=0,digits=0,pairs=0,cold_frames=0,cold_corrections=0,internal_frames=0,internal_corrections=0,final_rows=0,final_boundaries=0,warm_done=0;
    bool a_finishes_while_b_active=false;
    unsigned end=plan.back().start+DONE+3;
    for(unsigned tick=0;tick<end;tick++){
        d.clk=0;clear_warm(d);const Frame* incoming=nullptr;const Frame* correction=nullptr;const Frame* feedback=nullptr;const Frame* automatic=nullptr;
        for(const auto& f:plan){if(f.ordinal==0&&tick>=f.start&&tick<f.start+T)incoming=&f;if(f.ordinal==0&&tick==f.correction)correction=&f;if(f.ordinal&&tick==f.start)feedback=&f;if(f.ordinal&&tick==f.correction)automatic=&f;}
        if(incoming){const auto& f=*incoming;unsigned row=tick-f.start;d.in_slot_valid=1;d.frame_start=row==0;d.context_in=f.context;d.generation_in=f.generation;d.epoch_in=f.epoch;d.base_in=f.base;d.square_count=f.context?5:3;d.double_mask=f.context?10:0;
            for(unsigned l=0;l<P;l++)d.data_in[l]=f.input.digits[reverse_lane(l)*T+row];}
        if(correction){const auto& f=*correction;d.correction_valid=1;d.correction_context=f.context;d.correction_epoch=f.epoch;d.correction_generation=f.generation;for(unsigned b=0;b<P;b++){d.c0_in[b]=uint32_t(f.input.c0[b]);d.c1_in[b]=uint32_t(f.input.c1[b]);}}
        d.eval();bool starts=incoming&&tick==incoming->start;
        need(bool(d.frame_accept)==starts&&bool(d.correction_accept)==bool(correction),"S4_WARM_COLD_ADMISSION tick="+std::to_string(tick));
        need(bool(d.internal_frame_accept)==bool(feedback)&&bool(d.internal_correction_accept)==bool(automatic),"S4_WARM_INTERNAL_ADMISSION tick="+std::to_string(tick));
        need(!d.out_error&&!d.fault_pending&&!d.command_accept,"S4_WARM_PRE_PENDING tick="+std::to_string(tick));
        need(uint64_t(d.started_frames)==packed_counts(started)&&uint64_t(d.completed_frames)==packed_counts(completed),"S4_WARM_PRE_FULL32_COUNTERS");
        if(starts){started[incoming->context]++;cold_frames++;}if(correction)cold_corrections++;if(feedback){started[feedback->context]++;internal_frames++;}if(automatic)internal_corrections++;
        unsigned expected_done_mask=0;
        for(const auto& f:plan)if(tick==f.start+DONE+1){completed[f.context]++;if(f.ordinal+1==(f.context?5u:3u))expected_done_mask|=1u<<f.context;}
        d.clk=1;d.eval();need(!d.out_error,"S4_WARM_POST_ERROR tick="+std::to_string(tick));
        d.frame_start=d.correction_valid=0;d.in_slot_valid=incoming&&tick+1<incoming->start+T;d.eval();need(!d.out_error&&!d.fault_pending,"S4_WARM_SETTLED_PENDING tick="+std::to_string(tick));
        need(uint64_t(d.started_frames)==packed_counts(started)&&uint64_t(d.completed_frames)==packed_counts(completed),"S4_WARM_POST_FULL32_COUNTERS");
        need(unsigned(d.warm_done)==expected_done_mask&&!d.warm_cancelled,"S4_WARM_DONE_EXACT");
        if(expected_done_mask){warm_done++;if(expected_done_mask&1u)a_finishes_while_b_active=d.active&2;}
        const Frame *coefficient=nullptr,*digit=nullptr,*boundary=nullptr,*done=nullptr;
        for(const auto& f:plan){if(tick>=f.start+COEFFICIENT&&tick<f.start+COEFFICIENT+T)coefficient=&f;if(tick>=f.start+DIGIT&&tick<f.start+DIGIT+T)digit=&f;if(tick==f.start+BOUNDARY)boundary=&f;if(tick==f.start+DONE)done=&f;}
        need(bool(d.coefficient_valid)==bool(coefficient)&&bool(d.digit_valid)==bool(digit)&&bool(d.boundary_valid)==bool(boundary)&&bool(d.frame_done)==bool(done),"S4_WARM_RAW_CALENDAR tick="+std::to_string(tick));
        if(coefficient){unsigned row=tick-coefficient->start-COEFFICIENT;need(d.coefficient_context==coefficient->context&&d.coefficient_row==row&&d.coefficient_start==(row==0),"S4_WARM_COEFFICIENT_TAG");for(unsigned b=0;b<P;b++)need(signed96(d.coefficient_data,b)==coefficient->coefficients[b*T+row],"S4_WARM_COEFFICIENT_VALUE");coefficients+=P;}
        bool final_digit=digit&&digit->ordinal+1==(digit->context?5u:3u),final_boundary=boundary&&boundary->ordinal+1==(boundary->context?5u:3u);
        need(bool(d.final_load_valid)==final_digit&&bool(d.final_boundary_valid)==final_boundary,"S4_WARM_FINAL_EXACT_ORDINAL");
        if(digit){unsigned row=tick-digit->start-DIGIT;need(d.digit_context==digit->context&&d.digit_epoch==digit->epoch&&d.digit_generation==digit->generation&&d.digit_sequence==digit->ordinal&&d.digit_row==row&&d.digit_start==(row==0)&&d.digit_eligible,"S4_WARM_DIGIT_FULL_TAG");for(unsigned b=0;b<P;b++)need(d.digit_data[b]==digit->expected.digits[b*T+row],"S4_WARM_DIGIT_VALUE");digits+=P;
            if(final_digit){uint64_t owner=(uint64_t(digit->ordinal)<<24)|(uint64_t(digit->epoch)<<8)|digit->generation;need(d.final_load_context==digit->context&&uint64_t(d.final_load_owner)==owner,"S4_WARM_FINAL_CONTEXT_OWNER56");final_rows++;}}
        if(boundary){need(d.boundary_context==boundary->context&&d.next_epoch==uint16_t(boundary->epoch+1)&&d.next_generation==boundary->generation&&d.boundary_sequence==boundary->ordinal&&d.boundary_eligible,"S4_WARM_BOUNDARY_FULL_TAG");for(unsigned b=0;b<P;b++)need(int32_t(d.next_c0[b])==boundary->expected.c0[b]&&int32_t(d.next_c1[b])==boundary->expected.c1[b],"S4_WARM_BOUNDARY_VALUE");pairs+=P;if(final_boundary)final_boundaries++;}
        if(done)need(d.done_context==done->context&&d.done_epoch==done->epoch,"S4_WARM_RAW_DONE_TAG");
    }
    need(started==completed&&completed[0]==3&&completed[1]==5&&!d.active&&warm_done==2&&a_finishes_while_b_active,"S4_WARM_UNEQUAL_DRAIN");
    need(cold_frames==2&&cold_corrections==2&&internal_frames==6&&internal_corrections==6&&coefficients==8*N&&digits==8*N&&pairs==8*P&&final_rows==2*T&&final_boundaries==2,"S4_WARM_LEDGER");
    std::cout<<"S4_WARM_CONTEXTS_PASS aw="<<AW<<" p="<<P<<" counts=3/5 cold_frames=2 cold_corrections=2 internal_frames=6 internal_corrections=6 coefficients="<<coefficients<<" digits="<<digits<<" boundary_pairs="<<pairs<<" final_rows="<<final_rows<<" final_boundaries=2 final_owner_bits=56 a_done_b_active=1 onchip_feedback=1 canonical_host=0\n";
}
int main(int argc,char** argv){try{VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d(&context);if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);need(argc==1&&gfn16_runtime::matches(context,d),"S4_WARM_ARGUMENTS_THREADS");warm(d);return 0;}catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}}
