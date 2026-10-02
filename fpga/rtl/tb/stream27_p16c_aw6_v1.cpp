// Bounded composed probe oracle: direct x^64=-1 schoolbook square, no NTT.
#include "Vgenefer_stream27_p16c_physical_aw6_p16_f0_v1.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>

using DUT=Vgenefer_stream27_p16c_physical_aw6_p16_f0_v1;
static constexpr unsigned N=64,P=16,T=4,MOD=104857601,FIRST=85,LAST=88,DONE=89;
static unsigned events=0,physical=0,eligible=0,resets=0,aborts=0;
template<class Wide> void put(Wide &w,unsigned lane,uint32_t value){
    const unsigned bit=lane*27,word=bit/32,shift=bit%32;
    const uint64_t mask=((uint64_t(1)<<27)-1)<<shift;
    uint64_t old=w[word];if(shift+27>32)old|=uint64_t(w[word+1])<<32;
    old=(old&~mask)|(uint64_t(value)<<shift);w[word]=uint32_t(old);
    if(shift+27>32)w[word+1]=uint32_t(old>>32);
}
template<class Wide> uint32_t get(const Wide &w,unsigned lane){
    const unsigned bit=lane*27,word=bit/32,shift=bit%32;
    uint64_t value=w[word];if(shift+27>32)value|=uint64_t(w[word+1])<<32;
    return uint32_t((value>>shift)&((uint64_t(1)<<27)-1));
}
static unsigned reverse4(unsigned x){return ((x&1)<<3)|((x&2)<<1)|((x&4)>>1)|((x&8)>>3);}
static void fail(const std::string &kind,unsigned tick,const std::string &detail){
    throw std::runtime_error(kind+" tick="+std::to_string(tick)+" "+detail);
}
static std::array<uint32_t,N> oracle(const std::array<uint32_t,N> &x){
    std::array<uint32_t,N> y{};
    for(unsigned a=0;a<N;++a)for(unsigned b=0;b<N;++b){
        const unsigned k=(a+b)%N;const uint64_t product=uint64_t(x[a])*x[b]%MOD;
        y[k]=uint32_t((uint64_t(y[k])+(a+b<N ? product : MOD-product))%MOD);
    }
    return y;
}
static void edge(DUT &d){d.clk=0;d.eval();d.clk=1;d.eval();d.clk=0;d.eval();++events;}
static void run(unsigned image,int reset_at,int cancel_at,int disable_at,int bad_at){
    DUT d;d.rst_n=0;d.start=1;d.context_enabled=1;d.generation_in=7;d.live_generation=7;
    for(unsigned word=0;word<14;++word)d.data_in[word]=0;
    edge(d);++resets;
    if(d.out_slot_valid||d.ready||d.busy||d.done||d.error)fail("P16C_RESET_MISMATCH",0,"held start");
    std::array<uint32_t,N> x{};
    for(unsigned i=0;i<N;++i){
        if(image==0)x[i]=0;
        else if(image==1)x[i]=i==63 ? 1 : 0;
        else if(image==2)x[i]=MOD-1;
        else x[i]=uint32_t((uint64_t(i)*i*37+19*i+image*997)%MOD);
    }
    const auto expected=oracle(x);bool aborted=false,faulted=false;
    for(unsigned tick=0;tick<100;++tick){
        d.rst_n=reset_at<0||tick!=unsigned(reset_at);
        // Busy starts and changing unqualified generation pins must not
        // change the four accepted rows' latched owner.
        d.start=tick==0||tick==20||tick==88;
        d.generation_in=tick==0 ? 7 : 91;
        d.live_generation=cancel_at>=0&&tick>=unsigned(cancel_at) ? 8 : 7;
        d.context_enabled=!(disable_at>=0&&tick>=unsigned(disable_at));
        for(unsigned word=0;word<14;++word)d.data_in[word]=0;
        for(unsigned lane=0;lane<P;++lane){
            uint32_t value=tick<T ? x[reverse4(lane)*T+tick] : MOD-1;
            if(bad_at>=0&&tick==unsigned(bad_at)&&lane==0)value=MOD+7;
            put(d.data_in,lane,value);
        }
        d.clk=0;d.eval();
        const bool origin=bad_at>=0&&tick==unsigned(bad_at)&&tick<T&&!aborted;
        if(!aborted&&!faulted&&d.rst_n&&bool(d.fault_pending)!=origin)
            fail("P16C_PREFAULT_MISMATCH",tick,"legal/origin pending");
        edge(d);
        if(!d.rst_n){aborted=true;++resets;++aborts;}
        if(origin)faulted=true;
        const bool slot=!aborted&&!faulted&&tick>=FIRST&&tick<=LAST;
        if(bool(d.error)!=faulted)fail("P16C_ERROR_MISMATCH",tick,"registered sticky fault");
        if(bool(d.out_slot_valid)!=slot)fail("P16C_SLOT_MISMATCH",tick,"physical occupied rows");
        if(bool(d.out_frame_start)!=(slot&&tick==FIRST))fail("P16C_START_MISMATCH",tick,"physical first row");
        const bool permit=slot&&d.context_enabled&&d.live_generation==7;
        if(bool(d.out_eligible)!=permit)fail("P16C_ELIGIBLE_MISMATCH",tick,"current generation/enabled");
        if(slot){
            ++physical;eligible+=permit;
            if(d.generation_out!=7||d.output_row!=tick-FIRST)fail("P16C_OWNER_MISMATCH",tick,"generation/row");
            for(unsigned lane=0;lane<P;++lane){
                const auto wanted=expected[reverse4(lane)*T+tick-FIRST];
                if(get(d.data_out,lane)!=wanted)fail("P16C_DATA_MISMATCH",tick,"lane="+std::to_string(lane));
            }
        }
        const bool done=!aborted&&!faulted&&tick==DONE;
        if(bool(d.done)!=done)fail("P16C_DONE_MISMATCH",tick,"physical drain");
        if(faulted&&d.ready)fail("P16C_FAILSTOP_MISMATCH",tick,"ready before reload");
    }
}
int main(int argc,char **argv){
    Verilated::commandArgs(argc,argv);
    try{
        for(unsigned image=0;image<6;++image)run(image,-1,-1,-1,-1);
        for(int tick=0;tick<=90;++tick){run(3,tick,-1,-1,-1);run(4,-1,tick,-1,-1);run(5,-1,-1,tick,-1);}
        for(int tick=0;tick<4;++tick)run(3,-1,-1,-1,tick);
        std::cout<<"P16C_AW6_PASS events="<<events<<" physical="<<physical<<" eligible="<<eligible
                 <<" resets="<<resets<<" aborts="<<aborts<<"\n";
        return 0;
    }catch(const std::exception &error){std::cerr<<error.what()<<"\n";return 1;}
}
