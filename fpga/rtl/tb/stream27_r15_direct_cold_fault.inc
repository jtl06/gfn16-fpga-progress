// AUTHOR negatives for the frozen direct wrapper; no PCIe/reset-domain proof.
static void dc_reset(DUT& d){
    clear(d);d.dc_link_drained=0;d.dc_current_session=77;d.dc_session=77;d.dc_transport_empty=1;
    d.rst_n=0;edge(d);d.rst_n=1;d.dc_link_drained=1;edge(d);
    need(!d.error&&!d.dc_error&&!d.dc_loaded&&!d.dc_active,"R15_DC_FAULT_RESET");
}
static void dc_begin0(DUT& d){
    clear(d);d.dc_context=0;d.dc_owner=owner(0);d.dc_session=77;d.dc_lease=d.dc_next_lease;
    d.dc_count=COUNTS[0];d.dc_mask=0;d.dc_mode=1;
    for(unsigned k=0;k<8;k++)d.dc_profile[k]=0;
    d.dc_profile[0]=BASES[0];d.dc_profile[1]=1;
    d.dc_begin=1;
}
static void dc_failclosed(DUT& d){
    need(d.error&&d.dc_error,"R15_DC_EXPECT_FAULT");
    for(unsigned j=0;j<8;j++){
        clear(d);d.start_contexts=3;d.read_en=1;d.command_valid=1;edge(d);
        need(d.error&&!d.command_ready&&!d.command_accept&&!d.operation_accept&&!d.done&&
             !d.warm_done&&!d.busy&&!d.read_valid&&!d.canonical_ready,"R15_DC_GLOBAL_AUTHORITY_QUIET");
    }
}
static void direct_faults(DUT& d){
    unsigned cases=0;
    for(unsigned mode=0;mode<10;mode++){
        dc_reset(d);
        if(mode==6 || mode==7){
            direct_load(d);clear(d);
            if(mode==6)d.dc_link_drained=0;else d.dc_current_session=78;
            d.start_contexts=3;edge(d);dc_failclosed(d);cases++;continue;
        }
        dc_begin0(d);
        if(mode==0)d.dc_profile[2]=1;
        if(mode==1)d.dc_lease++;
        edge(d);d.dc_begin=0;
        if(mode<2){dc_failclosed(d);cases++;continue;}
        need(d.dc_active&&!d.error,"R15_DC_NEGATIVE_INITIAL_ACCEPT");
        d.dc_word_valid=1;d.dc_index=0;d.dc_word=uint32_t(INITIAL[0][0]);
        if(mode==2)d.dc_owner^=uint64_t(1)<<55;
        if(mode==3)d.dc_current_session=78;
        if(mode==4)d.dc_index=1;
        if(mode==5)d.dc_word=BASES[0];
        if(mode==8){d.dc_word_valid=0;d.dc_commit=1;}
        if(mode==9){d.dc_word_valid=0;d.dc_cancel=1;d.dc_lease++;}
        edge(d);dc_failclosed(d);cases++;
    }
    // Reset exactly while the previous accepted physical RAM ACK is pending.
    dc_reset(d);dc_begin0(d);edge(d);d.dc_begin=0;
    d.dc_word_valid=1;d.dc_index=0;d.dc_word=uint32_t(INITIAL[0][0]);edge(d);
    need(d.dc_applied==1&&!d.error,"R15_DC_ONE_RAM_WRITE");dc_reset(d);
    for(unsigned j=0;j<8;j++){clear(d);edge(d);need(!d.error&&!d.dc_loaded&&!d.canonical_ready&&!d.read_valid,"R15_DC_RESET_ACK_QUIET");}
    need(cases==10,"R15_DC_FAULT_CASES");
    std::cout<<"R15_DIRECT_COLD_FAULT_PASS cases=10 reset_pending_ack=1 recovery_normal_follows=1\n";
}
