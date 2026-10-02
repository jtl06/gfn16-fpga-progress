#define main frozen_normal_main
#include "shadow_rowwrite_v1.cpp"
#undef main
static void verify_retention(Harness& h){
    for(unsigned ctx=0;ctx<2;ctx++)for(unsigned a=0;a<256;a++){
        Inputs in;in.enabled=0;in.access=in.read=15;in.host_context=ctx;in.address=a;h.step(in);
    }
}
static void faults(Harness& h){
    normal(h);Inputs in;
    // Full-owner ordinal/epoch/generation aliases may not touch addressed RAM.
    for(uint64_t alias:{uint64_t(1),uint64_t(1)<<31,uint64_t(1)<<32,uint64_t(1)<<48}){
        in=Inputs{};in.commit=in.access=in.load=in.read=in.row_read=in.capture=15;
        in.commit_context=in.host_context=in.row_context=0;in.capture_context=1;
        in.commit_owner=in.live[0]^alias;in.row_owner=in.live[0];in.address=in.commit_address=3;
        in.commit_word=in.scalar_word=0xdeadbeefu;
        for(unsigned b=0;b<16;b++)in.capture_words[b]=word(1,b,4);h.step(in);
    }
    // Wrong context owner's exact56-bit tag is rejected despite being live elsewhere.
    in=Inputs{};in.commit=in.access=in.read=15;in.commit_owner=in.live[1];in.host_context=in.commit_context=0;in.address=3;h.step(in);
    // Stale capture blocks same-context lower row/host operations; A still copies.
    in=Inputs{};in.commit=in.capture=in.row_read=in.access=in.load=in.read=15;
    in.commit_context=0;in.capture_context=in.row_context=in.host_context=1;
    in.capture_owner=in.live[1]^(uint64_t(1)<<31);in.row_owner=in.live[1];
    in.commit_address=7;in.commit_word=0x12345678u;in.scalar_word=0xdeadbeefu;h.step(in);
    // Disabled internal read denies a cold-host load in that addressed context.
    in=Inputs{};in.enabled=2;in.row_read=in.access=in.load=in.read=15;
    in.row_context=in.host_context=0;in.row_owner=in.live[0];in.address=8;in.scalar_word=0xdeadbeefu;h.step(in);
    // Accepted commit wins over same-context dense capture and reports rejection.
    in=Inputs{};in.commit=in.capture=in.access=in.read=15;in.commit_context=in.capture_context=0;
    in.capture_owner=in.live[0];in.host_context=1;in.address=3;in.commit_address=9;in.commit_word=0x80000000u;
    for(unsigned b=0;b<16;b++)in.capture_words[b]=0xabcdef01u;h.step(in);
    verify_retention(h);
    // Full live-owner change leaves old response tag intact: wrapper can reject it.
    in=Inputs{};in.access=in.read=15;in.host_context=0;in.address=3;h.step(in);
    uint64_t previous=bits(h.d.read_owner,0,56);in=Inputs{};in.live[0]^=uint64_t(1)<<31;h.step(in);
    need(bits(h.d.read_owner,0,56)==previous && !h.d.read_valid,"SHADOW_ROW_RESPONSE_OWNER_HOLD");
    // A shared fault requires global quarantine, which kills BOTH contexts.
    in=Inputs{};in.access=in.read=15;in.host_context=0;in.address=3;h.step(in);
    for(unsigned i=0;i<3;i++){
        in=Inputs{};in.quarantine=true;in.commit=in.capture=in.row_read=in.access=in.load=in.read=15;
        in.commit_context=0;in.capture_context=in.row_context=in.host_context=1;
        in.commit_word=in.scalar_word=0xdeadbeefu;for(auto& x:in.capture_words)x=0xabcdef01u;h.step(in);
    }
    in=Inputs{};h.step(in);need(!h.d.read_valid&&!h.d.row_read_valid&&!h.d.commit_ack&&!h.d.row_write_ack,"SHADOW_ROW_NO_RESPONSE_RESURRECTION");
    verify_retention(h);
    // Asynchronous reset revokes eligibility/selector while preserving payload.
    in=Inputs{};in.row_read=in.access=in.read=15;in.row_context=1;in.host_context=0;h.step(in);
    in=Inputs{};in.reset=true;in.commit=in.capture=in.row_read=in.access=in.load=in.read=15;
    in.commit_word=in.scalar_word=0xdeadbeefu;for(auto& x:in.capture_words)x=0xabcdef01u;h.step(in);
    need(!h.d.read_context&&!h.d.row_response_context,"SHADOW_ROW_RESET_SELECTORS");
    for(unsigned g=0;g<4;g++)need(bits(h.d.read_owner,g*56,56)==0 && bits(h.d.row_response_owner,g*56,56)==0,"SHADOW_ROW_RESET_TAGS");
    in=Inputs{};h.step(in);h.step(in);verify_retention(h);
}
int main(int argc,char** argv){
    bool negative=argc==2 && std::string(argv[1])=="--negative-oracle";
    try{
        VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d(&context);
        if(argc==2 && std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
        need(argc==1 || negative,"SHADOW_ROW_FAULT_ARGUMENTS");need(gfn16_runtime::matches(context,d),"SHADOW_ROW_FAULT_THREADS");
        Harness h(context,d);
        if(negative){normal(h);h.memory[0][0][0]^=1;Inputs in;in.access=in.read=15;h.step(in);need(false,"SHADOW_ROW_NEGATIVE_MISSED");}
        else faults(h);
        std::cout<<"SHADOW_ROW_FAULT_PASS aliases=6 quarantine=global reset_retains_payload=1\n";return 0;
    }catch(const std::exception& e){
        if(negative && std::string(e.what())=="SHADOW_ROW_SIGNED96_E0")std::cerr<<"SHADOW_ROW_NEGATIVE_ORACLE_REJECT\n";
        else std::cerr<<e.what()<<"\n";
        return 1;
    }
}
