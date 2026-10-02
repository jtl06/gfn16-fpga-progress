#include "Vgenefer_track_a4_digit_image_v1.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#ifndef A4_IMAGE_AW
#error A4_IMAGE_AW must match the explicit native -GAW
#endif
static_assert(A4_IMAGE_AW==5 || A4_IMAGE_AW==8,"bounded source-native gate");
static void need(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
template<class Wide> static int64_t word33(const Wide& port,unsigned lane){
    const unsigned bit=lane*33,index=bit/32,shift=bit%32;
    const uint64_t pair=uint64_t(port[index])|(uint64_t(port[index+1])<<32);
    const uint64_t raw=(pair>>shift)&((uint64_t(1)<<33)-1);
    return (raw&(uint64_t(1)<<32)) ? int64_t(raw)-(int64_t(1)<<33) : int64_t(raw);
}
using Row=std::array<int64_t,157>;
static void check(const Vgenefer_track_a4_digit_image_v1& d,const Row& r,uint64_t edge){
    const auto at=" edge="+std::to_string(edge);
    need(d.configured==r[65] && d.active_base==r[66] && d.active_generation==r[67],"A4_IMAGE_CONFIG"+at);
    need(d.read_valid==r[68] && d.read_mask_out==r[69],"A4_IMAGE_READ_VALID"+at);
    need(d.error==r[72] && d.error_code==r[73],"A4_IMAGE_ERROR"+at);
    if(d.error)need(d.error_generation==r[74],"A4_IMAGE_ERROR_GENERATION"+at);
    need(d.shadow0_valid==r[75] && d.shadow1_valid==r[76],"A4_IMAGE_SHADOW_VALID"+at);
    if(d.read_valid){
        need(d.read_tag_out==r[70] && d.read_generation==r[71],"A4_IMAGE_READ_TAG"+at);
        for(unsigned j=0;j<16;++j)if((d.read_mask_out>>j)&1)
            need(word33(d.read_words,j)==r[77+j],"A4_IMAGE_EFFECTIVE_WORD"+at+" lane="+std::to_string(j));
    }
    for(unsigned j=0;j<16;++j){
        need(d.c0_words[j]==r[93+j] && d.c1_words[j]==r[109+j],"A4_IMAGE_CORRECTION"+at+" lane="+std::to_string(j));
        if((d.shadow0_valid>>j)&1)need(d.shadow0_words[j]==r[125+j],"A4_IMAGE_SHADOW0"+at);
        if((d.shadow1_valid>>j)&1)need(d.shadow1_words[j]==r[141+j],"A4_IMAGE_SHADOW1"+at);
    }
}
int main(int argc,char** argv){
    try{
        VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
        Vgenefer_track_a4_digit_image_v1 d{&context};
        if(argc==2 && std::string(argv[1])=="--runtime-probe"){
            std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
            return context.threads()==1 && d.threads()==1?0:2;
        }
        need(argc==2,"usage: a4_image vectors | --runtime-probe");
        std::ifstream input(argv[1]);need(bool(input),"A4_IMAGE_VECTOR_OPEN");
        std::string magic;unsigned aw;uint64_t events;
        need(bool(input>>magic>>aw>>events),"A4_IMAGE_HEADER");
        need(magic=="A4IMAGE1" && aw==A4_IMAGE_AW && events>0 && events<100000,"A4_IMAGE_PROFILE");
        d.clk=0;d.rst_n=0;d.configure=0;d.read_en=0;d.write_en=0;
        d.clear_corrections=0;d.set_minus_one=0;d.boundary_commit=0;d.eval();
        Row previous{};bool have_previous=false;
        uint64_t reads=0,words=0,errors=0,resets=0,before_checks=0;
        for(uint64_t edge=0;edge<events;++edge){
            Row r{};for(auto& value:r)need(bool(input>>value),"A4_IMAGE_TRUNCATED");
            for(unsigned k:{0u,1u,2u,5u,8u,10u,14u,15u,16u})need(r[k]==0 || r[k]==1,"A4_IMAGE_BOOL_RANGE");
            for(unsigned k:{6u,9u,11u})need(r[k]>=0 && r[k]<(1<<aw),"A4_IMAGE_ADDRESS_RANGE");
            for(unsigned k:{7u,12u})need(r[k]>=0 && r[k]<=65535,"A4_IMAGE_MASK_RANGE");
            need(r[3]>=0 && r[3]<=0xffffffffll && r[4]>=0 && r[4]<=0xffffffffll && r[13]>=0 && r[13]<=3,"A4_IMAGE_CONFIG_RANGE");
            for(unsigned k=17;k<65;++k)need(r[k]>=0 && r[k]<=0xffffffffll,"A4_IMAGE_WORD_RANGE");
            d.clk=0;d.eval();
            d.rst_n=r[0];d.configure=r[1];d.clear_image=r[2];d.base=r[3];d.generation=r[4];
            d.read_en=r[5];d.read_offset=r[6];d.read_mask=r[7];d.read_apply_corrections=r[8];d.read_tag=r[9];
            d.write_en=r[10];d.write_offset=r[11];d.write_mask=r[12];d.write_kind=r[13];
            d.clear_corrections=r[14];d.set_minus_one=r[15];d.boundary_commit=r[16];
            for(unsigned j=0;j<16;++j){d.write_words[j]=r[17+j];d.boundary_low_words[j]=r[33+j];d.boundary_high_words[j]=r[49+j];}
            d.eval();
            if(!d.rst_n)need(!d.configured && !d.read_valid && !d.error && !d.shadow0_valid && !d.shadow1_valid,"A4_IMAGE_RESET_CANCEL");
            else if(have_previous){check(d,previous,edge);++before_checks;}
            d.clk=1;d.eval();check(d,r,edge);
            reads+=d.read_valid;errors+=d.error;resets+=!r[0];
            for(unsigned j=0;j<16;++j)words+=d.read_valid && ((d.read_mask_out>>j)&1);
            previous=r;have_previous=true;
        }
        std::string trailing;need(!(input>>trailing),"A4_IMAGE_TRAILING");
        need(context.threads()==1 && d.threads()==1,"A4_IMAGE_THREAD_DRIFT");
        std::cout<<"A4_IMAGE_PASS aw="<<aw<<" events="<<events<<" reads="<<reads<<" words="<<words
                 <<" errors="<<errors<<" resets="<<resets<<" before_checks="<<before_checks<<"\n";
        d.final();return 0;
    }catch(const std::exception& ex){std::cerr<<ex.what()<<"\n";return 1;}
}
