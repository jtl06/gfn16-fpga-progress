#include "Vgenefer_track_a4_host_shell_v2.h"
#include "verilated.h"
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#ifndef A4_HOST_AW
#error A4_HOST_AW must match -GAW
#endif
static_assert(A4_HOST_AW==5 || A4_HOST_AW==8,"early small-N integration shell");
static void need(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
int main(int argc,char** argv){
    try{
        VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
        Vgenefer_track_a4_host_shell_v2 d{&context};
        if(argc==2 && std::string(argv[1])=="--runtime-probe"){
            std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
            return context.threads()==1 && d.threads()==1?0:2;
        }
        need(argc==2,"usage: a4_host vectors | --runtime-probe");
        std::ifstream input(argv[1]);need(bool(input),"A4_HOST_OPEN");
        std::string magic;unsigned aw,count;need(bool(input>>magic>>aw>>count),"A4_HOST_HEADER");
        need(magic=="A4HOST1" && aw==A4_HOST_AW && count>0 && count<10000,"A4_HOST_PROFILE");
        d.square_done=0;d.square_error=0;d.square_tail_checked=0;d.square_root_coherent=0;d.square_out_generation=0;
        d.square_coefficients_seen=0;d.square_digits_written=0;d.square_patch_words_written=0;
        d.compute_configure=0;d.compute_clear_image=0;d.compute_read_en=0;d.compute_write_en=0;
        d.compute_read_offset=0;d.compute_write_offset=0;d.compute_read_tag=0;
        d.compute_read_mask=0;d.compute_write_mask=0;d.compute_read_apply_corrections=0;d.compute_boundary_commit=0;
        for(unsigned i=0;i<16;++i){d.compute_write_words[i]=0;d.compute_boundary_low[i]=0;d.compute_boundary_high[i]=0;}
        d.cmd_valid=0;d.rsp_ready=0;d.cmd_double=0;d.rst_n=0;d.clk=0;
        uint64_t ticks=0,readbacks=0,errors=0,hold_checks=0,maximum_latency=0;
        auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();++ticks;need(!d.square_begin,"A4_HOST_UNEXPECTED_SQUARE");};
        tick();d.rst_n=1;tick();
        for(unsigned index=0;index<count;++index){
            unsigned op,address,expected_error,expected_image,expected_fault;uint64_t word,base,expected_word;
            need(bool(input>>op>>address>>word>>base>>expected_error>>expected_word>>expected_image>>expected_fault),"A4_HOST_TRUNCATED");
            need(op<8 && op!=5 && address<(1u<<aw) && word<=0xffffffffu && base<=0xffffffffu && expected_word<=0xffffffffu,"A4_HOST_RANGE");
            need(d.cmd_ready && !d.rsp_valid,"A4_HOST_READY");
            d.cmd_opcode=op;d.cmd_address=address;d.cmd_word=uint32_t(word);d.cmd_base=uint32_t(base);d.cmd_valid=1;tick();
            d.cmd_valid=0;d.cmd_opcode=7;d.cmd_base=0xffffffffu;d.cmd_word=0x80000000u;
            uint64_t latency=0;
            while(!d.rsp_valid && latency<100000){
                need(!d.cmd_ready,"A4_HOST_MISSING_BACKPRESSURE");
                d.cmd_valid=latency==2;tick();d.cmd_valid=0;++latency;
            }
            const auto at=" command="+std::to_string(index);
            need(d.rsp_valid,"A4_HOST_TIMEOUT"+at);
            need(d.rsp_opcode==op && d.rsp_error==unsigned(expected_error!=0) && d.rsp_error_code==expected_error,"A4_HOST_RESPONSE_ERROR"+at);
            need(uint32_t(d.rsp_word)==expected_word && d.image_valid==expected_image && d.fault_sticky==expected_fault && !d.prefill_valid,"A4_HOST_WORD_OR_ELIGIBILITY"+at);
            const auto generation=d.rsp_generation;
            for(unsigned hold=0;hold<2;++hold){tick();need(d.rsp_valid && d.rsp_generation==generation && d.rsp_opcode==op && uint32_t(d.rsp_word)==expected_word && d.rsp_error_code==expected_error,"A4_HOST_RESPONSE_HOLD"+at);++hold_checks;}
            if(latency>maximum_latency)maximum_latency=latency;
            readbacks+=op==2;errors+=expected_error!=0;
            d.rsp_ready=1;tick();d.rsp_ready=0;
        }
        // Abort real setup mid-operation, drain well past its former deadline.
        d.cmd_opcode=0;d.cmd_base=1000;d.cmd_valid=1;tick();d.cmd_valid=0;
        for(unsigned i=0;i<10;++i)tick();
        d.rst_n=0;tick();d.rst_n=1;
        for(unsigned i=0;i<110;++i){tick();need(!d.rsp_valid && !d.busy && !d.image_valid && !d.prefill_valid,"A4_HOST_RESET_CANCEL");}
        std::string trailing;need(!(input>>trailing),"A4_HOST_TRAILING");
        need(context.threads()==1 && d.threads()==1,"A4_HOST_THREAD_DRIFT");
        std::cout<<"A4_HOST_SHELL_PASS aw="<<aw<<" commands="<<count<<" readbacks="<<readbacks<<" errors="<<errors
                 <<" hold_checks="<<hold_checks<<" ticks="<<ticks<<" max_latency="<<maximum_latency<<"\n";
        d.final();return 0;
    }catch(const std::exception& ex){std::cerr<<ex.what()<<"\n";return 1;}
}
