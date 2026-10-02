#define main storage2_normal_unused_main
#include "stream27_host_contexts.cpp"
#undef main
static void fault_job(DUT& d,bool bad_base=false){
    clear(d);d.rst_n=0;d.eval();edge(d);d.rst_n=1;d.clk=0;d.eval();
    for(unsigned c=0;c<2;c++)for(unsigned a=0;a<N;a++){
        clear(d);d.load_we=1;d.host_context=c;d.host_addr=a;d.write_data=INITIAL[c][a];edge(d);
    }
    clear(d);d.start_contexts=d.batch_mode=d.feed_mode=3;
    d.base=uint64_t(bad_base?2:BASES[0])|(uint64_t(BASES[1])<<32);
    d.warm_count=uint64_t(COUNTS[0])|(uint64_t(COUNTS[1])<<32);
    for(unsigned c=0;c<2;c++)for(unsigned b=0;b<P;b++){
        d.initial_c0[c*P+b]=uint32_t(C0[c][b]);d.initial_c1[c*P+b]=uint32_t(C1[c][b]);
    }
    edge(d);if(!bad_base)need(!d.error&&d.busy==3,"C2_STORAGE_EXTERNAL_FEED_START");
}
static void fault_stop(DUT& d){
    need(d.error&&!d.busy&&!d.done&&!d.canonical_ready&&!d.read_valid,"C2_STORAGE_EXTERNAL_ABORT");
    for(unsigned k=0;k<8;k++){
        clear(d);d.read_en=d.command_valid=d.load_we=1;d.start_contexts=3;edge(d);
        need(d.error&&!d.busy&&!d.done&&!d.canonical_ready&&!d.read_valid&&!d.command_accept,
             "C2_STORAGE_EXTERNAL_STICKY");
    }
}
int main(int argc,char** argv){try{
    VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d(&context);
    if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
    need(argc==1&&gfn16_runtime::matches(context,d),"C2_STORAGE_EXTERNAL_ARGUMENTS");
    fault_job(d,true);fault_stop(d);
    for(unsigned mode=0;mode<2;mode++){
        fault_job(d);clear(d);d.command_valid=1;d.command_context=0;
        d.command_index=mode?65537:1;d.command_generation=mode?1:2;
        d.clk=0;d.eval();need(d.command_ready&&!d.command_accept&&!d.error,"C2_STORAGE_EXTERNAL_DENIED_PRE");
        d.clk=1;d.eval();fault_stop(d);
    }
    run(d);
    std::cout<<"C2_STORAGE_EXTERNAL_PASS bad_base=1 stale_generation=1 full32_index=1 global_abort=3 recovered_reads="<<4*N<<" peer_recovery=0\n";
    return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
