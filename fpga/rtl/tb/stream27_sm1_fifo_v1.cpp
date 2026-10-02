#include "Vstream27_sm1_fifo_probe_v1.h"
#include "verilated.h"
#include <cstdint>
#include <deque>
#include <iostream>
#include <stdexcept>
#include <string>
#include <array>
static void need(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
int main(int argc,char** argv){
    try{
        VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
        Vstream27_sm1_fifo_probe_v1 d{&context};
        if(argc==2 && std::string(argv[1])=="--runtime-probe"){
            std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
            return context.threads()==1 && d.threads()==1?0:2;
        }
        need(argc==2 && std::string(argv[1])=="--pilot","SM1_ARGUMENTS");
        std::array<std::deque<uint64_t>,7> queues;
        uint64_t random=0x534d31u;unsigned resets=0,advances=0,holds=0;
        constexpr uint64_t mask=(uint64_t(1)<<38)-1;
        d.clk=0;d.rst_n=0;d.advance=0;d.write_word=0;d.eval();
        for(unsigned edge=0;edge<4096;++edge){
            random=random*6364136223846793005ULL+1442695040888963407ULL;
            const bool reset=edge==0 || edge==19 || edge==137 || edge==1023 || edge==3071;
            d.rst_n=!reset;d.advance=!reset && ((random>>62)!=0);d.write_word=(random>>9)&mask;
            if(reset){for(auto& q:queues)q.clear();++resets;}
            else if(d.advance){
                ++advances;
                for(unsigned i=0;i<7;++i){queues[i].push_back(d.write_word);if(queues[i].size()>(1u<<i))queues[i].pop_front();}
            }else ++holds;
            d.clk=0;d.eval();d.clk=1;d.eval();
            need(d.mismatch==0,"SM1_FROZEN_EQUIVALENCE");
            for(unsigned i=0;i<7;++i){
                uint64_t observed=0;
                for(unsigned bit=0;bit<38;++bit){unsigned position=i*38+bit;observed|=uint64_t((d.heads[position/32]>>(position%32))&1u)<<bit;}
                const auto expected=queues[i].size()==(1u<<i)?queues[i].front():0;
                need(observed==expected,"SM1_INDEPENDENT_QUEUE");
            }
        }
        need(context.threads()==1 && d.threads()==1,"SM1_THREAD_DRIFT");
        std::cout<<"SM1_FIFO_PASS edges=4096 depths=7 head_checks=28672 resets="<<resets<<" advances="<<advances<<" holds="<<holds<<"\n";
        d.final();return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
