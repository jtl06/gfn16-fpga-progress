// Separate single-case AW16/L64 reset qualification harness; no physical top.
#include "Vrowcompact_reset_probe.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

static void need(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
template<class T> static __int128_t signed96(const T& a){
    __uint128_t x=__uint128_t(a[0])|(__uint128_t(a[1])<<32)|(__uint128_t(a[2])<<64);
    return a[2]&0x80000000u ? __int128_t(x)-(__int128_t(1)<<96) : __int128_t(x);
}
static unsigned number(const char* arg,unsigned maximum){
    std::string text(arg);need(text.size()==1 && text[0]>='0' && text[0]<='0'+maximum,"invalid case selector");
    return unsigned(text[0]-'0');
}
struct Vector {unsigned base;std::vector<int64_t> input,expected;};
static Vector vector_for(const char* path,unsigned bit){
    std::ifstream file(path);need(bool(file),"missing pinned vectors");
    unsigned n,base,first_bit,second_bit;std::string op,name;
    file>>n;bool found=false;
    while(file>>op){
        if(op=="LOAD"){file>>name>>base;found=true;break;}
        std::string skipped;std::getline(file,skipped); // Frozen suite begins with invalid-input cases.
    }
    need(found&&n==65536&&name=="full-random","frozen first LOAD changed");
    std::vector<int64_t> input(n),first(n),second(n);
    for(auto& value:input)file>>value;
    file>>op>>name>>first_bit;need(op=="RUN"&&name=="full-random-s0-d0"&&first_bit==0,"first RUN changed");
    for(auto& value:first)file>>value;
    file>>op>>name>>second_bit;need(op=="RUN"&&name=="full-random-s1-d1"&&second_bit==1,"second RUN changed");
    for(auto& value:second)file>>value;
    need(bool(file),"truncated vectors");
    return bit ? Vector{base,first,second} : Vector{base,input,first};
}
int main(int argc,char** argv){try{
    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
    Vrowcompact_reset_probe d{&context};
    if(argc==2&&std::string(argv[1])=="--runtime-probe"){
        d.eval();std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"aw\":16,\"lanes\":64}\n";
        return context.threads()==1&&d.threads()==1 ? 0 : 2;
    }
    need(context.threads()==1&&d.threads()==1,"single-thread runtime required");
    const bool recover_only=argc==4&&std::string(argv[2])=="--recover-only";
    need(recover_only||argc==6,"usage: vectors bf|mul variant age bit; or vectors --recover-only bit");
    const bool bf=!recover_only&&std::string(argv[2])=="bf";
    need(recover_only||bf||std::string(argv[2])=="mul","unknown target kind");
    const unsigned variant=recover_only?0:number(argv[3],1),age=recover_only?0:number(argv[4],7);
    const unsigned bit=number(argv[recover_only?3:5],1),bank=bf?(variant?0:2):64*variant;
    const unsigned target_group=bf?variant:2+variant,target_row=bf?256:1;
    Vector vector=vector_for(argv[1],bit);uint64_t edges=0;
    d.probe_bank=bank;d.base=vector.base;d.double_bit=bit;
    auto idle=[&](){d.start=0;d.load_we=0;d.read_en=0;};
    auto low=[&](){d.clk=0;d.eval();};
    auto rise=[&](){d.clk=1;d.eval();need(++edges<=500000,"single-case edge cap");};
    auto tick=[&](){low();rise();};
    auto reset_flags=[&](){
        need(!d.busy&&!d.done&&!d.error&&!d.read_valid&&!d.profile_cache_valid,"top reset flags");
        need(!d.probe_tag_nonzero&&!d.probe_bf_in&&!d.probe_mul_in&&!d.probe_bf_valid&&!d.probe_mul_valid&&!d.probe_any_write,"tag/valid/write reset quarantine");
        for(unsigned f=0;f<3;f++)need(d.probe_bf_checks[f]==0&&d.probe_mul_checks[f]==0&&d.probe_bf_nonzero[f]==0&&d.probe_mul_nonzero[f]==0,"shadow counter reset");
    };
    auto reset=[&](){idle();low();d.rst_n=0;d.eval();reset_flags(); // No rising edge before checking asynchronous effects.
        d.rst_n=1;d.eval();for(unsigned i=0;i<8;i++){tick();reset_flags();}};
    auto load=[&](){idle();d.base=vector.base;d.double_bit=bit;
        for(unsigned i=0;i<65536;i++){d.host_addr=i;d.write_data=uint32_t(vector.input[i]);d.load_we=1;tick();}
        idle();tick();};
    auto start=[&](){idle();d.start=1;tick();d.start=0;need(d.busy&&!d.done&&!d.error,"start rejected");};
    reset();
    if(!recover_only){
        load();start();bool reached=false;std::array<unsigned,3> saved_base{},saved_toggle{},saved_pair{},saved_orientation{};
        for(unsigned wait=0;wait<100000;wait++){
            low();bool match=d.probe_issue==7&&d.probe_read==7;
            for(unsigned f=0;f<3;f++)match=match&&d.probe_group[f]==target_group&&
                (bf ? d.probe_state[f]==5&&d.probe_stage[f]==15&&d.probe_op[f]==0&&d.probe_phase[f]==1&&((d.probe_orientation>>f)&1)==variant :
                      d.probe_state[f]==7&&d.probe_op[f]==2&&d.probe_phase[f]==0&&((d.probe_half>>f)&1)==variant);
            if(match){
                need(d.busy&&!d.done,"target not live");
                for(unsigned f=0;f<3;f++)need(d.probe_ra[f]==target_row,"selected bank row is not intended nonzero row");
                std::cout<<"ACCEPT kind="<<(bf?"bf":"mul")<<" variant="<<variant<<" bank="<<bank<<" row="<<target_row<<" group="<<target_group<<" edge="<<edges+1<<"\n";
                rise();reached=true;
                need((bf?d.probe_bf_in:d.probe_mul_in)==7,"E0 registered request missing");
                for(unsigned f=0;f<3;f++){
                    saved_base[f]=d.probe_base[f][bank/16][0];saved_toggle[f]=d.probe_toggle[f][bank/16][0];
                    saved_pair[f]=d.probe_pair[f][bank/16][0];saved_orientation[f]=d.probe_orient[f][bank/16]&1;
                    need(saved_base[f]==(bf?0:1)&&saved_toggle[f]==(bf?256:0),"E0 common row capture");
                    if(bf)need(saved_pair[f]==1&&saved_orientation[f]==variant,"E0 BF selector capture");
                }
                break;
            }
            need(!d.done&&!d.error,"operation finished before trigger");rise();
        }
        need(reached,"target acceptance timeout");unsigned committed=0;
        for(unsigned current=0;current<=age;current++){
            if(current<7)for(unsigned f=0;f<3;f++)need(
                d.probe_base[f][bank/16][current]==saved_base[f]&&d.probe_toggle[f][bank/16][current]==saved_toggle[f]&&
                d.probe_pair[f][bank/16][current]==saved_pair[f]&&((d.probe_orient[f][bank/16]>>current)&1)==saved_orientation[f],"target row token age mismatch");
            if(current==age)break;
            low();unsigned selected=0;
            for(unsigned f=0;f<3;f++)if(((d.probe_write>>f)&1)&&d.probe_wa[f]==target_row){
                selected++;need(d.probe_legacy[f]==target_row,"pre-E7 legacy address mismatch");}
            if(current==6)need(selected==3,"target E7 write missing");
            else need(selected==0,"target write occurred before E7");
            rise();if(selected==3)committed++;
        }
        need(committed==(age==7?1u:0u),"target commit classification");
        for(unsigned f=0;f<3;f++)std::cout<<"PRE_RESET field="<<f<<" age="<<age<<" committed="<<committed
            <<" bf_checks="<<d.probe_bf_checks[f]<<" mul_checks="<<d.probe_mul_checks[f]
            <<" bf_nonzero="<<d.probe_bf_nonzero[f]<<" mul_nonzero="<<d.probe_mul_nonzero[f]<<"\n";
        reset();std::cout<<"RESET async=1 quiet_edges=8 writes=0\n";
    }
    load();start();unsigned elapsed=0;
    while(!d.done&&elapsed<100000){tick();elapsed++;need(!d.error,"cold recovery error");}
    need(d.done&&!d.busy&&!d.error&&d.cycles==elapsed&&d.cycles==41708,"cold recovery completion/cycles");
    need(d.conversion_cycles==4102&&d.root_cycles==8743&&d.ntt_cycles==20558&&d.crt_cycles==4158&&d.carry_cycles==4147&&d.carry_passes==2,"cold recovery phase counts");
    need(d.profile_cache_valid&&d.profile_loads==1&&d.profile_hits==0&&d.profile_words_loaded==8738&&d.seed_setup_cycles==815,"cold recovery profile counts");
    for(unsigned f=0;f<3;f++){
        need(d.probe_bf_checks[f]==2097152&&d.probe_mul_checks[f]==196608,"full recovery shadow comparison counts");
        need(d.probe_bf_nonzero[f]==2093056&&d.probe_mul_nonzero[f]==196224,"full recovery nonzero-row comparison counts");
        std::cout<<"SHADOW field="<<f<<" bf="<<d.probe_bf_checks[f]<<" mul="<<d.probe_mul_checks[f]
            <<" bf_nonzero="<<d.probe_bf_nonzero[f]<<" mul_nonzero="<<d.probe_mul_nonzero[f]<<"\n";
    }
    for(unsigned i=0;i<65536;i++){d.read_en=1;d.host_addr=i;tick();need(d.read_valid&&signed96(d.read_data)==vector.expected[i],"cold recovery readback mismatch");}
    idle();tick();std::cout<<"PASS reset_probe kind="<<(recover_only?"recovery":bf?"bf":"mul")<<" variant="<<variant
        <<" age="<<age<<" bit="<<bit<<" readbacks=65536 recovery_cycles=41708 edges="<<edges<<"\n";
    return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
