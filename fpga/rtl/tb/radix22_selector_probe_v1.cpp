// Native selector-only token oracle; no NTT/root-field arithmetic or HDL on Mac.
#include "Vradix22_selector_probe_v1.h"
#include "verilated.h"
#include "native_runtime_context_v1.h"
#include <cstdint>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#ifndef N1_SELECTOR_MODE
#define N1_SELECTOR_MODE 2
#endif
static constexpr unsigned mode=N1_SELECTOR_MODE,mask=(1u<<27)-1;
static void require(bool v,const char* error){if(!v)throw std::runtime_error(error);}
static uint32_t token(uint32_t seed,unsigned word,unsigned salt){
    uint32_t x=seed+0x9e3779b9u*(word+1)+salt*0x85ebca6bu;
    x^=x>>16;x*=0x7feb352du;x^=x>>15;x*=0x846ca68bu;x^=x>>16;return x&mask;
}
template<class T>static void fill(T& data,unsigned bits,unsigned words,uint32_t seed,unsigned salt){
    for(unsigned i=0;i<(bits+31)/32;i++)data[i]=0;
    for(unsigned w=0;w<words;w++){
        unsigned bit=w*27,index=bit/32,shift=bit%32;uint32_t value=token(seed,w,salt);
        data[index]|=value<<shift;if(shift>5)data[index+1]|=value>>(32-shift);
    }
}
template<class T>static uint32_t word(const T& data,unsigned w){
    unsigned bit=w*27,index=bit/32,shift=bit%32;uint64_t value=data[index];
    if(shift>5)value|=uint64_t(data[index+1])<<32;
    return uint32_t(value>>shift)&mask;
}
static unsigned fold(unsigned a){return (a^(a>>7)^(a>>14))&127;}
static unsigned base(unsigned high,unsigned number){
    unsigned varying=0;
    for(unsigned coordinate=0;coordinate<7;coordinate++){
        unsigned bit=coordinate;
        if(coordinate==high%7)bit=high;
        else if(mode!=0 && coordinate==(high-1)%7)bit=high-1;
        varying|=1u<<bit;
    }
    unsigned result=0,source=0;
    for(unsigned bit=0;bit<16;bit++)if(!(varying&(1u<<bit))){result|=((number>>source)&1u)<<bit;source++;}
    return result;
}
struct Packet{unsigned pass,pattern,orientation,xors,root_mask,inverse;uint32_t seed;bool legal;};
static unsigned data_bank(unsigned lane,unsigned index,unsigned p){
    unsigned value=0,j=0,low=(p+6)%7;
    for(unsigned b=0;b<7;b++)if(b!=p && (mode==0 || b!=low)){value|=((lane>>j)&1u)<<b;j++;}
    if(mode==0)return value|(index<<p);
    return value|((index>>1)<<p)|((index&1u)<<low);
}
static unsigned data_word(unsigned bank,unsigned p){
    unsigned lane=0,j=0,low=(p+6)%7;
    for(unsigned b=0;b<7;b++)if(b!=p && (mode==0 || b!=low)){lane|=((bank>>b)&1u)<<j;j++;}
    return mode==0?lane*2+((bank>>p)&1u):lane*4+(((bank>>p)&1u)<<1)+((bank>>low)&1u);
}
static uint32_t expected_root(const Packet& q,unsigned out){
    if(mode==0){
        if(out>=64)return 0;
        unsigned index=out;
        for(unsigned bit=0;bit<6;bit++){
            bool b=(out>>bit)&1u,m=(q.root_mask>>bit)&1u,x=(q.xors>>bit)&1u;
            if(b?(!m||x):(m&&x))index^=1u<<bit;
        }
        return token(q.seed,index,3);
    }
    unsigned group=out/3,k=out%3;
    if(mode==2){
        unsigned index=q.pass==0?group*3+k:q.pass==1?96+(group/4)*3+k:120+(group/16)*3+k;
        return token(q.seed,index,3);
    }
    static constexpr unsigned offset[8]={0,96,120,126,129,132,135,138};
    unsigned streams=q.pass<3?1u<<(5-2*q.pass):1u;
    unsigned stream=(q.pass<3?group>>(2*q.pass):0u)^(q.xors&(streams-1));
    return token(q.seed,q.inverse*141+offset[q.pass]+3*stream+k,3);
}
int main(int argc,char** argv){
    try{
        VerilatedContext context;gfn16_runtime::configure(context,argc,argv);
        Vradix22_selector_probe_v1 d(&context);
        if(argc==2 && std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
        bool negative=argc==2 && std::string(argv[1])=="--negative-selector";
        require(argc==1 || negative,"N1_SELECTOR_ARGUMENTS");
        require(gfn16_runtime::matches(context,d),"N1_SELECTOR_THREADS");
        std::optional<Packet> pending;unsigned responses=0,aborts=0,faults=0;
        auto tick=[&](std::optional<Packet> next){
            uint32_t old_read[128],old_write[128],old_root[96];
            bool old_valid=d.out_valid,old_fault=d.out_fault;
            for(unsigned i=0;i<128;i++){old_read[i]=word(d.read_result,i);old_write[i]=word(d.write_result,i);}
            for(unsigned i=0;i<96;i++)old_root[i]=word(d.root_result,i);
            d.in_valid=next.has_value();
            if(next){const auto& q=*next;d.pattern=q.pattern;d.pass_sel=q.pass;d.orientation=q.orientation;
                d.root_xor=q.xors;d.root_mask=q.root_mask;d.inverse=q.inverse;
                fill(d.data_payload,3456,128,q.seed,1);fill(d.write_payload,3456,128,q.seed,2);fill(d.root_payload,7614,282,q.seed,3);}
            d.clk=0;d.eval();
            if(d.rst_n){
                require(bool(d.out_valid)==old_valid && bool(d.out_fault)==old_fault,"N1_SELECTOR_FALL_EDGE_HOLD");
                for(unsigned i=0;i<128;i++)require(word(d.read_result,i)==old_read[i] && word(d.write_result,i)==old_write[i],"N1_SELECTOR_FALL_EDGE_HOLD");
                for(unsigned i=0;i<96;i++)require(word(d.root_result,i)==old_root[i],"N1_SELECTOR_FALL_EDGE_HOLD");
            }
            d.clk=1;d.eval();
            if(!d.rst_n){require(!d.out_valid && !d.out_fault,"N1_SELECTOR_RESET");pending.reset();return;}
            bool valid=pending && pending->legal,fault=pending && !pending->legal;
            require(bool(d.out_valid)==valid,"N1_SELECTOR_VALID");require(bool(d.out_fault)==fault,"N1_SELECTOR_FAULT");
            if(fault)faults++;
            if(valid){const auto& q=*pending;unsigned degree=mode==0?2:4;
                for(unsigned i=0;i<128;i++){
                    unsigned b=data_bank(i/degree,(i%degree)^(q.orientation&(degree-1)),q.pattern);
                    require(word(d.read_result,i)==token(q.seed,b,1),"N1_SELECTOR_MISMATCH");
                    unsigned w=data_word(i,q.pattern),wi=(w/degree)*degree+((w%degree)^(q.orientation&(degree-1)));
                    require(word(d.write_result,i)==token(q.seed,wi,2),"N1_SELECTOR_MISMATCH");
                }
                for(unsigned i=0;i<96;i++){
                    uint32_t expected=expected_root(q,i);
                    if(negative && responses==0 && i==0)expected^=1;
                    require(word(d.root_result,i)==expected,"N1_SELECTOR_MISMATCH");
                }
                responses++;
            }
            pending=next;
        };
        d.rst_n=0;tick({});d.rst_n=1;tick({});
        for(unsigned pass=0;pass<8;pass++)for(unsigned inverse=0;inverse<2;inverse++)for(unsigned number=0;number<512;number++){
            unsigned high=2*pass+1,b=fold(base(high,number)),p=high%7,lo=(high-1)%7;
            unsigned orientation=mode==0?((b>>p)&1u):(((b>>p)&1u)<<1)|((b>>lo)&1u);
            unsigned streams=pass<3?1u<<(5-2*pass):1u;
            unsigned xors=mode==0?(number^pass)&63u:pass<3?(b>>(high+1))&(streams-1):0u;
            unsigned root_mask=mode==0?(number>>3)&63u:63u;
            tick(Packet{pass,p,orientation,xors,root_mask,inverse,0x223100u+pass*4096+inverse*512+number,true});
            if(number%17==0)tick({});
        }
        tick({});tick({});require(responses==8192,"N1_SELECTOR_COVERAGE");
        for(unsigned age=0;age<4;age++){
            tick(Packet{0,1,0,0,0,0,0xf100u+age,true});d.rst_n=0;tick({});d.rst_n=1;tick({});tick({});aborts++;
        }
        tick(Packet{0,7,0,0,0,0,1,false});tick({});tick({});require(faults==1 && aborts==4,"N1_SELECTOR_COVERAGE");
        std::cout<<"N1_SELECTOR_PASS mode="<<mode<<" cases=8192 responses="<<responses<<" aborts="<<aborts<<" faults="<<faults<<" threads="<<context.threads()<<"\n";
        return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}
}
