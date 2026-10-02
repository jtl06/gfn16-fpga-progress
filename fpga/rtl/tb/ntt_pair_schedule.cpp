#include "Vgenefer_ntt_pair_schedule.h"
#include "verilated.h"
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <vector>

#ifndef GROUP_AW
#define GROUP_AW 16
#endif
struct Event { int root=-1, root_kind=0, issue=-1, issue_kind=0, hold=-1, commit=-1; };
static Vgenefer_ntt_pair_schedule d;
static uint64_t checks=0, runs=0, aborts=0;
static void need(bool ok,const char* message) { if(!ok) throw std::runtime_error(message); ++checks; }
static void edge() { d.clk=1;d.eval();d.clk=0;d.eval(); }
static void reset() {
    d.start=0;d.rst_n=0;d.eval();edge();
    need(!d.busy && !d.done && !d.error && !d.root_read && !d.issue && !d.hold_first && !d.commit,"reset leaked events");
    d.rst_n=1;d.eval();
}
static void run(unsigned groups,int abort_at=-1) {
    std::vector<Event> schedule(2*groups+15);
    // Explicit reference event list, independent of DUT tick range comparators.
    for(unsigned g=0;g<groups;++g) {
        auto &a=schedule[2*g];need(a.root<0,"reference read collision");a.root=g;
        auto &b=schedule[2*g+7];need(b.root<0,"reference read collision");b.root=g;b.root_kind=1;b.hold=g;
        auto &ia=schedule[2*g+1];need(ia.issue<0,"reference issue collision");ia.issue=g;
        auto &ib=schedule[2*g+8];need(ib.issue<0,"reference issue collision");ib.issue=g;ib.issue_kind=1;
        schedule[2*g+14].commit=g;
    }
    d.group_count=groups;d.start=1;edge();d.start=0;d.eval();
    need(d.busy && !d.done && !d.error && d.active_cycles==0,"start contract");
    int held=-1;
    for(unsigned tick=0;tick<=2*groups+12;++tick) {
        if(int(tick)==abort_at) { reset();++aborts;return; }
        const auto &e=schedule[tick];
        need(d.busy && !d.done && !d.error && d.active_cycles==tick,"active contract");
        need(bool(d.root_read)==(e.root>=0) && bool(d.issue)==(e.issue>=0) &&
             bool(d.hold_first)==(e.hold>=0) && bool(d.commit)==(e.commit>=0),"event mismatch");
        if(e.root>=0)need(d.root_group==unsigned(e.root) && d.root_second==e.root_kind,"root tag mismatch");
        if(e.issue>=0)need(d.issue_group==unsigned(e.issue) && d.issue_second==e.issue_kind,"issue tag mismatch");
        if(e.hold>=0) {
            need(held<0 && d.hold_group==unsigned(e.hold),"hold overwrite/tag mismatch");
            held=e.hold;
        }
        if(e.issue>=0 && e.issue_kind==1) { need(held==e.issue,"second issue without held group");held=-1; }
        if(e.commit>=0)need(d.commit_group==unsigned(e.commit),"commit tag mismatch");
        // Attempts to replace the operation while busy must not reconfigure it.
        d.start=(tick%5==2);d.group_count=(tick%3==0)?0:((1u<<GROUP_AW)+1);
        edge();d.start=0;d.eval();
    }
    need(!d.busy && d.done && !d.error && d.active_cycles==2*groups+13,"completion edge/count");
    need(held<0 && !d.root_read && !d.issue && !d.hold_first && !d.commit,"completion leaked events");
    ++runs;
}
int main(int argc,char**argv) {
    Verilated::commandArgs(argc,argv);
    try {
        reset();
        for(unsigned invalid : {0u,(1u<<GROUP_AW)+1}) {
            d.group_count=invalid;d.start=1;edge();d.start=0;d.eval();
            need(d.done && d.error && !d.busy,"invalid count accepted");
            need(!d.root_read && !d.issue && !d.commit,"invalid count issued work");
        }
        for(unsigned g=1;g<=16 && g<=(1u<<GROUP_AW);++g) run(g);
        run(1u<<GROUP_AW);
        if(GROUP_AW>=12) for(unsigned g : {31u,512u,2048u,4095u}) run(g);
        for(unsigned g : {1u,3u,8u}) {
            if(g>(1u<<GROUP_AW))continue;
            for(unsigned tick=0;tick<=2*g+12;++tick) { run(g,tick);run(GROUP_AW==1?2:3); }
        }
        edge();need(!d.done,"done is not a pulse");
        std::cout<<"PASS group_aw="<<GROUP_AW<<" runs="<<runs<<" aborts="<<aborts<<" checks="<<checks<<"\n";
    } catch(const std::exception&e) { std::cerr<<e.what()<<"\n";return 1; }
    return 0;
}
