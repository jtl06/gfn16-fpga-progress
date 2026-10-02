#define main normal_unused_main
#include "stream27_host_contexts.cpp"
#undef main
#ifndef S4_HOST_PORTS_ONLY
#include "Vgenefer_stream27_host_contexts_aw5_p8_v1_closed_ram_v2___024root.h"
#endif
static void reset(DUT& d){clear(d);d.rst_n=0;d.eval();edge(d);need(!d.error&&!d.busy&&!d.done&&!d.canonical_ready&&!d.read_valid&&!d.read_owner&&!d.feed_level&&!d.operations_started&&!d.completed_squares,"S4_HOST_FAULT_RESET");d.rst_n=1;d.clk=0;d.eval();}
static void job(DUT& d,bool feed,bool bad_base=false){
    reset(d);for(unsigned ctx=0;ctx<2;ctx++)for(unsigned address=0;address<N;address++){clear(d);d.load_we=1;d.host_context=ctx;d.host_addr=address;d.write_data=INITIAL[ctx][address];edge(d);}
    clear(d);d.start_contexts=d.batch_mode=3;d.feed_mode=feed?3:0;d.base=uint64_t(bad_base?2:BASES[0])|(uint64_t(BASES[1])<<32);d.warm_count=uint64_t(COUNTS[0])|(uint64_t(COUNTS[1])<<32);
    for(unsigned ctx=0;ctx<2;ctx++)for(unsigned block=0;block<P;block++){d.initial_c0[ctx*P+block]=uint32_t(C0[ctx][block]);d.initial_c1[ctx*P+block]=uint32_t(C1[ctx][block]);}edge(d);
    if(!bad_base)need(!d.error&&d.busy==3&&d.accepted_generation==0x0101,"S4_HOST_FAULT_START");
}
static void quarantined(DUT& d){
    need(d.error&&!d.busy&&!d.done&&!d.canonical_ready&&!d.read_valid&&!d.command_accept&&!d.operation_accept,"S4_HOST_FAULT_GLOBAL_ABORT");
    for(unsigned k=0;k<8;k++){clear(d);d.host_context=k&1;d.read_en=d.load_we=d.command_valid=1;d.start_contexts=3;d.command_index=1;d.command_generation=1;edge(d);need(d.error&&!d.busy&&!d.done&&!d.canonical_ready&&!d.read_valid&&!d.command_ready&&!d.command_accept&&!d.operation_accept,"S4_HOST_FAULT_STICKY_NO_PEER_RECOVERY");}
}
static void external(DUT& d){
    job(d,false,true);quarantined(d);
    for(unsigned mode=0;mode<2;mode++){
        job(d,true);clear(d);d.command_valid=1;d.command_context=0;d.command_index=mode?65537:1;d.command_generation=mode?1:2;
        d.clk=0;d.eval();need(d.command_ready&&!d.command_accept&&!d.error,"S4_HOST_FAULT_DESCRIPTOR_DENIED_PRE");edge(d);quarantined(d);
    }
    std::cout<<"S4_HOST_CONTEXTS_EXTERNAL_FAULT_PASS bad_base=1 stale_generation=1 full32_index_alias=1 global_abort=3 peer_recovery=0\n";
}
static void resets(DUT& d){
    run(d);clear(d);d.host_context=0;d.read_en=1;d.host_addr=0;edge(d);read_word(d,0,0);
    d.rst_n=0;d.eval();need(!d.read_valid&&!d.read_owner&&!d.canonical_ready&&!d.busy&&!d.done,"S4_HOST_RESET_PENDING_RESPONSE_REVOKED");
    d.rst_n=1;d.eval();unsigned retained=0;
    for(unsigned address=0;address<N;address++)for(unsigned ctx=0;ctx<2;ctx++){
        clear(d);d.host_context=ctx;d.read_en=1;d.host_addr=address;edge(d);need(!d.read_valid&&!d.canonical_ready&&!d.busy&&!d.done&&!d.error,"S4_HOST_RESET_RETAINED_PAYLOAD_UNPUBLISHED");
        int32_t expected=EXPECTED[ctx][address];uint32_t high=expected<0?0xffffffffu:0;
        need(d.read_data[0]==uint32_t(expected)&&d.read_data[1]==high&&d.read_data[2]==high,"S4_HOST_RESET_ACTUAL_RAM_RETENTION");retained++;
    }
    job(d,true);
    for(unsigned ctx=0;ctx<2;ctx++)for(unsigned index=1;index<COUNTS[ctx];index++){
        clear(d);d.command_context=ctx;d.command_valid=1;d.command_index=index;d.command_generation=1;d.clk=0;d.eval();need(d.command_ready&&d.command_accept,"S4_HOST_RESET_REAL_FIFO_FILL");edge(d);need(!d.error,"S4_HOST_RESET_FIFO_ACCEPTED");
    }
    need(d.feed_level==34,"S4_HOST_RESET_NONEMPTY_TWO_FIFOS");reset(d);
    for(unsigned k=0;k<8;k++){clear(d);d.read_en=1;d.host_context=k&1;edge(d);need(!d.error&&!d.busy&&!d.done&&!d.read_valid&&!d.canonical_ready&&!d.feed_level&&!d.command_ready&&!d.operations_started&&!d.completed_squares,"S4_HOST_RESET_NO_STALE_WORK");}
    run(d);need(retained==2*N,"S4_HOST_RESET_RETAINED_LEDGER");
    std::cout<<"S4_HOST_CONTEXTS_RESET_PASS resets=2 retained_words="<<retained<<" pending_response_invalid=1 nonempty_fifo=2/4 recovered_chains=2\n";
}
#ifndef S4_HOST_PORTS_ONLY
static void owners(DUT& d){
    run(d); // Genuine both-chain normal baseline, not a comparator substitute.
    for(unsigned mode=0;mode<4;mode++){
        job(d,false);unsigned mutation=mode<2?FIRST[1]+T+8:FIRST[0]+(COUNTS[0]-1)*INTERVAL+FIRST_DIGIT-8,first_fault=0;
        for(unsigned age=1;age<1000;age++){
            clear(d);d.clk=0;d.eval();
            if(age==mutation){
                if(mode==0){auto& count=d.rootp->genefer_stream27_host_contexts_aw5_p8_v1_closed_ram_v2__DOT__job_count[0];need(count==3,"S4_HOST_OWNER_MUTATE_COUNT_BASELINE");count+=65536;need(uint16_t(count)==3&&count!=3,"S4_HOST_OWNER_FULL32_ALIAS_MUTATION");}
                if(mode==1){auto& epoch=d.rootp->genefer_stream27_host_contexts_aw5_p8_v1_closed_ram_v2__DOT__job_epoch[0];need(epoch==65534,"S4_HOST_OWNER_MUTATE_EPOCH_BASELINE");epoch^=0x8000;}
                if(mode==2){auto& generation=d.rootp->genefer_stream27_host_contexts_aw5_p8_v1_closed_ram_v2__DOT__engine__DOT__arithmetic__DOT__carry_generation;need(generation==1,"S4_HOST_OWNER_MUTATE_GEN_BASELINE");generation^=0x80;}
                if(mode==3){auto& ctx=d.rootp->genefer_stream27_host_contexts_aw5_p8_v1_closed_ram_v2__DOT__engine__DOT__arithmetic__DOT__carry_context;need(ctx==0,"S4_HOST_OWNER_MUTATE_CTX_BASELINE");ctx=1;}
                d.eval();
            }
            d.clk=1;d.eval();need(!d.done&&!d.canonical_ready&&!d.read_valid,"S4_HOST_OWNER_NO_PARTIAL_PUBLICATION");
            if(d.error){first_fault=age;break;}
            if(age<mutation)need(!d.error,"S4_HOST_OWNER_PRE_MUTATION_NORMAL");
        }
        unsigned first_capture=FIRST[0]+(COUNTS[0]-1)*INTERVAL+FIRST_DIGIT+1;
        need(first_fault>=first_capture&&first_fault<=FIRST[0]+(COUNTS[0]-1)*INTERVAL+CARRY_DONE+8,"S4_HOST_OWNER_BOUNDED_ORIGIN_FAULT");
        if(mode<2)need(first_fault==first_capture,"S4_HOST_OWNER_EXACT_CAPTURE_REJECTION");
        quarantined(d);
    }
    std::cout<<"S4_HOST_CONTEXTS_OWNER_FAULT_PASS baseline_chains=2 full32_ordinal_alias=1 epoch=1 generation=1 context=1 global_abort=4 publication=0 simulation_mutations=1\n";
}
#endif
int main(int argc,char** argv){try{VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d(&context);if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);need(argc==2&&gfn16_runtime::matches(context,d),"S4_HOST_FAULT_ARGUMENTS_THREADS");if(std::string(argv[1])=="--external")external(d);else if(std::string(argv[1])=="--reset")resets(d);
#ifndef S4_HOST_PORTS_ONLY
else if(std::string(argv[1])=="--owner")owners(d);
#endif
else need(false,"S4_HOST_FAULT_UNKNOWN_MODE");return 0;}catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}}
