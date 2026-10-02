// Independent flat-memory block oracle; native-only AW5/8, never full N.
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#include <verilated.h>
#include "Vgenefer_anext_a10_block_probe_v1.h"
#ifndef A10_AW
#define A10_AW 5
#endif
#ifndef A10_P
#define A10_P 104857601
#define A10_G 3
#endif
constexpr unsigned AW=A10_AW,N=1u<<AW,T=N/16;
constexpr uint32_t P=A10_P;
static_assert(AW==5 || AW==8,"small independent probe only");
static void need(bool value,const std::string& why){if(!value)throw std::runtime_error(why);}
static uint32_t power(uint32_t a,uint64_t k){uint32_t v=1;while(k){if(k&1)v=uint64_t(v)*a%P;a=uint64_t(a)*a%P;k>>=1;}return v;}
static unsigned reverse(unsigned x){unsigned y=0;for(unsigned j=0;j<AW;++j){y=(y<<1)|(x&1);x>>=1;}return y;}
static unsigned bank(unsigned a){unsigned b=0;for(unsigned j=0;j<AW;++j)b^=((a>>j)&1)<<(j%7);return b;}
int main(int argc,char** argv){try{
    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
    Vgenefer_anext_a10_block_probe_v1 d{&context};
    if(argc==2 && std::string(argv[1])=="--runtime-probe"){
        std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
        return context.threads()==1 && d.threads()==1 ? 0 : 2;
    }
    need(argc==1,"A10_BLOCK_ARGS");
    std::vector<uint32_t> flat(N);unsigned events=0;
    auto tick=[&](){
        const bool eligible=d.rst_n && d.block_read_valid;
        const unsigned offset=d.block_read_offset_out,mask=d.block_read_mask_out;
        std::array<uint32_t,16> words{};for(unsigned j=0;j<16;++j)words[j]=d.block_read_words[j];
        d.clk=0;d.eval();d.clk=1;d.eval();
        need(bool(d.consumed_valid)==eligible,"A10_BLOCK_E1_VALID");
        if(eligible){
            need(d.consumed_offset==offset && d.consumed_mask==mask,"A10_BLOCK_E1_METADATA");
            for(unsigned j=0;j<16;++j)need(d.consumed_words[j]==words[j],"A10_BLOCK_E1_PAYLOAD");
        }
    };
    auto quiet=[&](){
        d.block_read_en=0;d.block_write_en=0;d.block_external_conflict=0;
        d.legacy_load_we=0;d.legacy_read_en=0;d.legacy_vector_load_we=0;d.legacy_vector_read_en=0;
        d.profile_begin=0;d.profile_we=0;d.profile_commit=0;d.profile_abort=0;d.start=0;
    };
    auto reset=[&](){quiet();d.rst_n=0;tick();need(!d.block_read_valid && !d.consumed_valid && !d.profile_loaded,"A10_BLOCK_RESET");d.rst_n=1;tick();};
    d.size_log2=AW;d.profile_size_log2=AW;d.profile_modulus=P;d.profile_format=3;
    d.scale=0;d.op=0;d.inverse=0;d.dif=0;d.root_phase=1;reset();
    auto event=[&](bool re,bool we,unsigned ro,unsigned wo,unsigned rm,unsigned wm,
                   const std::array<uint32_t,16>& words,bool enable=true){
        d.block_read_en=re;d.block_write_en=we;d.block_read_offset=ro;d.block_write_offset=wo;
        d.block_read_mask=rm;d.block_write_mask=wm;for(unsigned j=0;j<16;++j)d.block_write_words[j]=words[j];
        bool canonical=true;for(unsigned j=0;j<16;++j)if((wm>>j&1) && words[j]>=P)canonical=false;
        const bool legal=enable && (!re || ro<T) && (!we || wo<T) && (!we || canonical) && !(re && we && ro==wo && (rm&wm));
        std::array<uint32_t,16> expected{};if(re && legal)for(unsigned j=0;j<16;++j)expected[j]=flat[j*T+ro];
        tick();++events;
        need(bool(d.block_error)==bool((re||we)&&!legal),"A10_BLOCK_ATOMIC_ERROR");
        need(bool(d.block_read_valid)==bool(re&&legal),"A10_BLOCK_E0_VALID");
        need(d.block_read_mask_out==(re&&legal?rm:0),"A10_BLOCK_E0_MASK");
        if(re&&legal){need(d.block_read_offset_out==ro,"A10_BLOCK_E0_OFFSET");for(unsigned j=0;j<16;++j)if(rm>>j&1)need(d.block_read_words[j]==expected[j],"A10_BLOCK_FLAT_READ");}
        if(re||we)need(!d.legacy_read_valid && !d.legacy_vector_read_valid,"A10_BLOCK_LEGACY_LEAK");
        if(we&&legal)for(unsigned j=0;j<16;++j)if(wm>>j&1)flat[j*T+wo]=words[j];
    };
    std::array<uint32_t,16> words{};
    auto fill=[&](){for(unsigned offset=0;offset<T;++offset){for(unsigned j=0;j<16;++j)words[j]=(j*T+offset)*12345u%P;event(false,true,0,offset,0,65535,words);}quiet();tick();};
    auto check=[&](){for(unsigned offset=0;offset<T;++offset)event(true,false,offset,0,65535,0,words);quiet();tick();};
    fill();check(); // Cold ordinary-residue prefill does not require a header.
    for(unsigned j=0;j<16;++j)words[j]=P-1-j;
    event(true,true,0,1,65535,65535,words);check();
    if(AW==8){bool shared=false;for(unsigned r=0;r<16;++r)for(unsigned w=0;w<16;++w)
        shared|=bank(r*T)==bank(w*T+1) && (r*T>>7)!=(w*T+1>>7);need(shared,"A10_BLOCK_MULTIR0W_NOT_EXERCISED");}
    event(true,true,0,0,0x5555,0xaaaa,words);check();
    event(true,true,0,0,1,1,words);check();
    event(true,true,T,0,65535,65535,words);event(true,true,0,T,65535,65535,words);check();
    words[0]=P;event(true,true,0,1,65535,65535,words);check();
    words[0]=0xffffffffu;event(false,true,0,1,0,0xfffe,words);check();
    words[0]=1;
    for(unsigned mode=0;mode<5;++mode){quiet();d.legacy_load_we=mode==0;d.legacy_read_en=mode==1;
        d.legacy_vector_load_we=mode==2;d.legacy_vector_read_en=mode==3;d.block_external_conflict=mode==4;
        event(true,true,0,1,65535,65535,words,false);quiet();tick();check();}
    quiet();d.profile_begin=1;event(true,true,0,1,65535,65535,words,false);
    need(d.profile_error && !d.profile_loaded && !d.profile_loading,"A10_BLOCK_HEADER_CONFLICT");quiet();tick();check();
    quiet();d.profile_begin=1;tick();need(d.profile_loading,"A10_BLOCK_HEADER_BEGIN");quiet();
    event(true,true,0,1,65535,65535,words,false);quiet();d.profile_abort=1;tick();quiet();tick();check();
    const uint32_t r=uint64_t(1ull<<32)%P;
    const uint32_t psi=power(A10_G,(P-1)/(2*N));
    std::array<uint32_t,4> header{0x41313000u,N,uint32_t(uint64_t(r)*r%P*power(N,P-2)%P),psi};
    auto load_profile=[&](){quiet();d.profile_begin=1;tick();quiet();
        for(unsigned j=0;j<4;++j){d.profile_we=1;d.profile_addr=j;d.profile_data=header[j];tick();}
        quiet();d.profile_commit=1;tick();quiet();tick();need(d.profile_loaded && !d.profile_error,"A10_BLOCK_HEADER_COMMIT");};
    load_profile();d.start=1;event(true,true,0,1,65535,65535,words,false);
    need(d.done && d.error && !d.busy,"A10_BLOCK_START_CONFLICT");quiet();tick();
    // A pending E0 response also prevents start from outrunning its E1 sink.
    event(true,false,0,0,65535,0,words);quiet();d.start=1;tick();
    need(d.done && d.error && !d.busy,"A10_BLOCK_PENDING_READ_START");quiet();tick();
    reset();fill();load_profile();
    // An actual pending response is flushed by reset; RAM image is retained.
    event(true,false,0,0,65535,0,words);reset();check();load_profile();
    auto input=flat;std::vector<uint32_t> spectrum(N);
    for(unsigned k=0;k<N;++k)for(unsigned j=0;j<N;++j)
        spectrum[k]=(spectrum[k]+uint64_t(input[j])*power(psi,uint64_t(2*reverse(k)+1)*j))%P;
    quiet();d.start=1;tick();quiet();need(d.busy && !d.error,"A10_BLOCK_FORWARD_START");
    for(unsigned j=0;j<3;++j){event(true,true,0,1,65535,65535,words,false);quiet();}
    unsigned timeout=0;while(!d.done && timeout++<AW*((N+127)/128+9)+64)tick();
    need(d.done && !d.error && !d.busy,"A10_BLOCK_BUSY_SUPPRESSION");
    need(d.cycles==AW*((N+127)/128+9),"A10_BLOCK_UNCHANGED_WORK_CYCLES");flat=spectrum;check();
    quiet();tick();d.final();
    std::cout<<"A10_BLOCK_PASS aw="<<AW<<" field="<<P<<" blocks=16 offsets="<<T<<" e0_to_e1=1 forward=direct-small\n";
    return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
