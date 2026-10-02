#include "Vgenefer_stream27_p16_mlab_test_v1.h"
#include "verilated.h"
#include "native_runtime_context_v1.h"
#include <array>
#include <cstdint>
#include <deque>
#include <iostream>
#include <stdexcept>
#include <string>
using DUT=Vgenefer_stream27_p16_mlab_test_v1;
using Word=std::array<uint32_t,7>;
static constexpr unsigned widths[]={1,10,28,29,37,38,64,224};
static constexpr unsigned depths[]={1,2,4,8,16,32,64};
static constexpr unsigned geometries=56,stride=7;
static void require(bool okay,const char* message){if(!okay)throw std::runtime_error(message);}
static uint64_t token(unsigned cycle,unsigned g,unsigned lane){
    uint64_t x=(uint64_t(cycle)+19)*0x9e3779b97f4a7c15ull+uint64_t(g+1)*0xbf58476d1ce4e5b9ull+lane;
    x=(x^(x>>30))*0xbf58476d1ce4e5b9ull;x=(x^(x>>27))*0x94d049bb133111ebull;return x^(x>>31);
}
template<class T>static Word read(const T& data,unsigned g){
    Word result{};for(unsigned i=0;i<stride;i++)result[i]=data[g*stride+i];return result;
}
static Word value(unsigned cycle,unsigned g){
    Word result{};unsigned width=widths[g/7];
    for(unsigned i=0;i<stride;i++)if(i*32<width){
        result[i]=uint32_t(token(cycle,g,i));
        if(width-i*32<32)result[i]&=(uint32_t(1)<<(width-i*32))-1;
    }
    return result;
}
int main(int argc,char** argv){
    try{
        VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d(&context);
        if(argc==2 && std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
        bool resets=argc==2 && std::string(argv[1])=="--reset-test";
        require(argc==1 || resets,"P2_MLAB_ARGUMENTS");require(gfn16_runtime::matches(context,d),"P2_MLAB_THREADS");
        std::array<std::deque<Word>,geometries> reference;
        unsigned comparisons=0,cycle=0;
        auto compare=[&](){for(unsigned g=0;g<geometries;g++){
            Word expected=reference[g].size()==depths[g%7]?reference[g].front():Word{};
            require(read(d.head_parent,g)==expected,"P2_MLAB_PARENT_MISMATCH");
            require(read(d.head_candidate,g)==expected,"P2_MLAB_CANDIDATE_MISMATCH");comparisons++;
        }};
        auto reset=[&](){d.rst_n=0;for(auto& q:reference)q.clear();d.eval();compare();};
        auto tick=[&](bool dense){
            d.advance=0;
            for(unsigned g=0;g<geometries;g++){
                Word x=value(cycle,g);for(unsigned i=0;i<stride;i++)d.write_words[g*stride+i]=x[i];
                if(dense || token(cycle+7,g,0)%11>=3)d.advance|=uint64_t(1)<<g;
            }
            d.clk=0;d.eval();compare();context.timeInc(1);
            for(unsigned g=0;g<geometries;g++)if(d.rst_n && ((d.advance>>g)&1)){
                if(reference[g].size()==depths[g%7])reference[g].pop_front();
                reference[g].push_back(read(d.write_words,g));
            }
            d.clk=1;d.eval();compare();context.timeInc(1);
            for(unsigned i=0;i<geometries*stride;i++)d.write_words[i]^=0xffffffffu;
            d.advance^=(uint64_t(1)<<geometries)-1;
            d.clk=0;d.eval();compare();context.timeInc(1);cycle++;
        };
        d.clk=0;d.rst_n=1;d.advance=0;
        for(unsigned i=0;i<geometries*stride;i++)d.write_words[i]=0;
        d.eval();reset();d.rst_n=1;
        if(!resets){
            for(unsigned i=0;i<4096;i++)tick(i<192);
            require(comparisons==688184,"P2_MLAB_COUNTS");
            std::cout<<"P2_MLAB_NORMAL_PASS geometries=56 cycles=4096 comparisons=688184\n";
        }else{
            for(unsigned age=0;age<130;age++){
                reset();d.rst_n=1;for(unsigned i=0;i<age;i++)tick(true);
                reset();for(unsigned i=0;i<3;i++)tick(true);
                d.rst_n=1;d.advance=0;d.eval();compare();
                for(unsigned i=0;i<160;i++)tick(i<80);
            }
            std::cout<<"P2_MLAB_RESET_PASS geometries=56 reset_ages=130 comparisons="<<comparisons<<"\n";
        }
        return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
