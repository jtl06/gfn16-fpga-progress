// Private CPU-only benchmark. The exact captured R14 AW8 model is linked only
// for the existing runtime/source-package contract; it is never evaluated.
#include "s4_host_contexts_config_v1.h"
#include "native_runtime_context_v1.h"
#include "stream27_host_offload_host_benchmark_v2.h"
#include <iostream>
#include <string>

int main(int argc,char** argv){
    try{
        VerilatedContext context;
        gfn16_runtime::configure(context,argc,argv);
        DUT model(&context);
        if(argc==2 && std::string(argv[1])=="--runtime-probe")
            return gfn16_runtime::probe(context,model);
        r14_host_need(gfn16_runtime::matches(context,model),"RUNTIME");
        if(argc==2 && std::string(argv[1])=="--host-selfcheck"){
            const unsigned checks=r14_host_selfcheck();
            r14_host_need(checks==301,"EXACT_SELFCHECK_COUNT");
            std::cout<<"R14_HOST_CPU_SELFCHECK_PASS checks=301 n=32 signed=-1 special=both atomic=1\n";
            return 0;
        }
        if(argc==2 && std::string(argv[1])=="--host-benchmark"){
#if defined(__linux__)
            // Guard admission before any full-size input construction or math.
            char host[256]={};
            r14_host_need(gethostname(host,sizeof(host)-1)==0,"HOSTNAME");
            const std::string hostname=std::string(host).substr(0,std::string(host).find('.'));
            r14_host_need(hostname=="aethia" || hostname=="gfn16-pilot-c4d","ADMITTED_HOSTNAME");
#else
            r14_host_need(false,"ADMITTED_LINUX_ONLY");
#endif
            return r14_host_cpu_benchmark(3);
        }
        r14_host_need(false,"ARGUMENTS");
        return 1;
    }catch(const std::exception& error){
        std::cerr<<error.what()<<'\n';
        return 1;
    }
}
