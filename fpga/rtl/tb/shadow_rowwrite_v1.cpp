#include "Vgenefer_stream27_shadow_rowwrite_test_v1.h"
#include "verilated.h"
#include "native_runtime_context_v1.h"
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
using DUT=Vgenefer_stream27_shadow_rowwrite_test_v1;
static constexpr unsigned AW[]={5,5,8,8},P[]={8,16,8,16};
static constexpr uint64_t MASK56=(uint64_t(1)<<56)-1;
static void need(bool okay,const char* message){if(!okay)throw std::runtime_error(message);}
template<class T>static uint64_t bits(const T& x,unsigned start,unsigned width){
    uint64_t result=0;for(unsigned b=0;b<width;b++)result|=uint64_t((x[(start+b)/32]>>((start+b)%32))&1)<<b;
    return result;
}
template<class T>static void put(T& x,unsigned start,unsigned width,uint64_t value){
    for(unsigned b=0;b<width;b++){unsigned bit=start+b;uint32_t m=uint32_t(1)<<(bit%32);
        x[bit/32]=(x[bit/32]&~m)|(((value>>b)&1)?m:0);}
}
static uint32_t word(unsigned context,unsigned address,unsigned phase){
    static const uint32_t signs[]={0,1,0xffffffffu,0x80000000u,0x7fffffffu,0xfffffffeu};
    if(address<6)return signs[(address+context+phase)%6];
    return uint32_t(uint64_t(address+1)*2654435761ull+context*104729u+phase*1237u);
}
struct Inputs{
    bool reset=false,quarantine=false;
    unsigned enabled=3,access=0,load=0,read=0,row_read=0,commit=0,capture=0;
    unsigned host_context=0,commit_context=0,row_context=0,capture_context=1;
    unsigned address=0,commit_address=0,row_address=0,capture_address=0;
    uint32_t scalar_word=0,commit_word=0;
    std::array<uint32_t,16> capture_words{};
    std::array<uint64_t,2> live={0x12000300000019ull,0x3500070000002bull};
    uint64_t commit_owner=0x12000300000019ull,row_owner=0x3500070000002bull,capture_owner=0x3500070000002bull;
};
struct Snapshot{
    std::array<uint32_t,12> scalar{};
    std::array<uint32_t,64> rows{};
    std::array<uint64_t,4> scalar_tags{},row_tags{};
    unsigned read_valid,row_valid,commit_ack,capture_ack,rejected,read_context,row_context;
    bool operator==(const Snapshot& x)const{return scalar==x.scalar && rows==x.rows && scalar_tags==x.scalar_tags &&
        row_tags==x.row_tags && read_valid==x.read_valid && row_valid==x.row_valid && commit_ack==x.commit_ack &&
        capture_ack==x.capture_ack && rejected==x.rejected && read_context==x.read_context && row_context==x.row_context;}
};
static Snapshot snapshot(const DUT& d){
    Snapshot x{};for(unsigned i=0;i<12;i++)x.scalar[i]=d.read_data[i];for(unsigned i=0;i<64;i++)x.rows[i]=d.row_read_data[i];
    for(unsigned g=0;g<4;g++){x.scalar_tags[g]=bits(d.read_owner,g*56,56);x.row_tags[g]=bits(d.row_response_owner,g*56,56);}
    x.read_valid=d.read_valid;x.row_valid=d.row_read_valid;x.commit_ack=d.commit_ack;x.capture_ack=d.row_write_ack;
    x.rejected=d.rejected;x.read_context=d.read_context;x.row_context=d.row_response_context;return x;
}
class Harness{
public:
    VerilatedContext& context;DUT& d;
    std::array<std::array<std::vector<uint32_t>,2>,4> memory;
    std::array<std::array<std::vector<bool>,2>,4> known;
    unsigned edges=0,scalar_checks=0,row_checks=0,dual_writes=0;
    Harness(VerilatedContext& c,DUT& dut):context(c),d(dut){
        for(unsigned g=0;g<4;g++)for(unsigned ctx=0;ctx<2;ctx++){
            memory[g][ctx].resize(1u<<AW[g]);known[g][ctx].resize(1u<<AW[g]);
        }
        d.clk=1;d.rst_n=0;d.quarantine=0;d.host_access=d.load_we=d.read_en=d.row_read_req=d.commit_we=d.row_write_req=0;d.eval();
    }
    void step(const Inputs& in){
        Snapshot before=snapshot(d);
        d.rst_n=!in.reset;d.quarantine=in.quarantine;d.owner_enabled=in.enabled;
        for(unsigned ctx=0;ctx<2;ctx++)put(d.live_owner,ctx*56,56,in.live[ctx]&MASK56);
        d.host_access=in.access;d.load_we=in.load;d.read_en=in.read;d.host_context=in.host_context;
        d.host_addr=in.address;d.write_data=in.scalar_word;
        d.commit_we=in.commit;d.commit_context=in.commit_context;d.commit_address=in.commit_address;
        d.commit_word=in.commit_word;d.commit_owner=in.commit_owner;
        d.row_read_req=in.row_read;d.row_read_context=in.row_context;d.row_read_address=in.row_address;d.row_read_owner=in.row_owner;
        d.row_write_req=in.capture;d.row_write_context=in.capture_context;d.row_write_address=in.capture_address;d.row_write_owner=in.capture_owner;
        for(unsigned b=0;b<16;b++)d.row_write_data[b]=in.capture_words[b];
        d.eval();
        if(!in.reset && !in.quarantine)need(snapshot(d)==before,"SHADOW_ROW_PRE_EDGE_RESPONSE_LEAK");
        else need(!d.read_valid && !d.row_read_valid && !d.commit_ack && !d.row_write_ack && !d.rejected,"SHADOW_ROW_REVOKED_ELIGIBILITY");
        Snapshot before_fall=snapshot(d);d.clk=0;context.timeInc(1);d.eval();need(snapshot(d)==before_fall,"SHADOW_ROW_FALL_EDGE_LEAK");
        d.clk=1;context.timeInc(1);d.eval();edges++;
        for(unsigned g=0;g<4;g++){
            unsigned mask=1u<<g,n=1u<<AW[g],rows=n/P[g];
            bool allow=!in.reset&&!in.quarantine;
            std::array<bool,2> denied{};
            auto authorized=[&](unsigned ctx,uint64_t owner){return ((in.enabled>>ctx)&1) && owner==in.live[ctx];};
            if((in.commit&mask)&&!authorized(in.commit_context,in.commit_owner))denied[in.commit_context]=true;
            if((in.capture&mask)&&!authorized(in.capture_context,in.capture_owner))denied[in.capture_context]=true;
            if((in.row_read&mask)&&!authorized(in.row_context,in.row_owner))denied[in.row_context]=true;
            bool commit=allow&&(in.commit&mask)&&!denied[in.commit_context];
            bool capture=allow&&(in.capture&mask)&&!denied[in.capture_context]&&!(commit&&in.commit_context==in.capture_context);
            bool row=allow&&(in.row_read&mask)&&!denied[in.row_context]&&!(commit&&in.commit_context==in.row_context)&&!(capture&&in.capture_context==in.row_context);
            bool host=allow&&(in.access&mask)&&!denied[in.host_context]&&!(commit&&in.commit_context==in.host_context)&&!(capture&&in.capture_context==in.host_context)&&!(row&&in.row_context==in.host_context);
            bool scalar=host&&!(in.load&mask)&&(in.read&mask);
            bool reject=allow&&(denied[0]||denied[1]||(commit&&(in.capture&mask)&&in.commit_context==in.capture_context));
            need(bool(d.read_valid&mask)==scalar && bool(d.row_read_valid&mask)==row && bool(d.commit_ack&mask)==commit &&
                bool(d.row_write_ack&mask)==capture && bool(d.rejected&mask)==reject,"SHADOW_ROW_ACCEPTANCE_E0");
            if(commit){unsigned a=in.commit_address&(n-1);memory[g][in.commit_context][a]=in.commit_word;known[g][in.commit_context][a]=true;}
            if(capture){for(unsigned b=0;b<P[g];b++){unsigned a=b*rows+(in.capture_address&(rows-1));
                memory[g][in.capture_context][a]=in.capture_words[b];known[g][in.capture_context][a]=true;}}
            if(commit&&capture)dual_writes++;
            if(host&&(in.load&mask)){unsigned a=in.address&(n-1);memory[g][in.host_context][a]=in.scalar_word;known[g][in.host_context][a]=true;}
            if(scalar){unsigned a=in.address&(n-1);need(known[g][in.host_context][a],"SHADOW_ROW_UNKNOWN_SCALAR");
                uint32_t value=memory[g][in.host_context][a],extension=value&0x80000000u?0xffffffffu:0;
                need(d.read_data[g*3]==value && d.read_data[g*3+1]==extension && d.read_data[g*3+2]==extension,"SHADOW_ROW_SIGNED96_E0");
                need(((d.read_context>>g)&1)==in.host_context && bits(d.read_owner,g*56,56)==in.live[in.host_context],"SHADOW_ROW_SCALAR_OWNER_E0");scalar_checks++;}
            if(row){need(((d.row_response_context>>g)&1)==in.row_context && bits(d.row_response_owner,g*56,56)==in.row_owner,"SHADOW_ROW_ROW_OWNER_E0");
                for(unsigned b=0;b<P[g];b++){unsigned a=b*rows+(in.row_address&(rows-1));need(known[g][in.row_context][a],"SHADOW_ROW_UNKNOWN_ROW");
                    need(d.row_read_data[g*16+b]==memory[g][in.row_context][a],"SHADOW_ROW_NATURAL_BLOCK_E0");row_checks++;}}
        }
    }
};
static void normal(Harness& h){
    Inputs in;in.reset=true;h.step(in);in.reset=false;
    for(unsigned ctx=0;ctx<2;ctx++)for(unsigned a=0;a<256;a++){
        in=Inputs{};in.enabled=0;in.access=in.load=15;in.host_context=ctx;in.address=a;in.scalar_word=word(ctx,a,0);h.step(in);
    }
    for(unsigned a=0;a<256;a++)for(unsigned ctx=0;ctx<2;ctx++){
        in=Inputs{};in.enabled=0;in.access=in.read=15;in.host_context=ctx;in.address=a;h.step(in);
    }
    // B captures ordered raw rows while A receives its ordered scalar copy.
    for(unsigned a=0;a<256;a++){
        in=Inputs{};in.commit=15;in.commit_context=0;in.commit_address=a;in.commit_word=word(0,a,1);
        in.capture_context=1;in.capture_address=a;
        for(unsigned g=0;g<4;g++)if(a<(1u<<AW[g])/P[g])in.capture|=1u<<g;
        for(unsigned b=0;b<16;b++)in.capture_words[b]=word(1,b*32+a,2);h.step(in);
    }
    // Simultaneous row response B and host response A, tags aligned with q.
    for(unsigned a=0;a<256;a++){
        in=Inputs{};in.access=in.read=15;in.host_context=0;in.address=a;in.row_context=1;in.row_address=a;
        for(unsigned g=0;g<4;g++)if(a<(1u<<AW[g])/P[g])in.row_read|=1u<<g;h.step(in);
    }
    for(unsigned a=0;a<256;a++){
        in=Inputs{};in.access=in.read=15;in.host_context=1;in.address=a;h.step(in);
    }
    // Existing load>read and commit>row-read>host priorities at capture0.
    for(unsigned ctx=0;ctx<2;ctx++){
        in=Inputs{};in.access=in.load=in.read=15;in.host_context=ctx;in.address=3;in.scalar_word=0xffffffffu;h.step(in);
        in=Inputs{};in.access=in.read=in.row_read=15;in.host_context=in.row_context=ctx;in.row_owner=in.live[ctx];h.step(in);
        in=Inputs{};in.commit=in.row_read=in.access=in.read=15;in.commit_context=in.row_context=in.host_context=ctx;
        in.commit_owner=in.row_owner=in.live[ctx];in.commit_address=4;in.commit_word=0x80000000u;h.step(in);
        in=Inputs{};in.access=in.read=15;in.host_context=ctx;in.address=4;h.step(in);
    }
    // Dense capture wins over row/host read in its context without mixed RAM.
    in=Inputs{};in.capture=in.row_read=in.access=in.read=15;in.capture_context=in.row_context=in.host_context=1;
    for(unsigned b=0;b<16;b++)in.capture_words[b]=word(1,b,3);h.step(in);
    in=Inputs{};in.row_read=15;in.row_context=1;h.step(in);
    in=Inputs{};h.step(in);h.step(in);
    need(h.edges==1805 && h.scalar_checks==4104 && h.row_checks==720 && h.dual_writes==54,"SHADOW_ROW_NORMAL_LEDGER");
}
int main(int argc,char** argv){
    try{
        VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d(&context);
        if(argc==2 && std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
        need(argc==1,"SHADOW_ROW_ARGUMENTS");need(gfn16_runtime::matches(context,d),"SHADOW_ROW_THREADS");
        Harness h(context,d);normal(h);
        std::cout<<"SHADOW_ROW_NORMAL_PASS geometries=4 contexts=2 read_edge=E0\n";return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
