#include "Vroot_recurrence27_lookahead_pair_v1.h"
#include "verilated.h"
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#ifndef TEST_LANES
#define TEST_LANES 16
#endif
#ifndef TEST_P
#define TEST_P 104857601
#endif
static constexpr unsigned L=TEST_LANES;
static constexpr uint64_t P=TEST_P;
using DUT=Vroot_recurrence27_lookahead_pair_v1;
static void require(bool value,const char* message) {if(!value)throw std::runtime_error(message);}
static uint32_t power(uint64_t a,unsigned k) {
    uint64_t y=1;while(k){if(k&1)y=y*a%P;a=a*a%P;k>>=1;}return uint32_t(y);
}
static uint32_t seed_value(unsigned context,unsigned lane) {return 19+31*context+103*lane;}
int main(int argc,char**argv) {try {
    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
    DUT d{&context};d.eval();
    if(argc==2&&std::string(argv[1])=="--runtime-probe") {
        std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()
                 <<",\"expected_threads\":1}\n";
        return context.threads()==1&&d.threads()==1?0:2;
    }
    require(argc==1||(argc==2&&std::string(argv[1])=="--bubble-witness"),"ROOT_LOOKAHEAD_ARGS");
    require(d.probe_lanes==L&&d.probe_p==P&&d.probe_q==uint32_t(2-P),"ROOT_LOOKAHEAD_PROFILE");
    uint64_t cases=0,responses=0;
    auto compare=[&](){require(!d.pair_mismatch,"ROOT_LOOKAHEAD_PAIR_MISMATCH");};
    auto tick=[&](){d.clk=0;d.eval();compare();d.clk=1;d.eval();compare();};
    auto idle=[&](){d.start=0;d.seed_we=0;d.seed_clear=0;d.request_valid=0;};
    auto reset=[&](){idle();d.rst_n=0;tick();d.rst_n=1;tick();
        require(!d.busy&&!d.done&&!d.error&&!d.seed_error&&!d.root_valid&&!d.root_mask&&!d.request_ready,"ROOT_LOOKAHEAD_RESET");};
    auto seed=[&](unsigned bank,unsigned c,unsigned j,uint32_t value,bool bad=false){
        idle();d.seed_we=1;d.seed_bank=bank;d.seed_context=c;d.seed_lane=j;d.seed_data=value;tick();
        require(bool(d.seed_error)==bad,"ROOT_LOOKAHEAD_SEED_GUARD");idle();};
    auto load=[&](unsigned active,unsigned bank){
        idle();d.seed_clear=1;d.seed_bank=bank;tick();idle();
        for(unsigned c=0;c<4;c++)for(unsigned j=0;j<active;j++)seed(bank,c,j,seed_value(c,j));};
    auto setup=[&](unsigned period,unsigned groups,unsigned active,unsigned bank){
        idle();d.config_bank=bank;d.config_groups=groups;d.config_period=period;
        d.config_active_lanes=active;d.config_step=uint32_t(7*((uint64_t(1)<<32)%P)%P);
        d.start=1;d.request_valid=1;d.seed_we=1;d.seed_data=uint32_t(P);tick();idle();
        require(d.busy&&!d.error&&!d.root_valid&&!d.seed_error&&d.request_ready,"ROOT_LOOKAHEAD_START");};
    auto run=[&](unsigned period,unsigned groups,unsigned active,unsigned pattern,unsigned bank){
        reset();load(active,bank);setup(period,groups,active,bank);
        unsigned issued=0,elapsed=0,gaps=0;uint32_t last[L]={};uint32_t last_tag=0,last_group=0;
        while(!d.done) {
            idle();d.start=1;d.config_groups=0;d.config_period=3;d.config_step=uint32_t(P);
            bool request=issued<groups&&(elapsed>=6||bool(pattern&(1u<<elapsed)));
            d.request_valid=request;d.request_tag=0x12340000u+elapsed;
            // Legal inactive-bank loading and illegal active-bank writes cannot
            // alter current selectors/seeds, even while config inputs change.
            bool bad=elapsed%11==7;
            d.seed_we=1;d.seed_bank=bad?bank:1-bank;d.seed_context=elapsed%4;
            d.seed_lane=0;d.seed_data=elapsed%17;
            d.clk=0;d.eval();compare();require(bool(d.request_ready)==(issued<groups),"ROOT_LOOKAHEAD_READY");
            tick();elapsed++;
            require(bool(d.seed_error)==bad,"ROOT_LOOKAHEAD_BUSY_SEED");
            require(bool(d.root_valid)==request,"ROOT_LOOKAHEAD_VALID");
            uint64_t mask=request?(active==64?~uint64_t(0):(uint64_t(1)<<active)-1):0;
            require(uint64_t(d.root_mask)==mask,"ROOT_LOOKAHEAD_MASK");
            if(request) {
                unsigned pos=period?issued%period:issued;
                require(d.root_tag==0x12340000u+elapsed-1&&d.root_group==issued,"ROOT_LOOKAHEAD_TAG");
                for(unsigned j=0;j<L;j++) {
                    uint32_t value=j<active?uint32_t(uint64_t(seed_value(pos%4,j))*power(7,pos/4)%P):0;
                    require(d.roots[j]==value,"ROOT_LOOKAHEAD_INTEGER_ORACLE");last[j]=value;
                }
                last_tag=d.root_tag;last_group=d.root_group;issued++;responses++;
            } else {
                if(issued<groups)gaps++;
                for(unsigned j=0;j<L;j++)require(d.roots[j]==last[j],"ROOT_LOOKAHEAD_HOLD");
                require(d.root_tag==last_tag&&d.root_group==last_group,"ROOT_LOOKAHEAD_TAG_HOLD");
            }
            require(!d.error&&elapsed<=groups+10,"ROOT_LOOKAHEAD_PROGRESS");
        }
        require(!d.busy&&issued==groups&&elapsed==groups+gaps+4&&d.cycles==elapsed,"ROOT_LOOKAHEAD_ZERO_CYCLE_DELTA");
        idle();tick();cases++;
    };
    // First witness: a bubble at issued=0, then distinct seed1 vs seed0.
    run(0,8,1,62,0);
    if(argc==2){std::cout<<"ROOT_LOOKAHEAD_WITNESS_PASS\n";return 0;}
    for(unsigned period:{0u,1u,2u,4u,8u,16u})for(unsigned pattern=0;pattern<64;pattern++)
        for(unsigned active:{1u,9u,L})run(period,20,active,pattern,pattern&1);
    for(unsigned k=0;k<18;k++)run(k?1u<<(k-1):0u,20,L,21,k&1);
    for(unsigned period:{0u,16u,65536u})run(period,65536,1,63,1);
    // Reset cancels each feedback age and drain. Restart without seed reload is
    // rejected, proving both-bank eligibility is reset, then fresh run recovers.
    for(unsigned age=1;age<=5;age++) {
        reset();load(L,0);setup(0,4,L,0);
        for(unsigned n=0;n<age;n++){d.request_valid=1;tick();}
        reset();d.config_groups=4;d.config_period=0;d.config_active_lanes=L;
        d.config_step=1;d.start=1;tick();require(d.done&&d.error&&!d.busy,"ROOT_LOOKAHEAD_RESET_ELIGIBILITY");
    }
    for(unsigned fault=0;fault<7;fault++) {
        reset();load(L,0);idle();d.config_bank=0;d.config_groups=8;d.config_period=0;d.config_active_lanes=L;d.config_step=1;
        if(fault==0)d.config_groups=0;if(fault==1)d.config_groups=65537;
        if(fault==2)d.config_period=3;if(fault==3)d.config_period=65537;
        if(fault==4)d.config_active_lanes=0;if(fault==5)d.config_active_lanes=L+1;if(fault==6)d.config_step=uint32_t(P);
        d.start=1;tick();require(d.done&&d.error&&!d.busy&&!d.request_ready,"ROOT_LOOKAHEAD_BAD_CONFIG");
    }
    require(cases==1174&&responses==220016,"ROOT_LOOKAHEAD_COVERAGE");
    std::cout<<"ROOT_LOOKAHEAD_PASS lanes="<<L<<" cases="<<cases<<" responses="<<responses<<"\n";
    return 0;
} catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
