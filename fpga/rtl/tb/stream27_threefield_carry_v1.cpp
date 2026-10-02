#include "s4_threefield_config_v1.h"
#include "verilated.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using I=__int128_t;using U=__uint128_t;
using Digits=std::array<uint32_t,N>;using Corrections=std::array<int32_t,P>;
using Coefficients=std::array<I,N>;
static void need(bool ok,const std::string& s){if(!ok)throw std::runtime_error(s);}
static unsigned rev4(unsigned x){unsigned y=0;for(unsigned k=0;k<4;++k){y=2*y+(x&1);x>>=1;}return y;}
static std::pair<I,uint32_t> euclidean(I v,uint32_t base){I q=v/base,r=v%base;if(r<0){r+=base;--q;}return {q,uint32_t(r)};}
static std::string decimal(I x){bool negative=x<0;U a=negative?U(-x):U(x);std::string s;do{s.push_back(char('0'+a%10));a/=10;}while(a);if(negative)s.push_back('-');std::reverse(s.begin(),s.end());return s;}
struct Image{Digits digits{};Corrections c0{},c1{};};
static Coefficients effective(const Image& x){Coefficients a{};for(unsigned j=0;j<N;++j)a[j]=x.digits[j];for(unsigned b=0;b<P;++b){a[b*T]+=x.c0[b];a[b*T+1]+=x.c1[b];}return a;}
static Coefficients schoolbook(const Image& x,bool twice){auto a=effective(x);Coefficients c{};for(unsigned i=0;i<N;++i)for(unsigned j=0;j<N;++j)c[(i+j)%N]+=a[i]*a[j]*(i+j<N?1:-1);if(twice)for(auto& v:c)v*=2;return c;}
// Ordinary serial Euclidean normalization modulo b^N+1, independent of NTT
// and the lane's reciprocal/parts schedule. Only an intermediate math check;
// this function does not satisfy the required hardware canonical readback.
static std::array<int64_t,N> canonical(Coefficients a,uint32_t base){
    for(unsigned pass=0;pass<6;++pass){I carry=0;Digits d{};for(unsigned j=0;j<N;++j){auto z=euclidean(a[j]+carry,base);carry=z.first;d[j]=z.second;}
        bool zero=true,max=true;for(auto v:d){zero&=v==0;max&=v==base-1;}
        std::array<int64_t,N> result{};
        if((carry==1 && zero)||(carry==-1 && max)){result[0]=-1;return result;}
        if(!carry){for(unsigned j=0;j<N;++j)result[j]=d[j];return result;}
        for(unsigned j=0;j<N;++j)a[j]=d[j];a[0]-=carry;
    }throw std::runtime_error("S4_CANONICAL_REFERENCE_BOUND");
}
static Image blockcarry(const Coefficients& c,uint32_t base){
    Image out;Corrections low{},high{};
    for(unsigned b=0;b<P;++b){I previous_r1=0,previous_q2=0,previous2_q2=0,carry=0,last_r1=0,last_q2=0,last_previous_q2=0;
        for(unsigned row=0;row<T;++row){auto first=euclidean(c[b*T+row],base);auto second=euclidean(first.first,base);
            auto z=euclidean(I(first.second)+previous_r1+previous2_q2+carry,base);out.digits[b*T+row]=z.second;carry=z.first;
            last_r1=second.second;last_q2=second.first;last_previous_q2=previous_q2;
            previous_r1=second.second;previous2_q2=previous_q2;previous_q2=second.first;
        }
        auto tail=euclidean(last_r1+last_previous_q2+carry,base);low[b]=int32_t(tail.second);high[b]=int32_t(last_q2+tail.first);
        need(tail.second<base && I(high[b])>=-I(BOUND) && I(high[b])<=I(BOUND),"S4_REFERENCE_BOUNDARY");
    }
    for(unsigned b=0;b<P;++b){unsigned destination=(b+1)%P;out.c0[destination]=b==P-1?-low[b]:low[b];out.c1[destination]=b==P-1?-high[b]:high[b];}
    need(canonical(c,base)==canonical(effective(out),base),"S4_REFERENCE_REPRESENTED_RESIDUE");return out;
}
struct Frame{unsigned start,correction,epoch;bool twice;Image input,expected;Coefficients coefficients;};
static Image seed(unsigned kind){Image x;uint32_t state=0x3b7a901d+kind;for(unsigned j=0;j<N;++j){state=1664525*state+1013904223;if(kind==1)x.digits[j]=(j==N-1||j==3)?1:0;else if(kind==2||kind==3)x.digits[j]=state%BASE;}
    for(unsigned b=0;b<P;++b){if(kind>=2&&kind<=3){x.c0[b]=int32_t(b%5)-2;x.c1[b]=int32_t(b%3)-1;}if(kind==3){x.c0[b]=(b&1)?int32_t(BASE-1):-int32_t(BASE-1);x.c1[b]=(b&1)?int32_t(BOUND):-int32_t(BOUND);}}
    if(kind==4)x.c0[0]=-1;return x;
}
static std::vector<Frame> plan(unsigned kind,unsigned count){std::vector<Frame> frames;Image input=seed(kind);for(unsigned i=0;i<count;++i){bool twice=kind==2&&(i&1);auto c=schoolbook(input,twice);auto out=blockcarry(c,BASE);frames.push_back({i*INTERVAL,i?(i-1)*INTERVAL+CORRECTION:0,i,twice,input,out,c});input=out;}return frames;}
static void clear(DUT& d){d.begin_setup=0;d.in_slot_valid=0;d.frame_start=0;d.correction_valid=0;d.double_in=0;d.context_enabled=1;d.generation_in=7;d.live_generation=7;d.base_in=BASE;d.epoch_in=0;d.correction_epoch=0;d.correction_generation=7;for(unsigned b=0;b<P;++b){d.data_in[b]=0;d.c0_in[b]=0;d.c1_in[b]=0;}}
static void reset_setup(DUT& d){clear(d);d.clk=0;d.rst_n=0;d.eval();d.clk=1;d.eval();need(!d.digit_valid&&!d.boundary_valid&&!d.frame_done&&!d.out_error,"S4_RESET");d.clk=0;d.rst_n=1;d.eval();for(unsigned k=0;k<=97;++k){d.clk=0;clear(d);d.begin_setup=k==0;d.eval();d.clk=1;d.eval();need(!d.out_error,"S4_SETUP_ERROR");need(bool(d.setup_done)==(k==97),"S4_SETUP_CYCLE");need(bool(d.config_valid)==(k==97),"S4_SETUP_QUALIFICATION");}}
template<class Wide>static I signed96(const Wide& data,unsigned lane){U v=U(data[3*lane])|(U(data[3*lane+1])<<32)|(U(data[3*lane+2])<<64);return data[3*lane+2]&0x80000000u?I(v)-(I(1)<<96):I(v);}
struct Counts{unsigned cases=0,frames=0,coefficients=0,digits=0,boundaries=0,feedback=0;};
static void run(DUT& d,unsigned kind,unsigned count,Counts& counts){
    reset_setup(d);auto frames=plan(kind,count);std::vector<Image> actual(count);std::vector<std::array<bool,T>> seen(count);std::vector<bool> boundary_seen(count,false);
    unsigned last=frames.back().start+DONE+2;
    for(unsigned tick=0;tick<last;++tick){d.clk=0;clear(d);unsigned starts=0,corrections=0;
        for(unsigned i=0;i<count;++i){const auto& f=frames[i];if(tick>=f.start&&tick<f.start+T){unsigned row=tick-f.start;d.in_slot_valid=1;d.frame_start=!row;d.epoch_in=f.epoch;d.double_in=f.twice;const auto& input=i?actual[i-1]:f.input;if(i)need(seen[i-1][row],"S4_ACTUAL_FEEDBACK_ROW_NOT_READY");for(unsigned lane=0;lane<P;++lane)d.data_in[lane]=input.digits[rev4(lane)*T+row];starts+=!row;if(i&&!row)++counts.feedback;}
            if(tick==f.correction){d.correction_valid=1;d.correction_epoch=f.epoch;const auto& input=i?actual[i-1]:f.input;if(i)need(boundary_seen[i-1],"S4_ACTUAL_FEEDBACK_CORRECTION_NOT_READY");for(unsigned b=0;b<P;++b){d.c0_in[b]=uint32_t(input.c0[b]);d.c1_in[b]=uint32_t(input.c1[b]);}++corrections;}}
        d.eval();need(unsigned(d.frame_accept)==starts&&unsigned(d.correction_accept)==corrections,"S4_ADMISSION tick="+std::to_string(tick));d.clk=1;d.eval();need(!d.out_error,"S4_ERROR tick="+std::to_string(tick));
        const Frame* coefficient=nullptr;const Frame* digit=nullptr;const Frame* boundary=nullptr;const Frame* done=nullptr;unsigned ci=0,di=0,bi=0;
        for(unsigned i=0;i<count;++i){const auto& f=frames[i];if(tick>=f.start+COEFFICIENT&&tick<f.start+COEFFICIENT+T){coefficient=&f;ci=i;}if(tick>=f.start+DIGIT&&tick<f.start+DIGIT+T){digit=&f;di=i;}if(tick==f.start+BOUNDARY){boundary=&f;bi=i;}if(tick==f.start+DONE)done=&f;}
        need(bool(d.coefficient_valid)==bool(coefficient),"S4_COEFFICIENT_SLOT tick="+std::to_string(tick));
        if(coefficient){unsigned row=tick-coefficient->start-COEFFICIENT;need(d.coefficient_row==row&&bool(d.coefficient_start)==!row,"S4_COEFFICIENT_TAG");for(unsigned b=0;b<P;++b){I got=signed96(d.coefficient_data,b),expected=coefficient->coefficients[b*T+row];need(got==expected,"S4_COEFFICIENT case="+std::to_string(kind)+" frame="+std::to_string(ci)+" row="+std::to_string(row)+" lane="+std::to_string(b)+" expected="+decimal(expected)+" actual="+decimal(got));}counts.coefficients+=P;}
        need(bool(d.digit_valid)==bool(digit),"S4_DIGIT_SLOT tick="+std::to_string(tick));
        if(digit){unsigned row=tick-digit->start-DIGIT;need(d.digit_row==row&&bool(d.digit_start)==!row&&d.digit_eligible&&d.digit_epoch==digit->epoch&&d.digit_generation==7,"S4_DIGIT_TAG");for(unsigned b=0;b<P;++b){uint32_t got=d.digit_data[b];need(got==digit->expected.digits[b*T+row],"S4_DIGIT_VALUE");actual[di].digits[b*T+row]=got;}seen[di][row]=true;counts.digits+=P;}
        need(bool(d.boundary_valid)==bool(boundary),"S4_BOUNDARY_SLOT tick="+std::to_string(tick));
        if(boundary){need(d.boundary_eligible&&d.next_epoch==boundary->epoch+1&&d.next_generation==7,"S4_BOUNDARY_TAG");for(unsigned b=0;b<P;++b){actual[bi].c0[b]=int32_t(d.next_c0[b]);actual[bi].c1[b]=int32_t(d.next_c1[b]);need(actual[bi].c0[b]==boundary->expected.c0[b]&&actual[bi].c1[b]==boundary->expected.c1[b],"S4_BOUNDARY_VALUE");}need(canonical(effective(actual[bi]),BASE)==canonical(boundary->coefficients,BASE),"S4_ACTUAL_REPRESENTED_RESIDUE");boundary_seen[bi]=true;counts.boundaries+=P;}
        need(bool(d.frame_done)==bool(done),"S4_DONE_SLOT tick="+std::to_string(tick));if(done){need(d.done_epoch==done->epoch,"S4_DONE_TAG");++counts.frames;}
    }++counts.cases;
}
int main(int argc,char** argv){try{VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);DUT d{&context};if(argc==2&&std::string(argv[1])=="--runtime-probe"){std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";return context.threads()==1&&d.threads()==1?0:2;}need(argc==1,"S4_ARGUMENTS");Counts counts;run(d,0,1,counts);run(d,1,4,counts);run(d,2,4,counts);run(d,3,2,counts);run(d,4,2,counts);need(context.threads()==1&&d.threads()==1,"S4_THREADS");std::cout<<PASS_LABEL<<" cases="<<counts.cases<<" frames="<<counts.frames<<" coefficient_words="<<counts.coefficients<<" digit_words="<<counts.digits<<" boundary_pairs="<<counts.boundaries<<" warm_feedback_starts="<<counts.feedback<<"\n";d.final();return 0;}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
