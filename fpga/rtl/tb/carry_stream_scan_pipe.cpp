#include "Vgenefer_carry_stream_scan_pipe.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <deque>
#include <iostream>
#include <random>
#include <stdexcept>
#include <type_traits>
#ifndef TEST_LANES
#define TEST_LANES 4
#endif
static constexpr unsigned W=TEST_LANES,DELAY=1+__builtin_ctz(W);
template<class T>void bit(T& word,unsigned i,bool x){
    if constexpr(std::is_integral_v<T>){uint64_t m=uint64_t(1)<<i;word=(word&~m)|(x?m:0);}
    else{uint32_t m=1u<<(i%32);word[i/32]=(word[i/32]&~m)|(x?m:0);}
}
template<class T>bool bit(const T& word,unsigned i){
    if constexpr(std::is_integral_v<T>)return (word>>i)&1;
    else return (word[i/32]>>(i%32))&1;
}
template<class T>void pack(T& word,unsigned offset,unsigned width,uint64_t value){for(unsigned i=0;i<width;i++)bit(word,offset+i,(value>>i)&1);}
template<class T>unsigned unpack(const T& word,unsigned offset,unsigned width){unsigned v=0;for(unsigned i=0;i<width;i++)v|=unsigned(bit(word,offset+i))<<i;return v;}
struct Pending{unsigned due,tag;std::array<std::array<unsigned,5>,W> prefix;};
int main(int argc,char** argv){try{
    Verilated::commandArgs(argc,argv);Vgenefer_carry_stream_scan_pipe d;
    std::mt19937_64 rng(0x5ca1cafe);std::deque<Pending> queue;unsigned checked=0,canceled=0;
    for(unsigned cycle=0;cycle<50016;cycle++){
        bool reset=cycle%257==0,valid=cycle<50000&&cycle%7!=3;
        unsigned base=cycle%4==0?2:cycle%4==1?1000000000:unsigned(rng()%999999999)+2;
        // Deliberately stable per transaction; threshold data belongs to the
        // same accepted edge as values, so arbitrary changes test alignment.
        for(unsigned k=0;k<5;k++)for(unsigned t=0;t<4;t++){
            int64_t threshold=(int64_t(t)-1)*base-int64_t(k)+2;
            pack(d.thresholds,(k*4+t)*34,34,uint64_t(threshold));
        }
        d.rst_n=!reset;d.in_valid=valid;d.mask=rng()&((1u<<W)-1);d.payload_in=cycle;
        Pending pending{cycle+DELAY,cycle,{}};std::array<unsigned,5> cumulative{0,1,2,3,4};
        for(unsigned lane=0;lane<W;lane++){
            int64_t s=int64_t(rng()&((uint64_t(1)<<33)-1));if(s&(int64_t(1)<<32))s-=int64_t(1)<<33;
            if(cycle%3==0)s=(int64_t(rng()%4)-1)*base+int64_t(rng()%7)-3;
            if(cycle%11==0)s=(int64_t(rng()%65536)-32768)*131072+int64_t(rng()%3)-1;
            if(s<-(int64_t(1)<<32))s=-(int64_t(1)<<32);
            if(s>=(int64_t(1)<<32))s=(int64_t(1)<<32)-1;
            pack(d.values,lane*33,33,uint64_t(s));std::array<unsigned,5> map;
            for(unsigned k=0;k<5;k++){
                int64_t x=s+int64_t(k)-2;
                map[k]=(d.mask>>lane&1)?(x<-int64_t(base)?0:x<0?1:x<int64_t(base)?2:x<2*int64_t(base)?3:4):k;
            }
            for(unsigned k=0;k<5;k++)cumulative[k]=map[cumulative[k]];
            pending.prefix[lane]=cumulative;
        }
        if(reset){canceled+=queue.size();queue.clear();}else if(valid)queue.push_back(pending);
        d.clk=0;d.eval();d.clk=1;d.eval();
        bool due=!queue.empty()&&queue.front().due==cycle;
        if(bool(d.out_valid)!=due)throw std::runtime_error("scan valid/latency mismatch");
        if(due){
            auto expected=queue.front();queue.pop_front();
            if(d.payload_out!=expected.tag)throw std::runtime_error("scan payload mismatch");
            for(unsigned lane=0;lane<W;lane++)for(unsigned k=0;k<5;k++)
                if(unpack(d.prefix,lane*15+k*3,3)!=expected.prefix[lane][k])throw std::runtime_error("scan transfer/prefix mismatch");
            checked++;
        }
    }
    if(!queue.empty())throw std::runtime_error("scan drain mismatch");
    std::cout<<"PASS scan lanes="<<W<<" checked="<<checked<<" canceled="<<canceled<<" delay="<<DELAY<<"\n";
}catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}}
