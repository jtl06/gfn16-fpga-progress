#include "s4_two_context_field_config_v1.h"
#include "verilated.h"
#include "native_runtime_context_v1.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
static void need(bool ok,const std::string& text){if(!ok)throw std::runtime_error(text);}
#include "stream27_shared_reference_ntt_v1.h"
static unsigned reverse_lane(unsigned x){unsigned y=0;for(unsigned b=0;b<LANE_BITS;b++){y=(y<<1)|(x&1);x>>=1;}return y;}
struct Frame{
    unsigned context,generation,epoch,ordinal,start,correction,bank;
    uint32_t base;
    std::array<uint32_t,N> digits{},expected{};
    std::array<int32_t,P> c0{},c1{};
};
static std::vector<Frame> frames(){
    std::vector<Frame> result;
    for(unsigned i=0;i<FRAME_COUNT;i++){
        Frame f{};f.context=FRAME_CONTEXT[i];f.generation=f.context?23:11;f.epoch=FRAME_EPOCH[i];f.ordinal=FRAME_ORDINAL[i];
        f.start=FRAME_START[i];f.correction=FRAME_CORRECTION[i];f.bank=FRAME_BANK[i];f.base=f.context?2017:1009;
        uint32_t state=0x91e10da5u+f.context*997u+f.ordinal*1721u;
        std::vector<int64_t> expanded(N);
        for(unsigned j=0;j<N;j++){state=1664525u*state+1013904223u;f.digits[j]=state%f.base;expanded[j]=f.digits[j];}
        for(unsigned block=0;block<P;block++){
            f.c0[block]=int32_t((block+f.ordinal+3*f.context)%7)-3;
            f.c1[block]=int32_t((2*block+f.ordinal+f.context)%3)-1;
            expanded[block*T]+=f.c0[block];expanded[block*T+1]+=f.c1[block];
        }
        auto expected=ref_negacyclic_square(expanded);std::copy(expected.begin(),expected.end(),f.expected.begin());result.push_back(f);
    }
    return result;
}
template<class Wide>static uint32_t unpack(const Wide& x,unsigned lane){
    unsigned bit=27*lane,index=bit/32,shift=bit%32;uint64_t pair=x[index];
    if(index+1<(P*27+31)/32)pair|=uint64_t(x[index+1])<<32;
    return uint32_t(pair>>shift)&((1u<<27)-1);
}
static void clear(DUT& d){
    d.in_slot_valid=d.frame_start=d.correction_valid=0;d.context_in=d.correction_context=0;d.context_enabled=3;
    d.generation_in=11;d.live_generation=(23u<<8)|11;d.epoch_in=d.correction_epoch=0;d.correction_generation=11;d.base_in=1009;
    for(unsigned l=0;l<P;l++)d.data_in[l]=d.c0_in[l]=d.c1_in[l]=0;
}
static void run(DUT& d){
    ref_self_check();auto image=frames();clear(d);d.clk=0;d.rst_n=0;d.eval();d.clk=1;d.eval();
    need(!d.owner_count&&!d.out_slot_valid&&!d.commit_valid&&!d.out_error,"S4_TWO_RESET");d.clk=0;d.rst_n=1;d.eval();
    std::array<int,4> leases={-1,-1,-1,-1};std::array<unsigned,2> accepted{},committed_frames{};
    unsigned peak=0,used=0,physical=0,commits=0,words=0;
    unsigned end=image.back().start+SINK+T+2;
    for(unsigned tick=0;tick<end;tick++){
        d.clk=0;clear(d);const Frame* incoming=nullptr;const Frame* correction=nullptr;
        const Frame* pw=nullptr;const Frame* sink=nullptr;
        for(const auto& f:image){
            if(tick>=f.start && tick<f.start+T){need(!incoming,"S4_TWO_INPUT_OVERLAP");incoming=&f;}
            if(tick==f.correction){need(!correction,"S4_TWO_CORRECTION_OVERLAP");correction=&f;}
            if(tick>=f.start+PW && tick<f.start+PW+T)pw=&f;
            if(tick>=f.start+SINK && tick<f.start+SINK+T)sink=&f;
        }
        if(incoming){unsigned row=tick-incoming->start;d.in_slot_valid=1;d.frame_start=row==0;d.context_in=incoming->context;
            d.generation_in=incoming->generation;d.epoch_in=incoming->epoch;d.base_in=incoming->base;
            for(unsigned l=0;l<P;l++)d.data_in[l]=incoming->digits[reverse_lane(l)*T+row];}
        if(correction){d.correction_valid=1;d.correction_context=correction->context;d.correction_epoch=correction->epoch;d.correction_generation=correction->generation;
            for(unsigned l=0;l<P;l++){d.c0_in[l]=uint32_t(correction->c0[l]);d.c1_in[l]=uint32_t(correction->c1[l]);}}
        d.eval();
        bool starts=incoming && tick==incoming->start;
        need(bool(d.frame_accept)==starts && bool(d.correction_accept)==bool(correction),"S4_TWO_ADMISSION tick="+std::to_string(tick));
        need(!d.fault_pending&&!d.out_error,"S4_TWO_PRE_PENDING tick="+std::to_string(tick));
        unsigned pre_owners=std::count_if(leases.begin(),leases.end(),[](int i){return i>=0;});
        need(unsigned(d.owner_count)==pre_owners,"S4_TWO_PRE_OWNER_COUNT");
        if(starts){unsigned free=0;while(free<4&&leases[free]>=0)free++;need(free<4 && free==incoming->bank,"S4_TWO_LOWEST_FREE_BANK");}
        if(correction)need(unsigned(d.correction_bank)==correction->bank,"S4_TWO_CORRECTION_BANK");
        if(pw)need(unsigned(d.pointwise_bank)==pw->bank,"S4_TWO_POINTWISE_BANK tick="+std::to_string(tick));
        if(sink)need(unsigned(d.sink_bank)==sink->bank,"S4_TWO_SINK_BANK tick="+std::to_string(tick));
        for(unsigned b=0;b<4;b++)if(leases[b]>=0 && tick==image[leases[b]].start+SINK+T-1)leases[b]=-1;
        if(starts){unsigned index=unsigned(incoming-&image[0]);leases[incoming->bank]=int(index);used|=1u<<incoming->bank;accepted[incoming->context]++;}
        d.clk=1;d.eval();
        need(!d.out_error,"S4_TWO_POST_ERROR tick="+std::to_string(tick));need(d.cycle_count==tick+1,"S4_TWO_CYCLE");
        // fault_pending diagnoses the proposed next edge, not this completion.
        // Remove consumed strobes without another edge; keep a dense continuation
        // valid when the current frame has another row.
        d.frame_start=0;d.correction_valid=0;
        d.in_slot_valid=incoming && tick+1<incoming->start+T;
        d.eval();need(!d.fault_pending&&!d.out_error,"S4_TWO_QUIESCENT_PENDING tick="+std::to_string(tick));
        unsigned owners=std::count_if(leases.begin(),leases.end(),[](int i){return i>=0;});
        need(unsigned(d.owner_count)==owners,"S4_TWO_POST_OWNER_COUNT");peak=std::max(peak,owners);
        const Frame* out=nullptr;const Frame* commit=nullptr;
        for(const auto& f:image){if(tick>=f.start+FIRST && tick<f.start+FIRST+T)out=&f;if(tick>=f.start+SINK && tick<f.start+SINK+T)commit=&f;}
        need(bool(d.out_slot_valid)==bool(out)&&bool(d.commit_valid)==bool(commit),"S4_TWO_PHYSICAL_COMMIT_CALENDAR tick="+std::to_string(tick));
        if(out){unsigned row=tick-out->start-FIRST;
            need(d.out_frame_start==(row==0)&&d.out_context==out->context&&d.out_epoch==out->epoch&&d.generation_out==out->generation&&d.output_row==row&&d.out_eligible,"S4_TWO_PHYSICAL_FULL_TAG");
            for(unsigned l=0;l<P;l++)need(unpack(d.data_out,l)==out->expected[reverse_lane(l)*T+row],"S4_TWO_PHYSICAL_VALUE tick="+std::to_string(tick)+" lane="+std::to_string(l));
            physical++;words+=P;
        }
        if(commit){unsigned row=tick-commit->start-SINK;
            need(d.commit_frame_start==(row==0)&&d.commit_context==commit->context&&d.commit_epoch==commit->epoch&&d.commit_generation==commit->generation,"S4_TWO_COMMIT_FULL_TAG");
            for(unsigned l=0;l<P;l++)need(unpack(d.commit_data,l)==commit->expected[reverse_lane(l)*T+row],"S4_TWO_COMMIT_VALUE");
            if(row==0)committed_frames[commit->context]++;commits++;
        }
    }
    need(!d.owner_count&&d.frame_count==FRAME_COUNT&&accepted[0]==3&&accepted[1]==5&&committed_frames==accepted,"S4_TWO_UNEQUAL_CONTEXT_DRAIN");
    need(physical==FRAME_COUNT*T&&commits==physical&&words==FRAME_COUNT*N&&peak==EXPECTED_PEAK&&used==EXPECTED_BANK_MASK,"S4_TWO_LEDGER");
    std::cout<<"S4_TWO_CONTEXT_FIELD_PASS aw="<<AW<<" p="<<P<<" field="<<FIELD<<" frames=8 counts=3/5 physical_rows="<<physical
        <<" words="<<words<<" commits="<<commits<<" peak="<<peak<<" bank_mask="<<used<<" injected_field_only=1\n";
}
int main(int argc,char** argv){
    try{VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d(&context);
        if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
        need(argc==1,"S4_TWO_ARGUMENTS");need(gfn16_runtime::matches(context,d),"S4_TWO_THREADS");run(d);return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}
}
