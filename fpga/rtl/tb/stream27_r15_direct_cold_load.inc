// AUTHOR direct-wrapper driver. No legacy raw-load bypass and no PCIe/CDC claim.
static void direct_load(DUT& d){
    d.dc_current_session=77;d.dc_session=77;d.dc_link_drained=1;d.dc_transport_empty=1;
    edge(d);need(!d.error&&d.dc_idle==3,"R15_DIRECT_SESSION_DRAIN");
    unsigned accepted=0;
    for(unsigned ctx=0;ctx<2;ctx++){
        clear(d);d.dc_context=ctx;d.dc_owner=owner(ctx);d.dc_session=77;
        uint32_t lease=d.dc_next_lease;need(lease==ctx+1,"R15_CORE_MINTED_LEASE");d.dc_lease=lease;
        d.dc_count=COUNTS[ctx];d.dc_mask=0;d.dc_mode=1;
        for(unsigned k=0;k<8;k++)d.dc_profile[k]=0;
        d.dc_profile[0]=BASES[ctx];d.dc_profile[1]=1;
        need(uint16_t(d.dc_next_epoch>>(16*ctx))==EPOCHS[ctx]&&((d.dc_job_generation>>(8*ctx))&255)==0,"R15_CORE_ISSUED_OWNER_BASIS");
        d.dc_begin=1;edge(d);d.dc_begin=0;
        need(d.dc_active&&!d.dc_error&&!d.error&&!(d.dc_loaded&(1u<<ctx)),"R15_DIRECT_BEGIN");
        for(unsigned i=0;i<N+2*P;i++){
            d.dc_index=i;d.dc_word=i<N?uint32_t(INITIAL[ctx][i]):
                i<N+P?uint32_t(C0[ctx][i-N]):uint32_t(C1[ctx][i-N-P]);
            d.dc_word_valid=1;d.eval();unsigned waits=0;
            while(!d.dc_word_ready){edge(d);need(!d.error&&++waits<16,"R15_DIRECT_PORT_PROGRESS");}
            edge(d);accepted++;
            need(!d.error&&!d.dc_error&&d.dc_applied==i+1&&!d.canonical_ready,"R15_DIRECT_APPLIED_RAM_WORD");
        }
        d.dc_word_valid=0;edge(d);edge(d);d.dc_commit=1;edge(d);d.dc_commit=0;
        unsigned waits=0;while(!(d.dc_loaded&(1u<<ctx))){edge(d);need(!d.error&&++waits<8,"R15_DIRECT_COMMIT_ACK_PUBLISH");}
        need(!d.dc_active&&!d.error&&d.dc_loaded==((1u<<(ctx+1))-1),"R15_DIRECT_LOADED_NOT_STARTED");
    }
    need(accepted==2*(N+2*P),"R15_DIRECT_LOAD_COUNT");
    // Deliberately hostile inactive legacy payloads must not modify loaded data/header.
    clear(d);d.load_we=1;d.write_data=0xffffffffu;d.host_addr=N-1;d.base=0;d.warm_count=0;
    edge(d);need(!d.error&&d.dc_loaded==3&&!d.canonical_ready,"R15_NO_LEGACY_LOAD_BYPASS");
}
