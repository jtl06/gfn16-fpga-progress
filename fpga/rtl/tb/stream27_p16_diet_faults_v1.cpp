// Separate small whole-diet faults; no RTL mutation or normal-run delay.
#include "stream27_p16_diet_prp_helpers_v1.h"
int main(int argc,char** argv){try{
    if(argc==2&&std::string(argv[1])=="--runtime-probe")return scalar_regression_main(argc,argv);
    bool negative=argc==2&&std::string(argv[1])=="--negative-oracle";
    need(argc==1||negative,"P16_DIET_FAULT_ARGS");
    need(AW==5&&N==32&&P==16&&MIN_BASE==300&&INTERVAL==161&&CARRY_DONE==161&&FIRST_DIGIT==156,"P16_DIET_FAULT_SOURCE");
    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);DUT d{&context};FeedCounts c;
    if(!negative){
        for(unsigned type=0;type<4;++type)feed_fault(d,type,c);
        feed_abort(d,10,c);feed_abort(d,102+INTERVAL+8,c);
        need(c.faults==4&&c.aborts==2,"P16_DIET_ALL_CONTROLS");
    }
    reset(d);Program p{};p.base=MIN_BASE;p.paired=true;p.initial[16]=1;p.expected[0]=-1;p.bits={0};
    // Independent scalar identity: (b**16)**2 mod (b**32+1) is exactly -1.
    d.base=p.base;load(d,p.initial);chain_run(d,p,false,c);long_production(d,p);
    need(d.canonical_cycles==10*N&&d.image_copy_cycles==N+3,"P16_DIET_SPECIAL_10N_COPY");
    if(negative)p.expected[0]=0; // comparator-only after correct special branch.
    long_compare(d,p,c);need(!negative,"P16_DIET_ORACLE_NEGATIVE_MISSED");
    need(c.jobs==1&&c.operations==1&&c.reads==32,"P16_DIET_SPECIAL_FULL_SIGNED96");
    need(context.threads()==1&&d.threads()==1,"P16_DIET_FAULT_THREADS");
    std::cout<<"P16_DIET_FAULT_PASS descriptor_codes=1,2,3,4 reset_ages=10,271 quarantine_checks=20 recovery_words=224 special_signed96_words=32 canonical_special_cycles=320\n";
    d.final();return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
