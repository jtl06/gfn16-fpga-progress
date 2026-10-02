#include "Vgenefer_stream27_final_pair_inputreg_sizing_v1.h"
#include "verilated.h"
#include <cstdint>
#include <deque>
#include <iostream>
#include <stdexcept>
#include <string>
#ifndef TEST_P
#define TEST_P 104857601
#endif
#ifndef TEST_SCALE
#define TEST_SCALE 1
#endif
static constexpr uint64_t P=TEST_P,SCALE=TEST_SCALE;
static void need(bool good,const char* why){if(!good)throw std::runtime_error(why);}
static uint64_t power(uint64_t a,uint64_t e){uint64_t r=1;while(e){if(e&1)r=r*a%P;a=a*a%P;e>>=1;}return r;}
struct Token{uint64_t due;uint32_t a,b;};
int main(int argc,char**argv){try{
    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
    Vgenefer_stream27_final_pair_inputreg_sizing_v1 d{&context};d.eval();
    if(argc==2&&std::string(argv[1])=="--runtime-probe"){
        std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
        return context.threads()==1&&d.threads()==1?0:2;
    }
    need(argc==1,"FINAL_PAIR_ARGS");
    const uint64_t ri=power((uint64_t(1)<<32)%P,P-2);
    std::deque<Token> pending[2];uint64_t checked[2]={},cancelled[2]={},holds[2]={};
    uint32_t held0[2]={},held1[2]={};bool lastvalid[2]={};uint64_t random=0x6525ac4df8369b71ULL;
    for(uint64_t edge=0;edge<6400;edge++){
        const bool reset=!(edge<2||edge%257==100||edge%257==101);
        const bool valid=edge<6200&&edge%11!=0;
        random=random*6364136223846793005ULL+1442695040888963407ULL;uint64_t u=random%P;
        random=random*6364136223846793005ULL+1442695040888963407ULL;uint64_t v=random%P;
        random=random*6364136223846793005ULL+1442695040888963407ULL;uint64_t w=random%P;
        switch(edge%17){case 0:u=0;v=0;w=0;break;case 1:u=P-1;v=P-1;w=P-1;break;
            case 2:u=0;v=P-1;w=1;break;case 3:u=P-1;v=0;w=P-1;break;
            case 4:u=P/2;v=P/2+1;w=0;break;default:break;}
        if(edge%3==0)u+=P;if(edge%5==0)v+=P;
        d.clk=0;d.rst_n=reset;d.in_valid=valid?3:0;d.u=u|(u<<28);d.v=v|(v<<28);d.normalized_lower_root=w|(w<<32);d.eval();
        const uint32_t before0[2]={d.old_y0,d.new_y0},before1[2]={d.old_y1,d.new_y1};
        const bool beforevalid[2]={bool(d.old_valid),bool(d.new_valid)};
        for(unsigned k=0;k<2;k++){
            if(!reset){cancelled[k]+=pending[k].size();pending[k].clear();lastvalid[k]=false;
                held0[k]=before0[k];held1[k]=before1[k];}
            need(beforevalid[k]==lastvalid[k]&&before0[k]==held0[k]&&before1[k]==held1[k],"FINAL_PAIR_BEFORE_EDGE");
            if(reset&&valid){uint64_t a=(((u%P+v%P)%P)*SCALE%P)*ri%P,b=(((u%P+P-v%P)%P)*w%P)*ri%P;
                pending[k].push_back({edge+6+k,uint32_t(a),uint32_t(b)});}
        }
        d.clk=1;d.eval();need(!d.old_error&&!d.new_error,"FINAL_PAIR_ALIGNMENT_ERROR");
        const uint32_t after0[2]={d.old_y0,d.new_y0},after1[2]={d.old_y1,d.new_y1};
        const bool aftervalid[2]={bool(d.old_valid),bool(d.new_valid)};
        for(unsigned k=0;k<2;k++){
            bool due=!pending[k].empty()&&pending[k].front().due==edge;
            need(aftervalid[k]==due,"FINAL_PAIR_VALID_E5_E6");
            if(due){Token expected=pending[k].front();pending[k].pop_front();
                need(after0[k]<P&&after1[k]<P,"FINAL_PAIR_CANONICAL_RANGE");
                need(after0[k]==expected.a&&after1[k]==expected.b,"FINAL_PAIR_BIT_EXACT_VALUE");
                held0[k]=after0[k];held1[k]=after1[k];checked[k]++;
            }else{need(after0[k]==held0[k]&&after1[k]==held1[k],"FINAL_PAIR_INVALID_HOLD");holds[k]++;}
            lastvalid[k]=due;
        }
    }
    need(pending[0].empty()&&pending[1].empty(),"FINAL_PAIR_TAIL");
    std::cout<<"FINAL_PAIR_INPUTREG_SIZING_PASS p="<<P<<" scale="<<SCALE<<" edges=6400 old_checked="<<checked[0]
        <<" new_checked="<<checked[1]<<" old_cancelled="<<cancelled[0]<<" new_cancelled="<<cancelled[1]
        <<" old_holds="<<holds[0]<<" new_holds="<<holds[1]<<" old_latency=6 new_latency=7\n";
    return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
