#include "p8_small_prp_helpers_v1.h"
int main(int argc,char** argv){try{
    if(argc==2&&std::string(argv[1])=="--runtime-probe")return scalar_regression_main(argc,argv);
    bool negative=argc==2&&std::string(argv[1])=="--negative-oracle";
    need(argc==1||negative,"P8_FAULT_ARGUMENTS");
    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);DUT d{&context};FeedCounts c;
    if(!negative){
        // Underflow cancels the scheduled frame; no external cancel ABI exists.
        feed_fault(d,0,c);
        // One asserted reset edge with four pending descriptors, cold and warm.
        feed_abort(d,10,c);feed_abort(d,102+INTERVAL+8,c);
    }
    // Separate nonzero numeric recovery, including all signed96 upper words.
    reset(d);Image input{};input[0]=3;load(d,input);Job job{};
    job.base=MIN_BASE;job.count=1;job.twice=1;job.expected[0]=18;
    candidate(d,job,false,0,0);production(d,job);Counts reads;
    compare(d,job,0,0,negative,reads);
    need(c.faults==1&&c.aborts==2&&reads.reads==N,"P8_FAULT_COVERAGE");
    std::cout<<"P8_FAULT_PASS underflow_cancels=1 reset_aborts=2 reset_ages=10,237 recovery_reads=128 nonzero_recovery_reads=32\n";
    need(context.threads()==1&&d.threads()==1,"P8_FAULT_THREADS");d.final();return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
