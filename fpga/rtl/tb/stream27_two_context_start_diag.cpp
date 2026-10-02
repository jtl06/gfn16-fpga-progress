#define main frozen_field_main
#include "stream27_two_context_field.cpp"
#undef main
int main(int argc,char** argv){
    try{
        VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d(&context);
        if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
        bool duplicate=argc==2&&std::string(argv[1])=="--duplicate";
        need(argc==1||duplicate,"S4_TWO_DIAG_ARGUMENTS");auto image=frames();const Frame& f=image.front();
        clear(d);d.clk=0;d.rst_n=0;d.eval();d.clk=1;d.eval();d.clk=0;d.rst_n=1;d.eval();
        d.in_slot_valid=d.frame_start=d.correction_valid=1;d.context_in=d.correction_context=f.context;
        d.generation_in=d.correction_generation=f.generation;d.epoch_in=d.correction_epoch=f.epoch;d.base_in=f.base;
        for(unsigned lane=0;lane<P;lane++){
            d.data_in[lane]=f.digits[reverse_lane(lane)*T];d.c0_in[lane]=uint32_t(f.c0[lane]);d.c1_in[lane]=uint32_t(f.c1[lane]);
        }
        d.eval();need(d.frame_accept&&d.correction_accept&&!d.out_error&&!d.fault_pending,"S4_TWO_DIAG_PRE_ACCEPT");
        d.clk=1;d.eval();unsigned registered=d.out_error,held=d.fault_pending;
        if(duplicate){
            need(!registered&&held&&d.owner_count==1,"S4_TWO_DUPLICATE_FIRST_EDGE");
            d.clk=0;d.eval();need(d.fault_pending&&!d.frame_accept&&!d.correction_accept,"S4_TWO_DUPLICATE_PRE_SECOND");
            d.clk=1;d.eval();need(d.out_error&&!d.frame_accept&&!d.correction_accept,"S4_TWO_DUPLICATE_LATCHED");
            const Frame& other=image[1];
            d.clk=0;d.context_in=d.correction_context=other.context;
            d.generation_in=d.correction_generation=other.generation;d.epoch_in=d.correction_epoch=other.epoch;d.base_in=other.base;
            d.eval();need(d.out_error&&!d.frame_accept&&!d.correction_accept&&!d.out_eligible&&!d.commit_valid,"S4_TWO_DUPLICATE_GLOBAL_STOP");
            d.clk=1;d.eval();need(d.out_error&&!d.frame_accept&&!d.correction_accept&&!d.out_eligible&&!d.commit_valid,"S4_TWO_DUPLICATE_OTHER_CONTEXT_STOP");
            std::cout<<"S4_TWO_DUPLICATE_PASS held_second_edge=1 registered_fault=1 unrelated_context_stopped=1 clock_edges=3\n";return 0;
        }
        d.frame_start=0;d.correction_valid=0;d.eval();unsigned dropped=d.fault_pending;
        std::cout<<"S4_TWO_START_DIAG registered="<<registered<<" pending_held="<<held<<" pending_after_drop="<<dropped<<" owners="<<unsigned(d.owner_count)<<" clock_edges=1\n";
        need(!registered&&held&&!dropped&&d.owner_count==1,"S4_TWO_DIAG_CONTRACT");return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}
}
