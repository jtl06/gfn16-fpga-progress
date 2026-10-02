#include "Vgenefer_stream27_term_payload_mlab_pair_v1.h"
#include "verilated.h"
#include "native_runtime_context_v1.h"
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
using DUT=Vgenefer_stream27_term_payload_mlab_pair_v1;
static constexpr unsigned LANES=16,ROWS=16,WORDS=14;
static constexpr uint32_t MOD=104857601,R=uint32_t((uint64_t(1)<<32)%MOD);
static void need(bool ok,const char* msg){if(!ok)throw std::runtime_error(msg);}
template<class W>static void lane_set(W& w,unsigned lane,uint32_t value){
    for(unsigned b=0;b<27;b++){unsigned n=lane*27+b;uint32_t mask=uint32_t(1)<<(n&31);
        w[n>>5]=(w[n>>5]&~mask)|((value&(uint32_t(1)<<b))?mask:0);}
}
template<class W>static uint32_t lane_get(const W& w,unsigned lane){
    uint32_t result=0;for(unsigned b=0;b<27;b++){unsigned n=lane*27+b;
        result|=((w[n>>5]>>(n&31))&1u)<<b;}return result;
}
static uint32_t coeff(unsigned frame,unsigned row,unsigned lane){return 1u+(frame*107+row*29+lane*83)%(MOD-1);}
static void clear(DUT& d){
    d.seed_slot=d.seed_start=d.pointwise_slot=d.pointwise_start=d.quarantine=0;
    d.seed_row=d.pointwise_row=0;d.seed_owner=d.pointwise_owner=0;d.update_R_factor=R;
    for(unsigned i=0;i<WORDS;i++)d.seed_coeff[i]=d.seed_R_roots[i]=d.next_coeff[i]=d.next_seed_R_roots[i]=0;
}
static void paired(DUT& d,bool occupied=false){
    need(d.old_status==d.new_status&&d.old_bypass==d.new_bypass,"TERM_MLAB_PAIR_STATUS");
    if(d.old_status&1u)need(d.old_term_owner==d.new_term_owner&&d.old_term_row==d.new_term_row,"TERM_MLAB_PAIR_OWNER_ROW");
    if(d.old_status&4u)need(d.old_cache_owner==d.new_cache_owner,"TERM_MLAB_PAIR_CACHE_OWNER");
    if(occupied)for(unsigned lane=0;lane<LANES;lane++)
        need(lane_get(d.old_current,lane)==lane_get(d.new_current,lane),"TERM_MLAB_PAIR_OCCUPIED_PRE_POST_READ");
    if((d.old_status&1u)&&!(d.old_status&8u))for(unsigned lane=0;lane<LANES;lane++)
        need(lane_get(d.old_term_data,lane)==lane_get(d.new_term_data,lane),"TERM_MLAB_PAIR_REGISTERED_DATA");
}
static void edge(DUT& d){d.clk=0;d.eval();paired(d,d.pointwise_slot);d.clk=1;d.eval();paired(d,d.pointwise_slot);}
static void reset(DUT& d){clear(d);d.rst_n=0;edge(d);need(!(d.old_status&13u),"TERM_MLAB_RESET_VALIDITY");d.rst_n=1;d.clk=0;d.eval();}
static unsigned frame(DUT& d,unsigned frame_index,unsigned reset_row=99){
    unsigned ctx=frame_index&1u,logical=frame_index&3u;
    uint32_t epoch=uint16_t(65534+frame_index/2),generation=(frame_index/2+1)&255u;
    uint32_t owner=(logical<<25)|(ctx<<24)|(epoch<<8)|generation;unsigned bypass=0;
    for(unsigned tick=1;tick<=42;tick++){
        clear(d);
        if(tick<=4){d.seed_slot=1;d.seed_start=tick==1;d.seed_row=tick-1;d.seed_owner=owner;
            for(unsigned lane=0;lane<LANES;lane++){lane_set(d.seed_coeff,lane,coeff(frame_index,tick-1,lane));lane_set(d.seed_R_roots,lane,R);}}
        if(tick>=16&&tick<16+ROWS){unsigned row=tick-16;
            d.pointwise_slot=1;d.pointwise_start=row==0;d.pointwise_row=row;d.pointwise_owner=owner;
            for(unsigned lane=0;lane<LANES;lane++){lane_set(d.next_coeff,lane,coeff(frame_index,row+4,lane));lane_set(d.next_seed_R_roots,lane,R);}
            d.clk=0;d.eval();paired(d,true);need(!(d.old_status&24u),"TERM_MLAB_NORMAL_PRE_FAULT");
            for(unsigned lane=0;lane<LANES;lane++)need(lane_get(d.old_current,lane)==coeff(frame_index,row,lane),"TERM_MLAB_PRE_INDEPENDENT_VALUE");
            if(d.old_bypass)bypass++;
            if(row==reset_row){reset(d);for(unsigned q=0;q<8;q++){clear(d);edge(d);need(!(d.old_status&13u),"TERM_MLAB_RESET_QUIET_TAIL");}return bypass;}
        }
        edge(d);need(!(d.old_status&24u),"TERM_MLAB_NORMAL_POST_FAULT");
        if(d.pointwise_slot){need((d.old_status&1u)&&d.old_term_owner==owner&&d.old_term_row==tick-16,"TERM_MLAB_EXACT_REGISTERED_LATENCY");
            for(unsigned lane=0;lane<LANES;lane++)need(lane_get(d.old_term_data,lane)==coeff(frame_index,tick-16,lane),"TERM_MLAB_POST_INDEPENDENT_VALUE");}
    }
    return bypass;
}
static void normal(DUT& d){
    reset(d);unsigned bypass=0;for(unsigned f=0;f<40;f++)bypass+=frame(d,f);
    need(bypass==480,"TERM_MLAB_ACTUAL_SAME_ADDRESS_BYPASS_COUNT");
    std::cout<<"TERM_MLAB_PAIR_PASS frames=40 lane_words=10240 pre_post=1 bypass=480 contexts=2 epoch_wrap=1 latency_delta=0\n";
}
static void faults(DUT& d){
    normal(d);
    for(unsigned mode=0;mode<2;mode++){
        reset(d);clear(d);
        if(mode==0){d.pointwise_slot=d.pointwise_start=1;d.pointwise_owner=1;}
        else{d.seed_slot=d.seed_start=1;d.seed_row=1;d.seed_owner=1;}
        d.clk=0;d.eval();paired(d,d.pointwise_slot);need(d.old_status&16u,"TERM_MLAB_ACTUAL_PENDING_FAULT");
        d.clk=1;d.eval();paired(d,d.pointwise_slot);need(d.old_status&8u,"TERM_MLAB_REGISTERED_FAULT");
        for(unsigned q=0;q<8;q++){clear(d);edge(d);need((d.old_status&8u)&&!(d.old_status&5u),"TERM_MLAB_STICKY_QUIET");}
    }
    reset(d);frame(d,0,3);normal(d);
    std::cout<<"TERM_MLAB_FAULT_PASS missing_cache=1 bad_seed=1 in_flight_reset=1 quiet_edges=24 recovered_lane_words=10240 raw_pending_lockstep=1\n";
}
int main(int argc,char** argv){try{
    VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d(&context);
    if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
    need(gfn16_runtime::matches(context,d),"TERM_MLAB_THREADS");
    if(argc==1)normal(d);else if(argc==2&&std::string(argv[1])=="--faults")faults(d);
    else need(false,"TERM_MLAB_ARGUMENTS");return 0;
}catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}}
