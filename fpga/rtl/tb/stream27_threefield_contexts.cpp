#include "s4_threefield_contexts_config_v1.h"
#include "verilated.h"
#include "native_runtime_context_v1.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
using I=__int128_t;using U=__uint128_t;
using Digits=std::array<uint32_t,N>;using Corrections=std::array<int32_t,P>;using Coefficients=std::array<I,N>;
static void need(bool ok,const std::string& s){if(!ok)throw std::runtime_error(s);}
static unsigned reverse_lane(unsigned x){unsigned y=0;for(unsigned k=0;k<LANE_BITS;k++){y=2*y+(x&1);x>>=1;}return y;}
static std::pair<I,uint32_t> euclidean(I value,uint32_t base){I q=value/base,r=value%base;if(r<0){r+=base;q--;}return {q,uint32_t(r)};}
struct Image{Digits digits{};Corrections c0{},c1{};};
static Coefficients effective(const Image& x){Coefficients a{};for(unsigned j=0;j<N;j++)a[j]=x.digits[j];for(unsigned b=0;b<P;b++){a[b*T]+=x.c0[b];a[b*T+1]+=x.c1[b];}return a;}
static Coefficients schoolbook(const Image& x,bool twice){auto a=effective(x);Coefficients c{};for(unsigned i=0;i<N;i++)for(unsigned j=0;j<N;j++)c[(i+j)%N]+=a[i]*a[j]*(i+j<N?1:-1);if(twice)for(auto& v:c)v*=2;return c;}
static std::array<int64_t,N> canonical(Coefficients a,uint32_t base){
    for(unsigned pass=0;pass<6;pass++){I carry=0;Digits digits{};for(unsigned j=0;j<N;j++){auto qr=euclidean(a[j]+carry,base);carry=qr.first;digits[j]=qr.second;}
        bool zero=true,max=true;for(auto d:digits){zero&=d==0;max&=d==base-1;}std::array<int64_t,N> result{};
        if((carry==1&&zero)||(carry==-1&&max)){result[0]=-1;return result;}
        if(!carry){for(unsigned j=0;j<N;j++)result[j]=digits[j];return result;}
        for(unsigned j=0;j<N;j++)a[j]=digits[j];a[0]-=carry;
    }throw std::runtime_error("S4_THREE_CTX_REFERENCE_CANONICAL_BOUND");
}
static Image blockcarry(const Coefficients& c,uint32_t base){
    Image out;Corrections low{},high{};
    for(unsigned block=0;block<P;block++){
        I previous_r1=0,previous_q2=0,previous2_q2=0,carry=0,last_r1=0,last_q2=0,last_previous_q2=0;
        for(unsigned row=0;row<T;row++){
            auto first=euclidean(c[block*T+row],base);auto second=euclidean(first.first,base);
            auto digit=euclidean(I(first.second)+previous_r1+previous2_q2+carry,base);out.digits[block*T+row]=digit.second;carry=digit.first;
            last_r1=second.second;last_q2=second.first;last_previous_q2=previous_q2;
            previous_r1=second.second;previous2_q2=previous_q2;previous_q2=second.first;
        }
        auto tail=euclidean(last_r1+last_previous_q2+carry,base);low[block]=int32_t(tail.second);high[block]=int32_t(last_q2+tail.first);
        need(tail.second<base&&I(high[block])>=-I(BOUND)&&I(high[block])<=I(BOUND),"S4_THREE_CTX_REFERENCE_BOUNDARY");
    }
    for(unsigned block=0;block<P;block++){unsigned destination=(block+1)%P;out.c0[destination]=block==P-1?-low[block]:low[block];out.c1[destination]=block==P-1?-high[block]:high[block];}
    need(canonical(c,base)==canonical(effective(out),base),"S4_THREE_CTX_REFERENCE_RESIDUE");return out;
}
struct Frame{unsigned context,generation,epoch,ordinal,start,correction;uint32_t base;bool twice;Image input,expected;Coefficients coefficients;};
static std::vector<Frame> frames(){
    std::array<Image,2> prior{};
    for(unsigned ctx=0;ctx<2;ctx++){uint32_t state=0x983ef17du+ctx*391u;for(unsigned j=0;j<N;j++){state=1664525u*state+1013904223u;prior[ctx].digits[j]=state%BASES[ctx];}
        for(unsigned b=0;b<P;b++){prior[ctx].c0[b]=int32_t((b+3*ctx)%7)-3;prior[ctx].c1[b]=int32_t((2*b+ctx)%3)-1;}}
    std::vector<Frame> result;
    for(unsigned i=0;i<FRAME_COUNT;i++){Frame f{};f.context=FRAME_CONTEXT[i];f.generation=f.context?23:11;f.epoch=FRAME_EPOCH[i];f.ordinal=FRAME_ORDINAL[i];f.start=FRAME_START[i];f.correction=FRAME_CORRECTION[i];f.base=BASES[f.context];f.twice=f.context&&(f.ordinal&1);
        f.input=prior[f.context];f.coefficients=schoolbook(f.input,f.twice);f.expected=blockcarry(f.coefficients,f.base);prior[f.context]=f.expected;result.push_back(f);}
    return result;
}
static void clear(DUT& d){d.begin_setup=d.setup_context=d.in_slot_valid=d.frame_start=d.correction_valid=d.double_in=0;d.context_in=d.correction_context=0;d.context_enabled=3;d.generation_in=d.correction_generation=11;d.live_generation=(23u<<8)|11;d.base_in=BASES[0];d.epoch_in=d.correction_epoch=0;for(unsigned b=0;b<P;b++)d.data_in[b]=d.c0_in[b]=d.c1_in[b]=0;}
static void setup(DUT& d){
    clear(d);d.clk=0;d.rst_n=0;d.eval();d.clk=1;d.eval();need(!d.config_valid&&!d.setup_done&&!d.digit_valid&&!d.boundary_valid&&!d.frame_done&&!d.out_error,"S4_THREE_CTX_RESET");d.clk=0;d.rst_n=1;d.eval();
    for(unsigned ctx=0;ctx<2;ctx++)for(unsigned k=0;k<=SETUP;k++){
        d.clk=0;clear(d);d.begin_setup=k==0;d.setup_context=ctx;d.base_in=BASES[ctx];d.generation_in=ctx?23:11;d.eval();
        need(!d.fault_pending&&!d.out_error,"S4_THREE_CTX_SETUP_PRE");d.clk=1;d.eval();need(!d.out_error,"S4_THREE_CTX_SETUP_ERROR");
        need(bool(d.setup_done)==(k==SETUP),"S4_THREE_CTX_SETUP_E98");if(k==SETUP)need(unsigned(d.setup_done_context)==ctx,"S4_THREE_CTX_SETUP_CONTEXT");
        need(unsigned(d.config_valid)==((1u<<ctx)-1u+(k==SETUP?(1u<<ctx):0u)),"S4_THREE_CTX_PROFILE_PUBLICATION");
        d.begin_setup=0;d.eval();need(!d.fault_pending,"S4_THREE_CTX_SETUP_SETTLED");
    }
}
template<class Wide>static I signed96(const Wide& data,unsigned lane){U v=U(data[3*lane])|(U(data[3*lane+1])<<32)|(U(data[3*lane+2])<<64);return data[3*lane+2]&0x80000000u?I(v)-(I(1)<<96):I(v);}
static void run(DUT& d){
    setup(d);auto plan=frames();std::vector<Image> actual(FRAME_COUNT);std::vector<std::array<bool,T>> seen(FRAME_COUNT);std::vector<bool> boundary_seen(FRAME_COUNT,false);
    std::array<unsigned,2> accepted{},completed{};unsigned coefficients=0,digits=0,pairs=0,feedback=0;
    unsigned end=plan.back().start+DONE+2;
    for(unsigned tick=0;tick<end;tick++){
        d.clk=0;clear(d);const Frame* incoming=nullptr;const Frame* correction=nullptr;unsigned input_index=0,correction_index=0;
        for(unsigned i=0;i<FRAME_COUNT;i++){const auto& f=plan[i];if(tick>=f.start&&tick<f.start+T){need(!incoming,"S4_THREE_CTX_INPUT_OVERLAP");incoming=&f;input_index=i;}if(tick==f.correction){need(!correction,"S4_THREE_CTX_CORRECTION_OVERLAP");correction=&f;correction_index=i;}}
        if(incoming){const auto& f=*incoming;unsigned row=tick-f.start;int prior=-1;for(unsigned i=0;i<input_index;i++)if(plan[i].context==f.context)prior=int(i);const Image* input=&f.input;
            if(f.ordinal){need(prior>=0&&seen[prior][row],"S4_THREE_CTX_ACTUAL_FEEDBACK_ROW_READY");input=&actual[prior];}
            d.in_slot_valid=1;d.frame_start=row==0;d.context_in=f.context;d.generation_in=f.generation;d.epoch_in=f.epoch;d.base_in=f.base;d.double_in=f.twice;
            for(unsigned l=0;l<P;l++)d.data_in[l]=input->digits[reverse_lane(l)*T+row];if(row==0&&f.ordinal)feedback++;
        }
        if(correction){const auto& f=*correction;const Image* input=&f.input;
            if(f.ordinal){int prior=-1;for(unsigned i=0;i<correction_index;i++)if(plan[i].context==f.context)prior=int(i);need(prior>=0&&boundary_seen[prior],"S4_THREE_CTX_ACTUAL_FEEDBACK_CORRECTION_READY");input=&actual[prior];}
            d.correction_valid=1;d.correction_context=f.context;d.correction_epoch=f.epoch;d.correction_generation=f.generation;
            for(unsigned b=0;b<P;b++){d.c0_in[b]=uint32_t(input->c0[b]);d.c1_in[b]=uint32_t(input->c1[b]);}
        }
        d.eval();bool starts=incoming&&tick==incoming->start;
        need(bool(d.frame_accept)==starts&&bool(d.correction_accept)==bool(correction),"S4_THREE_CTX_ADMISSION tick="+std::to_string(tick));
        need(!d.out_error&&!d.fault_pending,"S4_THREE_CTX_PRE_PENDING tick="+std::to_string(tick));
        if(starts)accepted[incoming->context]++;
        d.clk=1;d.eval();need(!d.out_error,"S4_THREE_CTX_POST_ERROR tick="+std::to_string(tick));
        d.frame_start=d.correction_valid=0;d.in_slot_valid=incoming&&tick+1<incoming->start+T;d.eval();
        need(!d.out_error&&!d.fault_pending,"S4_THREE_CTX_SETTLED_PENDING tick="+std::to_string(tick));
        const Frame *coefficient=nullptr,*digit=nullptr,*boundary=nullptr,*done=nullptr;unsigned di=0,bi=0;
        for(unsigned i=0;i<FRAME_COUNT;i++){const auto& f=plan[i];if(tick>=f.start+COEFFICIENT&&tick<f.start+COEFFICIENT+T)coefficient=&f;if(tick>=f.start+DIGIT&&tick<f.start+DIGIT+T){digit=&f;di=i;}if(tick==f.start+BOUNDARY){boundary=&f;bi=i;}if(tick==f.start+DONE)done=&f;}
        need(bool(d.coefficient_valid)==bool(coefficient),"S4_THREE_CTX_COEFFICIENT_CALENDAR tick="+std::to_string(tick));
        if(coefficient){unsigned row=tick-coefficient->start-COEFFICIENT;need(d.coefficient_row==row&&d.coefficient_start==(row==0)&&d.coefficient_context==coefficient->context,"S4_THREE_CTX_COEFFICIENT_TAG");for(unsigned b=0;b<P;b++)need(signed96(d.coefficient_data,b)==coefficient->coefficients[b*T+row],"S4_THREE_CTX_COEFFICIENT_VALUE tick="+std::to_string(tick)+" block="+std::to_string(b));coefficients+=P;}
        need(bool(d.digit_valid)==bool(digit),"S4_THREE_CTX_DIGIT_CALENDAR tick="+std::to_string(tick));
        if(digit){unsigned row=tick-digit->start-DIGIT;need(d.digit_row==row&&d.digit_start==(row==0)&&d.digit_eligible&&d.digit_context==digit->context&&d.digit_epoch==digit->epoch&&d.digit_generation==digit->generation,"S4_THREE_CTX_DIGIT_FULL_TAG");for(unsigned b=0;b<P;b++){need(d.digit_data[b]==digit->expected.digits[b*T+row],"S4_THREE_CTX_DIGIT_VALUE");actual[di].digits[b*T+row]=d.digit_data[b];}seen[di][row]=true;digits+=P;}
        need(bool(d.boundary_valid)==bool(boundary),"S4_THREE_CTX_BOUNDARY_CALENDAR tick="+std::to_string(tick));
        if(boundary){need(d.boundary_eligible&&d.boundary_context==boundary->context&&d.next_epoch==uint16_t(boundary->epoch+1)&&d.next_generation==boundary->generation,"S4_THREE_CTX_BOUNDARY_FULL_TAG");for(unsigned b=0;b<P;b++){actual[bi].c0[b]=int32_t(d.next_c0[b]);actual[bi].c1[b]=int32_t(d.next_c1[b]);need(actual[bi].c0[b]==boundary->expected.c0[b]&&actual[bi].c1[b]==boundary->expected.c1[b],"S4_THREE_CTX_BOUNDARY_VALUE");}need(canonical(effective(actual[bi]),boundary->base)==canonical(boundary->coefficients,boundary->base),"S4_THREE_CTX_ACTUAL_RESIDUE");boundary_seen[bi]=true;pairs+=P;}
        need(bool(d.frame_done)==bool(done),"S4_THREE_CTX_DONE_CALENDAR tick="+std::to_string(tick));if(done){need(d.done_context==done->context&&d.done_epoch==done->epoch,"S4_THREE_CTX_DONE_TAG");completed[done->context]++;}
    }
    need(accepted==completed&&completed[0]==3&&completed[1]==5&&feedback==6&&coefficients==FRAME_COUNT*N&&digits==coefficients&&pairs==FRAME_COUNT*P,"S4_THREE_CTX_LEDGER");
    std::cout<<"S4_THREE_CONTEXTS_PASS aw="<<AW<<" p="<<P<<" frames=8 counts=3/5 setup_profiles=2 coefficients="<<coefficients<<" digits="<<digits<<" boundary_pairs="<<pairs<<" actual_feedback_starts="<<feedback<<" intermediate_external_driver=1\n";
}
int main(int argc,char** argv){try{VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d(&context);if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);need(argc==1&&gfn16_runtime::matches(context,d),"S4_THREE_CTX_ARGUMENTS_THREADS");run(d);return 0;}catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}}
