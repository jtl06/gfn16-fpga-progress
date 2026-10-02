// Actual term/root pair: direct modular-weight oracle plus independent
// origin-edge, stop/reset and full-owner/calendar fault expectations.
#include "s4_term_select_fault_config.h"
#include <verilated.h>
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
static void need(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
static uint32_t power(uint32_t a,uint64_t e){uint64_t r=1;for(;e;e>>=1,a=uint64_t(a)*a%PRIME)if(e&1)r=r*a%PRIME;return uint32_t(r);}
static unsigned reverse(unsigned x,unsigned bits){unsigned y=0;for(unsigned i=0;i<bits;++i)y=(y<<1)|((x>>i)&1);return y;}
template<class W>static void pack(W& value,unsigned lane,uint32_t x){
    unsigned bit=lane*27,word=bit/32,shift=bit%32;uint64_t mask=uint64_t(0x7ffffff)<<shift;
    value[word]=(value[word]&~uint32_t(mask))|uint32_t(uint64_t(x)<<shift);
    if(shift>5)value[word+1]=(value[word+1]&~uint32_t(mask>>32))|uint32_t(uint64_t(x)>>(32-shift));
}
template<class W>static uint32_t unpack(const W& value,unsigned lane){
    unsigned bit=lane*27,word=bit/32,shift=bit%32;uint64_t x=value[word];
    if(shift>5)x|=uint64_t(value[word+1])<<32;return uint32_t(x>>shift)&0x7ffffff;
}
static uint32_t coefficient(unsigned row,unsigned salt){return uint32_t((uint64_t(reverse(row,ROW_BITS)+1)*1234567+salt*76543)%PRIME);}
static uint32_t expected(unsigned row,unsigned lane,unsigned salt){
    uint64_t j=uint64_t(reverse(lane,LANE_BITS))*ROWS+reverse(row,ROW_BITS);
    uint32_t psi=power(GENERATOR,(PRIME-1)/(2*N));
    return uint64_t(coefficient(row,salt))*power(psi,2*j+1)%PRIME;
}
static void idle(DUT& d){d.seed_slot=0;d.seed_start=0;d.seed_owner=0;d.seed_row=0;
    d.pointwise_slot=0;d.pointwise_start=0;d.pointwise_owner=0;d.pointwise_row=0;
    d.quarantine=0;d.debug_drop_select=0;for(unsigned w=0;w<WORDS;++w){d.seed_coeff[w]=0;d.next_coeff[w]=0;}}
static void same(const DUT& d){
    need(d.parent_term_slot==d.term_slot && d.parent_term_start==d.term_start &&
         d.parent_term_owner==d.term_owner && d.parent_term_row==d.term_row &&
         d.parent_cache_ready==d.cache_ready && d.parent_cache_owner==d.cache_owner &&
         d.parent_out_error==d.out_error && d.parent_fault_pending==d.fault_pending,
         "S4_TERM_SELECT_QUALIFIED_PUBLIC_EQUIVALENCE");
    for(unsigned w=0;w<WORDS;++w)need(d.parent_term_data[w]==d.term_data[w],"S4_TERM_SELECT_SAMPLED_PAYLOAD_EQUIVALENCE");
}
static void edge(DUT& d,bool compare=true){d.clk=0;d.eval();if(compare)same(d);d.clk=1;d.eval();if(compare)same(d);}
static void reset(DUT& d){d.clk=0;idle(d);d.rst_n=0;d.eval();
    need(!d.term_slot && !d.cache_ready && !d.out_error,"S4_TERM_SELECT_ASYNC_RESET_VALIDITY");
    edge(d);d.clk=0;d.rst_n=1;d.eval();}
static void row_inputs(DUT& d,unsigned tick,uint32_t owner,unsigned salt){
    idle(d);d.seed_owner=owner;d.pointwise_owner=owner;
    if(tick<4){d.seed_slot=1;d.seed_start=tick==0;d.seed_row=tick;
        for(unsigned lane=0;lane<LANES;++lane)pack(d.seed_coeff,lane,coefficient(tick,salt));}
    if(tick>=PW_FIRST && tick<PW_FIRST+ROWS){unsigned row=tick-PW_FIRST;
        d.pointwise_slot=1;d.pointwise_start=row==0;d.pointwise_row=row;
        for(unsigned lane=0;lane<LANES;++lane)pack(d.next_coeff,lane,coefficient((row+4)%ROWS,salt));}
}
static void word_oracle(const DUT& d,unsigned row,uint32_t owner,unsigned salt){
    need(d.term_slot && bool(d.term_start)==(row==0) && d.term_row==row && d.term_owner==owner,
         "S4_TERM_SELECT_DIRECT_OWNER_ROW_START");
    for(unsigned lane=0;lane<LANES;++lane)need(unpack(d.term_data,lane)==expected(row,lane,salt),
        "S4_TERM_SELECT_DIRECT_WEIGHT row="+std::to_string(row)+" lane="+std::to_string(lane));
}
struct Counts{unsigned cases=0,frames=0,rows=0,faults=0,legal_origin=0,resets=0,stops=0;};
static void normal(DUT& d,Counts& c,uint32_t owner,unsigned salt,bool mutation=false){
    unsigned seen=0;
    for(unsigned tick=0;tick<PW_FIRST+ROWS+8;++tick){
        d.clk=0;row_inputs(d,tick,owner,salt);
        if(mutation && tick==PW_FIRST+4)d.debug_drop_select=1;
        d.eval();same(d);need(!d.out_error && !d.fault_pending,"S4_TERM_SELECT_NORMAL_PREEDGE");
        edge(d,!mutation || tick!=PW_FIRST+4);
        need(!d.out_error,"S4_TERM_SELECT_NORMAL_REGISTERED_FAULT");
        bool occupied=tick>=PW_FIRST && tick<PW_FIRST+ROWS;
        need(bool(d.term_slot)==occupied,"S4_TERM_SELECT_REGISTERED_CALENDAR");
        if(occupied){unsigned row=tick-PW_FIRST;
            if(mutation && row==4){
                need(d.term_owner==owner && d.term_row==4 && unpack(d.term_data,0)!=expected(4,0,salt),
                     "S4_TERM_SELECT_TYPED_MUTANT_NOT_OBSERVED");
                std::cerr<<"S4_TERM_SELECT_TYPED_BYPASS row=4 lane=0 direct-mismatch\n";return;
            }
            word_oracle(d,row,owner,salt);++seen;
        }
    }
    need(seen==ROWS,"S4_TERM_SELECT_FIXED_NORMAL_ROWS");++c.cases;++c.frames;c.rows+=seen;
}
static void failed_tail(DUT& d){for(unsigned i=0;i<16;++i){idle(d);d.seed_slot=1;d.seed_start=1;
    d.pointwise_slot=1;d.pointwise_start=1;edge(d);
    need(d.out_error && !d.term_slot && !d.cache_ready,"S4_TERM_SELECT_STICKY_QUIET16");}}
static void fault(DUT& d,Counts& c,unsigned kind){
    reset(d);uint32_t owner=0x123405;unsigned salt=3;
    unsigned target=kind==3?PW_FIRST:PW_FIRST+5;
    for(unsigned tick=0;tick<=target;++tick){
        d.clk=0;row_inputs(d,tick,owner,salt);
        if(tick==target){
            if(kind==0){d.pointwise_slot=0;d.pointwise_start=0;}
            if(kind==1)d.pointwise_owner=owner^1; // same bank, different full generation
            if(kind==2)d.pointwise_row=6;        // cached/expected row mismatch
            if(kind==3){d.seed_slot=1;d.seed_start=1;d.seed_row=0;d.seed_owner=owner^256;
                for(unsigned lane=0;lane<LANES;++lane)pack(d.seed_coeff,lane,coefficient(0,salt));}
        }
        d.eval();same(d);need(!d.out_error && bool(d.fault_pending)==(tick==target),"S4_TERM_SELECT_GENUINE_FAULT_ORIGIN");
        edge(d);need(bool(d.out_error)==(tick==target),"S4_TERM_SELECT_REGISTERED_FAULT_EDGE");
        if(tick==target && kind==3){word_oracle(d,0,owner,salt);++c.legal_origin;}
    }
    failed_tail(d);++c.cases;++c.faults;
}
static void reset_pending(DUT& d,Counts& c,unsigned age){
    reset(d);for(unsigned tick=0;tick<age;++tick){row_inputs(d,tick,0x523408,2);edge(d);need(!d.out_error,"S4_TERM_SELECT_RESET_BASELINE");}
    reset(d);for(unsigned i=0;i<16;++i){idle(d);edge(d);need(!d.term_slot && !d.cache_ready && !d.out_error,"S4_TERM_SELECT_RESET_STALE_TAIL");}
    ++c.cases;++c.resets;normal(d,c,0x723409,4);
}
static void stop_window(DUT& d,Counts& c){
    reset(d);for(unsigned tick=0;tick<PW_FIRST+4;++tick){row_inputs(d,tick,0x92340a,6);edge(d);need(!d.out_error,"S4_TERM_SELECT_STOP_BASELINE");}
    d.clk=0;row_inputs(d,PW_FIRST+4,0x92340a,6);d.quarantine=1;d.eval();same(d);
    need(d.monitor_data_select && !d.monitor_product_slot && d.monitor_data_bypass,
         "S4_TERM_SELECT_STOPPED_RAW_SELECTION_ACTUALLY_OBSERVED");
    for(unsigned i=0;i<16;++i){idle(d);d.quarantine=1;edge(d);
        need(!d.term_slot && !d.cache_ready && !d.out_error,"S4_TERM_SELECT_STOPPED_SELECTION_NOT_SAMPLED");}
    ++c.cases;++c.stops;reset(d);normal(d,c,0xb2340b,7);
}
static void footer(const Counts& c){
    need(c.cases==13 && c.frames==6 && c.rows==6*ROWS && c.faults==4 && c.legal_origin==1 && c.resets==2 && c.stops==1,
         "S4_TERM_SELECT_FIXED_SCENARIO_COUNTS");
    std::cout<<"S4_TERM_SELECT_FAULT_PASS aw=8 p=16 field=1 cases=13 normal_frames=6 normal_rows="<<6*ROWS
        <<" normal_words="<<6*N<<" genuine_faults=4 legal_origin_terms=1 reset_aborts=2 quarantine_windows=1 stopped_selection_seen=1 quiet_tail=16\n";
}
int main(int argc,char** argv){try{
    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);DUT d{&context};
    if(argc==2 && std::string(argv[1])=="--runtime-probe"){
        std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
        return context.threads()==1 && d.threads()==1?0:2;}
    bool negative=argc==2 && std::string(argv[1])=="--negative-bypass";need(argc==1 || negative,"S4_TERM_SELECT_ARGUMENTS");
    Counts c;reset(d);normal(d,c,0x123401,1);normal(d,c,0x323402,2);normal(d,c,0x523503,3);
    for(unsigned kind=0;kind<4;++kind)fault(d,c,kind);
    reset_pending(d,c,2);reset_pending(d,c,PW_FIRST+4);stop_window(d,c);footer(c);
    if(negative){reset(d);normal(d,c,0x123405,3,true);d.final();return 41;}
    d.final();return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
