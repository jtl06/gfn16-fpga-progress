#include "Vgenefer_stream27_shared_warm_aw8_p16_f0_v1.h"
#include "verilated.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using DUT=Vgenefer_stream27_shared_warm_aw8_p16_f0_v1;
constexpr unsigned N=256,P=16,T=N/P,PRIME=104857601;
constexpr unsigned FIRST=143,SINK=144,INTERVAL=187,CORRECTION=205;
using Image=std::array<uint32_t,N>;
using Corrections=std::array<int32_t,P>;
static void need(bool ok,const std::string& s){if(!ok)throw std::runtime_error(s);}
static unsigned reverse4(unsigned x){unsigned y=0;for(unsigned k=0;k<4;++k){y=2*y+(x&1);x>>=1;}return y;}
struct Frame{
    unsigned start,correction,epoch;
    uint32_t base;
    Image digits{};
    Corrections c0{},c1{};
    Image expected{};
};
static Frame frame(unsigned kind,unsigned start=0,unsigned correction=0,unsigned epoch=0){
    Frame f{start,correction,epoch,1000000000};
    uint32_t state=0x1234abcd+kind;
    for(unsigned j=0;j<N;++j){
        state=1664525*state+1013904223;
        if(kind==1)f.digits[j]=(j==255 || j==3)?1:0;
        else if(kind>=2)f.digits[j]=state%f.base;
    }
    for(unsigned k=0;k<P;++k){
        if(kind>=2){f.c0[k]=int32_t(k%5)-2;f.c1[k]=int32_t(k%3)-1;}
        if(kind==3){f.c0[k]=(k&1)?999999999:-999999999;f.c1[k]=(k&1)?896:-896;}
    }
    // Independent signed negacyclic schoolbook; no emitted roots/NTT model.
    std::array<int64_t,N> expanded{};
    for(unsigned j=0;j<N;++j)expanded[j]=f.digits[j];
    for(unsigned k=0;k<P;++k){expanded[k*T]+=f.c0[k];expanded[k*T+1]+=f.c1[k];}
    for(unsigned a=0;a<N;++a)for(unsigned b=0;b<N;++b){
        int64_t x=expanded[a]%PRIME,y=expanded[b]%PRIME;
        if(x<0)x+=PRIME;if(y<0)y+=PRIME;
        uint32_t value=uint64_t(x)*uint64_t(y)%PRIME;
        unsigned index=(a+b)%N;
        uint32_t term=(a+b>=N && value)?PRIME-value:value;
        uint32_t sum=f.expected[index]+term;
        f.expected[index]=sum>=PRIME?sum-PRIME:sum;
    }
    return f;
}
template<class Wide>static uint32_t unpack(const Wide& words,unsigned lane){
    unsigned bit=27*lane,word=bit/32,shift=bit%32;
    uint64_t pair=words[word];if(word+1<(P*27+31)/32)pair|=uint64_t(words[word+1])<<32;
    return uint32_t(pair>>shift)&((1u<<27)-1);
}
static void clear_inputs(DUT& d){
    d.in_slot_valid=0;d.frame_start=0;d.correction_valid=0;d.context_enabled=1;
    d.generation_in=7;d.live_generation=7;d.base_in=1000000000;
    d.epoch_in=0;d.correction_epoch=0;d.correction_generation=7;
    for(unsigned j=0;j<P;++j){d.data_in[j]=0;d.c0_in[j]=0;d.c1_in[j]=0;}
}
static void reset(DUT& d){
    clear_inputs(d);d.clk=0;d.rst_n=0;d.eval();d.clk=1;d.eval();
    need(!d.out_slot_valid && !d.commit_valid && !d.out_error && !d.owner_count,"S4_RESET");
    d.clk=0;d.rst_n=1;d.eval();
}
struct Counts{unsigned cases=0,frames=0,physical=0,words=0,eligible=0,commits=0,peak=0;};
static void run(DUT& d,const std::vector<Frame>& frames,Counts& counts,bool enabled=true,bool live=true){
    reset(d);unsigned last=0;for(const auto& f:frames)last=std::max(last,f.start+SINK+T+1);
    for(unsigned tick=0;tick<last;++tick){
        d.clk=0;clear_inputs(d);d.context_enabled=enabled;d.live_generation=live?7:8;
        unsigned starts=0,corrections=0;
        for(const auto& f:frames){
            if(tick>=f.start && tick<f.start+T){
                d.in_slot_valid=1;d.frame_start=tick==f.start;d.epoch_in=f.epoch;d.base_in=f.base;
                for(unsigned lane=0;lane<P;++lane)d.data_in[lane]=f.digits[reverse4(lane)*T+tick-f.start];
                starts+=tick==f.start;
            }
            if(tick==f.correction){
                d.correction_valid=1;d.correction_epoch=f.epoch;
                for(unsigned lane=0;lane<P;++lane){d.c0_in[lane]=uint32_t(f.c0[lane]);d.c1_in[lane]=uint32_t(f.c1[lane]);}
                ++corrections;
            }
        }
        d.eval();need(d.frame_accept==starts && d.correction_accept==corrections,"S4_ADMISSION tick="+std::to_string(tick));
        counts.frames+=starts;
        d.clk=1;d.eval();
        need(!d.out_error,"S4_ERROR tick="+std::to_string(tick));
        need(d.cycle_count==tick+1,"S4_CYCLE_COUNTER");
        counts.peak=std::max(counts.peak,unsigned(d.owner_count));
        const Frame* physical=nullptr;const Frame* committed=nullptr;
        for(const auto& f:frames){
            if(tick>=f.start+FIRST && tick<f.start+FIRST+T)physical=&f;
            if(tick>=f.start+SINK && tick<f.start+SINK+T)committed=&f;
        }
        need(bool(d.out_slot_valid)==bool(physical),"S4_SLOT tick="+std::to_string(tick));
        need(bool(d.commit_valid)==bool(committed && enabled && live),"S4_COMMIT tick="+std::to_string(tick));
        if(physical){
            unsigned row=tick-physical->start-FIRST;
            need(d.out_frame_start==(row==0) && d.out_epoch==physical->epoch && d.generation_out==7,
                 "S4_PHYSICAL_TAG tick="+std::to_string(tick));
            need(d.output_row==row,"S4_OUTPUT_ROW tick="+std::to_string(tick));
            need(bool(d.out_eligible)==(enabled && live),"S4_ELIGIBLE tick="+std::to_string(tick));
            for(unsigned lane=0;lane<P;++lane)
                need(unpack(d.data_out,lane)==physical->expected[reverse4(lane)*T+row],
                     "S4_DATA tick="+std::to_string(tick)+" lane="+std::to_string(lane));
            ++counts.physical;counts.words+=P;counts.eligible+=enabled && live;
        }
        if(d.commit_valid){
            unsigned row=tick-committed->start-SINK;
            need(d.commit_frame_start==(row==0) && d.commit_epoch==committed->epoch && d.commit_generation==7,"S4_COMMIT_TAG");
            for(unsigned lane=0;lane<P;++lane)
                need(unpack(d.commit_data,lane)==committed->expected[reverse4(lane)*T+row],"S4_COMMIT_DATA");
            ++counts.commits;
        }
    }
    need(d.owner_count==0 && d.frame_count==frames.size(),"S4_DRAIN");++counts.cases;
}
int main(int argc,char** argv){
    try{
        VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);DUT d{&context};
        if(argc==2 && std::string(argv[1])=="--runtime-probe"){
            std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
            return context.threads()==1 && d.threads()==1?0:2;
        }
        need(argc==1,"S4_ARGUMENTS");Counts counts;
        for(unsigned kind=0;kind<3;++kind)run(d,{frame(kind)},counts);
        run(d,{frame(2),frame(3,INTERVAL,CORRECTION,1)},counts);
        run(d,{frame(2),frame(3,24,24,1)},counts);
        run(d,{frame(2)},counts,false,true);run(d,{frame(2)},counts,true,false);
        // Reset-held requests cannot produce acceptance or stale output.
        reset(d);d.rst_n=0;d.in_slot_valid=1;d.frame_start=1;d.correction_valid=1;d.eval();
        need(!d.frame_accept && !d.correction_accept && !d.out_slot_valid && !d.commit_valid,"S4_HELD_RESET");++counts.cases;
        // Admission faults are registered at their origin; the lease may be
        // accepted there, but the partial image is invalid and no next work.
        reset(d);d.in_slot_valid=1;d.frame_start=1;d.data_in[0]=d.base_in;d.eval();
        need(d.frame_accept && d.fault_pending && !d.out_error,"S4_FAULT_ORIGIN");
        d.clk=1;d.eval();need(d.out_error,"S4_FAULT_REGISTER");
        d.clk=0;d.epoch_in=1;d.eval();need(!d.frame_accept && !d.correction_accept,"S4_FAULT_STOP");++counts.cases;
        need(context.threads()==1 && d.threads()==1,"S4_THREAD_DRIFT");
        std::cout<<"S4_SHARED_AW8_PASS cases="<<counts.cases<<" frames="<<counts.frames<<" physical_rows="<<counts.physical
                 <<" physical_words="<<counts.words<<" eligible_rows="<<counts.eligible<<" commits="<<counts.commits<<" peak_owners="<<counts.peak<<"\n";
        d.final();return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}
}
