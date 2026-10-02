#include "Vgenefer_root_recurrence27_periodmask.h"
#include "verilated.h"
#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>
#ifndef TEST_LANES
#define TEST_LANES 16
#endif
#ifndef TEST_P
#define TEST_P 104857601u
#endif
static constexpr unsigned L=TEST_LANES;
struct Case {std::string name;unsigned groups,active,period,step,contexts;std::vector<uint32_t> seeds,expected;};
int main(int argc,char** argv){try{
    Verilated::commandArgs(argc,argv);if(argc!=2)throw std::runtime_error("vectors required");
    std::ifstream f(argv[1]);if(!f)throw std::runtime_error("input open");
    Vgenefer_root_recurrence27_periodmask d;std::mt19937 rng(0x414193);uint64_t checks=0,responses=0,seedchecks=0,bubbles=0;
    unsigned runs=0,aborts=0,rejects=0;std::vector<uint32_t> last(L);uint32_t lasttag=0,lastgroup=0;
    auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();};
    auto idle=[&](){d.start=0;d.request_valid=0;d.seed_we=0;d.seed_clear=0;};
    auto reset=[&](){idle();d.rst_n=0;tick();d.rst_n=1;tick();
        if(d.busy||d.done||d.error||d.seed_error||d.root_valid||d.root_mask||d.request_ready)throw std::runtime_error("reset flags mismatch");
        for(unsigned j=0;j<L;j++)if(d.roots[j])throw std::runtime_error("reset roots mismatch");
        std::fill(last.begin(),last.end(),0);lasttag=lastgroup=0;};
    auto seed=[&](bool clear,unsigned bank,unsigned context,unsigned lane,uint32_t value,bool bad=false){
        idle();d.seed_clear=clear;d.seed_we=!clear;d.seed_bank=bank;d.seed_context=context;d.seed_lane=lane;d.seed_data=value;tick();seedchecks++;
        if(bool(d.seed_error)!=bad||d.root_valid||d.root_mask)throw std::runtime_error("seed access mismatch");idle();};
    auto config=[&](const Case& c,unsigned bank){d.config_bank=bank;d.config_groups=c.groups;d.config_active_lanes=c.active;d.config_period=c.period;d.config_step=c.step;};
    auto load=[&](const Case& c,unsigned bank){seed(true,bank,0,0,0);
        for(unsigned q=0;q<c.contexts;q++)for(unsigned j=0;j<c.active;j++)seed(false,bank,q,j,c.seeds[q*c.active+j]);};
    reset();
    // No valid seeds after reset. Bad configuration and incomplete seed sets
    // must reject synchronously without producing roots or becoming busy.
    Case empty{"empty",8,L,0,1,4,std::vector<uint32_t>(4*L,1),{}};
    for(unsigned fault=0;fault<8;fault++){
        if(fault==1)load(empty,0);
        idle();config(empty,0);
        if(fault==1)d.config_groups=0;if(fault==2)d.config_groups=65537;
        if(fault==3)d.config_active_lanes=0;if(fault==4)d.config_active_lanes=L+1;
        if(fault==5)d.config_period=3;if(fault==6)d.config_period=65537;if(fault==7)d.config_step=TEST_P;
        d.start=1;tick();if(!d.done||!d.error||d.busy||d.root_valid||d.request_ready)throw std::runtime_error("config rejection missing");rejects++;idle();tick();
    }
    std::string marker;unsigned cases=0;bool drain_tested=false;
    while(f>>marker){
        Case c;if(marker!="CASE")throw std::runtime_error("bad input record");
        f>>c.name>>c.groups>>c.active>>c.period>>c.step>>c.contexts;
        c.seeds.resize(c.contexts*c.active);c.expected.resize(c.groups*c.active);
        for(auto& x:c.seeds)f>>x;for(auto& x:c.expected)f>>x;
        load(c,0);
        // Illegal idle writes must not destroy previously loaded seeds.
        seed(false,0,0,L,0,true);seed(false,0,0,0,TEST_P,true);seed(false,0,0,0,0xffffffffu,true);seed(false,0,0,0,0x80000001u,true);
        for(unsigned rep=0;rep<2;rep++){
            unsigned bank=rep,other=1-bank;if(rep==0)seed(true,other,0,0,0);
            idle();config(c,bank);d.start=1;d.request_valid=1;d.seed_we=1;d.seed_bank=bank;d.seed_data=TEST_P;tick();
            if(!d.busy||d.error||d.root_valid||d.seed_error||!d.request_ready)throw std::runtime_error("start mismatch "+c.name);
            unsigned issued=0,prefetch=0,elapsed=0,gaps=0;
            while(!d.done&&elapsed<3*c.groups+50){
                d.start=1;d.config_groups=0;d.config_active_lanes=0;d.config_step=TEST_P;
                d.config_period=(elapsed&1) ? 0u : 131071u; // Busy configuration must not alter the cached mask.
                d.request_valid=issued<c.groups && (!rep||rng()%3!=0);d.request_tag=rng();
                bool valid=d.request_valid;uint32_t tag=d.request_tag;
                bool active_bad=elapsed%19==7,clear_bad=elapsed%43==11;
                d.seed_we=0;d.seed_clear=0;
                if(rep==1&&elapsed==0){d.seed_clear=1;d.seed_bank=other;}
                else if(clear_bad){d.seed_clear=1;d.seed_bank=bank;}
                else if(active_bad){d.seed_we=1;d.seed_bank=bank;d.seed_context=0;d.seed_lane=0;d.seed_data=0;}
                else if(prefetch<c.seeds.size()){
                    d.seed_we=1;d.seed_bank=other;d.seed_context=prefetch/c.active;d.seed_lane=prefetch%c.active;d.seed_data=c.seeds[prefetch];prefetch++;
                }
                d.clk=0;d.eval();
                if(bool(d.request_ready)!=(issued<c.groups))throw std::runtime_error("unexpected ready/backpressure "+c.name);
                if(d.root_tag!=lasttag||d.root_group!=lastgroup)throw std::runtime_error("combinational tag mismatch");
                for(unsigned j=0;j<L;j++)if(d.roots[j]!=last[j])throw std::runtime_error("combinational root mismatch");
                d.clk=1;d.eval();elapsed++;checks++;
                if(bool(d.seed_error)!=(active_bad||clear_bad))throw std::runtime_error("busy seed arbitration mismatch");
                uint64_t mask=valid?(c.active==64?~uint64_t(0):(uint64_t(1)<<c.active)-1):0;
                if(bool(d.root_valid)!=valid||uint64_t(d.root_mask)!=mask)throw std::runtime_error("root response latency/mask mismatch");
                if(valid){
                    if(d.root_tag!=tag||d.root_group!=issued)throw std::runtime_error("root tag/group mismatch");
                    lasttag=tag;lastgroup=issued;
                    for(unsigned j=0;j<L;j++){
                        uint32_t expected=j<c.active?c.expected[issued*c.active+j]:0;
                        if(d.roots[j]!=expected)throw std::runtime_error("root data mismatch "+c.name+" group="+std::to_string(issued)+" lane="+std::to_string(j));
                        last[j]=expected;
                    }
                    issued++;responses++;
                }else{if(issued<c.groups)gaps++;for(unsigned j=0;j<L;j++)if(d.roots[j]!=last[j])throw std::runtime_error("root hold mismatch");}
                if(d.error)throw std::runtime_error("unexpected root error");
            }
            if(!d.done||d.busy||issued!=c.groups||elapsed!=c.groups+gaps+4||d.cycles!=elapsed)throw std::runtime_error("root completion/drain mismatch "+c.name);
            bubbles+=gaps;runs++;idle();
            // Short profiles may finish before serial prefetch is complete;
            // complete those writes while idle, then use the new bank next.
            for(;prefetch<c.seeds.size();prefetch++)seed(false,other,prefetch/c.active,prefetch%c.active,c.seeds[prefetch]);
        }
        if(c.groups>=8 && cases%17==0){
            for(unsigned depth=1;depth<=4;depth++){
                load(c,0);idle();config(c,0);d.start=1;tick();d.start=0;
                for(unsigned j=0;j<depth;j++){d.request_valid=1;d.request_tag=j;tick();}
                reset();aborts++;
                // Reset must clear both banks' seed eligibility, not merely
                // recurrence valid bits. A stale profile cannot restart.
                config(c,0);d.start=1;tick();
                if(!d.done||!d.error||d.busy||d.root_valid)throw std::runtime_error("stale seed reset acceptance");
                rejects++;idle();tick();
            }
        }
        if(c.groups>=8&&!drain_tested){
            load(c,0);idle();config(c,0);d.start=1;tick();d.start=0;
            for(unsigned j=0;j<c.groups;j++){d.request_valid=1;d.request_tag=j;tick();}
            // Even held valid must not produce an extra response after the
            // last accepted group. Cancel while update results still drain.
            for(unsigned j=0;j<2;j++){tick();if(d.root_valid||d.request_ready||d.done)throw std::runtime_error("drain quarantine mismatch");}
            reset();aborts++;drain_tested=true;
        }
        cases++;
    }
    if(!f.eof()||!runs)throw std::runtime_error("incomplete vectors");
    std::cout<<"PASS lanes="<<L<<" cases="<<cases<<" runs="<<runs<<" responses="<<responses<<" checked_cycles="<<checks
        <<" bubbles="<<bubbles<<" seed_checks="<<seedchecks<<" aborts="<<aborts<<" rejects="<<rejects<<"\n";
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
