#define main storage2_normal_unused_main
#include "stream27_host_contexts.cpp"
#undef main
#include "c2_storage2_fault_config.h"

// Actual generated-root ABI is checked against this candidate's collected
// native header by the constructor. Mutations are simulation diagnostics only.
static void storage_reset(DUT& d){
    clear(d);d.rst_n=0;d.eval();edge(d);
    need(!d.error&&!d.busy&&!d.done&&!d.canonical_ready&&!d.read_valid&&!d.feed_level,
         "C2_STORAGE_RESET_PUBLIC");
    need(!STORAGE(seed_running)&&!STORAGE(payload_reserved)&&!STORAGE(payload_ready)&&
         !STORAGE(term_producer__DOT__product_slot)&&
         !STORAGE(term_producer__DOT__context_valid)[0]&&!STORAGE(term_producer__DOT__context_valid)[1],
         "C2_STORAGE_RESET_ACTUAL_VALIDITY");
    d.rst_n=1;d.clk=0;d.eval();
}
static void storage_job(DUT& d,bool bad_base=false){
    storage_reset(d);
    for(unsigned ctx=0;ctx<2;ctx++)for(unsigned a=0;a<N;a++){
        clear(d);d.load_we=1;d.host_context=ctx;d.host_addr=a;d.write_data=INITIAL[ctx][a];edge(d);
    }
    clear(d);d.start_contexts=d.batch_mode=3;
    d.base=uint64_t(bad_base?2:BASES[0])|(uint64_t(BASES[1])<<32);
    d.warm_count=uint64_t(COUNTS[0])|(uint64_t(COUNTS[1])<<32);
    for(unsigned ctx=0;ctx<2;ctx++)for(unsigned b=0;b<P;b++){
        d.initial_c0[ctx*P+b]=uint32_t(C0[ctx][b]);d.initial_c1[ctx*P+b]=uint32_t(C1[ctx][b]);
    }
    edge(d);if(!bad_base)need(!d.error&&d.busy==3,"C2_STORAGE_JOB_START");
}
static void storage_quarantine(DUT& d){
    need(d.error&&!d.busy&&!d.done&&!d.canonical_ready&&!d.read_valid,"C2_STORAGE_GLOBAL_ABORT");
    for(unsigned k=0;k<8;k++){
        clear(d);d.host_context=k&1;d.read_en=d.load_we=d.command_valid=1;d.start_contexts=3;
        edge(d);need(d.error&&!d.busy&&!d.done&&!d.canonical_ready&&!d.read_valid&&!d.command_accept,
                     "C2_STORAGE_STICKY_NO_PUBLICATION");
    }
}
static void storage_external(DUT& d){
    storage_job(d,true);storage_quarantine(d);
    for(unsigned mode=0;mode<2;mode++){
        storage_job(d);clear(d);d.command_valid=1;d.command_context=0;
        d.command_index=mode?65537:1;d.command_generation=mode?1:2;
        edge(d);storage_quarantine(d);
    }
    std::cout<<"C2_STORAGE_EXTERNAL_PASS bad_base=1 stale_generation=1 full32_index=1 global_abort=3 peer_recovery=0\n";
}
static void storage_resets(DUT& d){
    for(unsigned mode=0;mode<3;mode++){
        storage_job(d);bool found=false;
        for(unsigned age=1;age<1000;age++){
            clear(d);d.clk=0;d.eval();need(!d.error&&!d.done&&!d.canonical_ready,"C2_STORAGE_RESET_PRE_NORMAL");
            bool event=mode==0?bool(STORAGE(seed_running)):
                mode==1?bool(STORAGE(fwd_slot)):
                bool(STORAGE(fwd_slot)&&STORAGE(protocol_pw_row)==T-1&&STORAGE(term_producer__DOT__product_slot));
            if(event){found=true;storage_reset(d);break;}
            d.clk=1;d.eval();
        }
        need(found,"C2_STORAGE_RESET_ACTUAL_EVENT");
        for(unsigned k=0;k<8;k++){
            clear(d);d.read_en=1;edge(d);
            need(!d.busy&&!d.done&&!d.error&&!d.read_valid&&!d.canonical_ready&&!STORAGE(payload_ready)&&
                 !STORAGE(term_producer__DOT__product_slot),"C2_STORAGE_RESET_QUIET_TAIL");
        }
        run(d); // Every reset recovers the complete two-chain numerical corpus.
    }
    std::cout<<"C2_STORAGE_RESET_PASS seed=1 pointwise=1 last_read_e4=1 quiet_edges=24 recovered_reads="<<12*N<<" epoch_wrap=1\n";
}
static void storage_owners(DUT& d){
    const unsigned bits[4]={25,24,23,7}; // Logical bank, context, epoch, generation.
    for(unsigned mode=0;mode<4;mode++){
        storage_job(d);bool injected=false,failed=false;
        for(unsigned age=1;age<1000;age++){
            clear(d);d.clk=0;d.eval();
            need(!d.done&&!d.canonical_ready&&!d.read_valid,"C2_STORAGE_OWNER_NO_PARTIAL_PUBLICATION");
            if(!injected&&(STORAGE(payload_ready)&1u)){
                auto& key=STORAGE(payload_owner)[0];
                need((STORAGE(payload_reserved)&1u)&&!(key&(1u<<24)),"C2_STORAGE_OWNER_REAL_CACHED_KEY");
                key^=1u<<bits[mode];injected=true;d.eval();
            }
            d.clk=1;d.eval();if(d.error){failed=true;break;}
        }
        need(injected&&failed,"C2_STORAGE_OWNER_FULL_KEY_REJECTION");storage_quarantine(d);
    }
    run(d);
    std::cout<<"C2_STORAGE_OWNER_PASS mutants=4 full27=1 bank_context_epoch_generation=1 publication=0 recovered_reads="<<4*N<<" simulation_only=1\n";
}
static void storage_early_cache(DUT& d){
    storage_job(d);bool failed=false;
    for(unsigned age=1;age<300;age++){
        clear(d);edge(d);need(!d.done&&!d.canonical_ready&&!d.read_valid,"C2_STORAGE_EARLY_CACHE_NO_PUBLICATION");
        if(d.error){failed=true;break;}
    }
    need(failed,"C2_STORAGE_EARLY_CACHE_DIAGNOSTIC_NOT_DETECTED");storage_quarantine(d);
    std::cout<<"C2_STORAGE_EARLY_CACHE_PASS seed_start_token=1 duplicate_cache_rejected=1 publication=0 simulation_only=1\n";
}
int main(int argc,char** argv){try{
    VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d(&context);
    if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
    need(argc==2&&gfn16_runtime::matches(context,d),"C2_STORAGE_FAULT_ARGUMENTS_THREADS");
    std::string mode=argv[1];
    if(mode=="--external")storage_external(d);else if(mode=="--reset")storage_resets(d);
    else if(mode=="--owner")storage_owners(d);else if(mode=="--early-cache")storage_early_cache(d);
    else need(false,"C2_STORAGE_FAULT_MODE");return 0;
}catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}}
