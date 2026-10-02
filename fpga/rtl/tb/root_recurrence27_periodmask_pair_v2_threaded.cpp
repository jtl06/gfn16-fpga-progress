// Explicit context and runtime probe around the separately pinned pair bench.
#define main periodmask_pair_main
#include "root_recurrence27_periodmask_pair_v2.cpp"
#undef main
int main(int argc,char** argv) {
    VerilatedContext* const context=Verilated::threadContextp();
    context->threads(1);
    context->commandArgs(argc,argv);
    if(argc==2 && std::string(argv[1])=="--runtime-probe") {
        Vroot_recurrence27_periodmask_pair dut{context};
        dut.eval();
        std::cout<<"{\"context_threads\":"<<context->threads()
            <<",\"model_threads\":"<<dut.threads()
            <<",\"lanes\":"<<dut.probe_lanes<<",\"p\":"<<dut.probe_p
            <<",\"q\":"<<dut.probe_q<<"}\n";
        return context->threads()==1 && dut.threads()==1 ? 0 : 2;
    }
    const int result=periodmask_pair_main(argc,argv);
    return context->threads()==1 ? result : 97;
}
