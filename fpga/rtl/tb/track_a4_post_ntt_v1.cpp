#include "Vtrack_a4_post_ntt_probe_v1.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#ifndef A4_POST_AW
#error A4_POST_AW must match -GAW
#endif
static_assert(A4_POST_AW==5 || A4_POST_AW==8,"small post-NTT gate");
static void need(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
template<class Wide>static void set96(Wide& value,const std::string& text){need(text.size()==24,"A4_POST_HEX");for(unsigned i=0;i<3;++i)value[i]=uint32_t(std::stoul(text.substr(16-8*i,8),nullptr,16));}
template<class Wide>static uint64_t get33(const Wide& value,unsigned lane){const unsigned bit=lane*33,word=bit/32,shift=bit%32;return ((uint64_t(value[word])>>shift)|(uint64_t(value[word+1])<<(32-shift)))&((uint64_t(1)<<33)-1);}
int main(int argc,char** argv){
    try{
        VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
        Vtrack_a4_post_ntt_probe_v1 d{&context};
        if(argc==2 && std::string(argv[1])=="--runtime-probe"){
            std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
            return context.threads()==1 && d.threads()==1?0:2;
        }
        need(argc==2,"usage: a4_post vectors | --runtime-probe");std::ifstream input(argv[1]);need(bool(input),"A4_POST_OPEN");
        std::string magic;unsigned aw,count;need(bool(input>>magic>>aw>>count),"A4_POST_HEADER");
        need(magic=="A4POST1" && aw==A4_POST_AW && count>0 && count<1000,"A4_POST_PROFILE");
        const unsigned n=1u<<aw,t=n/16;uint64_t field_words=0,image_words=0;
        auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();};
        for(unsigned test=0;test<count;++test){
            uint64_t base;unsigned double_bit,clocks;std::string limit,reciprocal;
            need(bool(input>>base>>double_bit>>clocks>>limit>>reciprocal),"A4_POST_CASE");
            std::array<std::vector<uint32_t>,3> residues,expected_fields;
            for(auto& field:residues){field.resize(n);for(auto& x:field)need(bool(input>>x),"A4_POST_RESIDUES");}
            std::vector<uint64_t> effective(n);for(auto& x:effective)need(bool(input>>x)&&x<(uint64_t(1)<<33),"A4_POST_IMAGE");
            for(auto& field:expected_fields){field.resize(n);for(auto& x:field)need(bool(input>>x),"A4_POST_EXPECTED_FIELDS");}
            std::array<uint32_t,16> c0,c1,s0,s1;for(auto* a:{&c0,&c1,&s0,&s1})for(auto& x:*a)need(bool(input>>x),"A4_POST_BOUNDARIES");
            need(base<=1000000000u && double_bit<=1 && clocks==t+58,"A4_POST_RANGE");
            d.rst_n=0;d.cancel=0;d.prepare=0;d.start_post=0;d.configure_image=0;d.host_field_load=0;d.host_field_read=0;d.image_read=0;tick();
            d.rst_n=1;d.base=uint32_t(base);d.generation=test+1;d.double_bit=double_bit;set96(d.coefficient_limit,limit);set96(d.reciprocal,reciprocal);
            d.prepare=1;d.configure_image=1;tick();d.prepare=0;d.configure_image=0;
            d.host_field_load=1;
            for(unsigned offset=0;offset<t;++offset){d.host_offset=offset;for(unsigned f=0;f<3;++f)for(unsigned lane=0;lane<16;++lane)d.host_field_words[f*16+lane]=residues[f][lane*t+offset];tick();}
            d.host_field_load=0;unsigned waited=0;while(!d.ready && waited++<64){tick();need(!d.error,"A4_POST_PREPARE_ERROR");}need(d.ready,"A4_POST_NOT_READY");
            d.start_post=1;tick();d.start_post=0;unsigned elapsed=0;
            while(!d.done && elapsed<clocks+16){tick();++elapsed;need(!d.error,"A4_POST_SERVICE_ERROR case="+std::to_string(test)+" code="+std::to_string(d.error_code));}
            need(d.done && d.cycles==clocks && elapsed+1==clocks && d.tail_checked && d.out_generation==test+1
                && d.coefficients_seen==n && d.digits_written==n && d.patch_words_written==32,"A4_POST_COMPLETION_OR_CYCLES");
            need(d.shadow0_valid==65535 && d.shadow1_valid==65535,"A4_POST_SHADOW_VALID");
            for(unsigned lane=0;lane<16;++lane)need(d.c0_words[lane]==c0[lane] && d.c1_words[lane]==c1[lane] && d.shadow0_words[lane]==s0[lane] && d.shadow1_words[lane]==s1[lane],"A4_POST_BOUNDARY_OR_SHADOW");
            d.host_field_read=1;d.image_read=1;
            for(unsigned offset=0;offset<t;++offset){
                d.host_offset=offset;tick();need(d.host_field_valid==7 && d.image_read_valid,"A4_POST_READ_VALID");
                for(unsigned lane=0;lane<16;++lane){need(get33(d.image_read_words,lane)==effective[lane*t+offset],"A4_POST_EFFECTIVE_IMAGE");++image_words;}
                for(unsigned f=0;f<3;++f)for(unsigned lane=0;lane<16;++lane){need(d.host_field_read_words[f*16+lane]==expected_fields[f][lane*t+offset],"A4_POST_PREFILL_RESIDUE");++field_words;}
            }
            d.host_field_read=0;d.image_read=0;
        }
        std::string trailing;need(!(input>>trailing),"A4_POST_TRAILING");need(context.threads()==1 && d.threads()==1,"A4_POST_THREAD_DRIFT");
        std::cout<<"A4_POST_NTT_PASS aw="<<aw<<" cases="<<count<<" post_clocks="<<t+58<<" field_words="<<field_words<<" image_words="<<image_words<<"\n";
        d.final();return 0;
    }catch(const std::exception& ex){std::cerr<<ex.what()<<"\n";return 1;}
}
