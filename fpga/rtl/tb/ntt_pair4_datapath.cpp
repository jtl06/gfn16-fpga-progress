#include "Vgenefer_ntt_pair4_datapath.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

#ifndef FIELD_P
#define FIELD_P 104857601u
#endif
#ifndef FIELD_G
#define FIELD_G 3u
#endif
#ifndef GROUP_AW
#define GROUP_AW 12
#endif
using Words=std::array<uint32_t,4>;
struct Group { Words data, expected; std::array<uint32_t,2> first,second; };
static Vgenefer_ntt_pair4_datapath d;
static constexpr uint64_t p=FIELD_P;
static uint64_t checks=0,commits=0,runs=0,aborts=0,rejections=0,faults=0;
static uint32_t mul(uint64_t x,uint64_t y) { return x*y%p; }
static uint32_t power(uint64_t x,uint64_t e) { uint64_t y=1;while(e){if(e&1)y=mul(y,x);x=mul(x,x);e>>=1;}return y; }
static uint32_t mont(uint32_t x) { return mul(x,(uint64_t(1)<<32)%p); }
static void need(bool ok,const char* why) { if(!ok)throw std::runtime_error(why);++checks; }
static std::array<uint32_t,2> butterfly(uint64_t a,uint64_t b,uint32_t w,bool dif) {
    if(dif)return {uint32_t((a+b)%p),mul((a+p-b)%p,w)};
    uint64_t product=mul(b,w);return {uint32_t((a+product)%p),uint32_t((a+p-product)%p)};
}
static void edge() {d.clk=1;d.eval();d.clk=0;d.eval();}
static void reset() {d.start=0;d.rst_n=0;d.eval();edge();need(!d.busy&&!d.done&&!d.error&&!d.root_read&&!d.write_valid,"reset leakage");d.rst_n=1;d.eval();}
static void run(unsigned count,bool mode,bool inverse,int abort_at=-1,bool tag_fault=false) {
    std::mt19937 rng(930301+count+1000*mode+2000*inverse);
    std::vector<Group> groups(count);
    uint32_t omega=power(FIELD_G,(p-1)/65536);if(inverse)omega=power(omega,p-2);
    uint32_t quarter=power(omega,16384);
    for(unsigned g=0;g<count;++g) {
        auto &q=groups[g];
        for(unsigned k=0;k<4;++k)q.data[k]=g%7==0?0:g%7==1?p-1:rng()%p;
        if(g%2==0) {
            // Actual adjacent top-stage roots for N65536, in dependency order.
            uint32_t w=power(omega,g%16384),v=mul(w,w),wi=mul(w,quarter);
            q.first=mode?std::array<uint32_t,2>{w,wi}:std::array<uint32_t,2>{v,v};
            q.second=mode?std::array<uint32_t,2>{v,v}:std::array<uint32_t,2>{w,wi};
        } else {
            for(unsigned k=0;k<2;++k) {
                q.first[k]=g%11==1?0:g%11==3?p-1:rng()%p;
                q.second[k]=g%11==1?p-1:g%11==3?1:rng()%p;
            }
        }
        const auto &a=q.data;
        auto x=butterfly(a[0],a[mode?2:1],q.first[0],mode);
        auto y=butterfly(a[mode?1:2],a[3],q.first[1],mode);
        // Both modes combine first-layer sums together and differences
        // together. Only the initial pairing and final placement differ.
        auto u=butterfly(x[0],y[0],q.second[0],mode);
        auto v=butterfly(x[1],y[1],q.second[1],mode);
        q.expected=mode?Words{u[0],u[1],v[0],v[1]}:Words{u[0],v[0],u[1],v[1]};
    }
    d.group_count=count;d.dif=mode;d.start=1;edge();d.start=0;d.eval();
    need(d.busy&&!d.error&&!d.done,"start contract");
    unsigned writes=0,reads=0,root_reads=0;
    for(unsigned tick=0;tick<=2*count+12;++tick) {
        if(int(tick)==abort_at) { reset();++aborts;return; }
        need(d.busy&&!d.done,"pipeline contract");
        need(bool(d.error)==(tag_fault && tick>14),"fault timing mismatch");
        if(d.root_read) {
            need(d.root_group<count,"root group bounds");auto &q=groups[d.root_group];
            auto &r=d.root_second?q.second:q.first;
            d.root_beat=uint64_t(mont(r[0]))|(uint64_t(mont(r[1]))<<32);++root_reads;
        } else d.root_beat=~uint64_t(0);
        if(d.data_read) {
            need(d.root_read&&!d.root_second,"unexpected data read");
            for(unsigned k=0;k<4;++k)d.data_beat[k]=mont(groups[d.root_group].data[k]);
            ++reads;
        } else for(unsigned k=0;k<4;++k)d.data_beat[k]=~uint32_t(0);
        d.eval();
        bool expected_write=tick>=14 && tick%2==0;
        if(tag_fault && tick>=14)need(!d.write_valid,"unsafe write on bad commit token");
        else need(bool(d.write_valid)==expected_write,"write event mismatch");
        if(d.write_valid) {
            unsigned g=(tick-14)/2;need(d.write_group==g,"write tag mismatch");
            for(unsigned k=0;k<4;++k)need(d.write_data[k]==mont(groups[g].expected[k]),"arithmetic mismatch");
            ++writes;++commits;
        }
        d.dif=!mode;d.group_count=0;d.start=(tick%11==3);edge();d.start=0;d.eval();
    }
    need(!d.busy&&d.done&&bool(d.error)==tag_fault,"completion contract");
    need(d.active_cycles==2*count+13,"cycle contract");
    need(writes==(tag_fault?0:count)&&reads==count&&root_reads==2*count,"traffic count mismatch");++runs;
    if(tag_fault)++faults;
}
static void invalid(unsigned count) {
    d.start=1;d.group_count=count;edge();d.start=0;d.eval();
    need(!d.busy&&d.done&&d.error&&!d.root_read&&!d.write_valid,"invalid group count accepted");
    edge();need(!d.done&&d.error,"invalid count error persistence");++rejections;
}
int main(int argc,char**argv) {
    Verilated::commandArgs(argc,argv);
    try {
        reset();
        const unsigned max_groups=1u<<GROUP_AW;
        if(argc==2 && std::string(argv[1])=="fault") {
            run(2,true,false,-1,true);
            // Fault injection is mode-qualified; a legal start must clear
            // sticky error, without resetting or changing frozen pipelines.
            run(2,false,true);reset();run(1,false,false);
        } else {
            for(bool mode:{false,true})for(bool inverse:{false,true})
                for(unsigned count:{1u,2u,3u,4u,7u,8u,16u,31u,64u,512u,2048u,4096u})
                    if(count<=max_groups)run(count,mode,inverse);
            unsigned short_count=max_groups<3?max_groups:3;
            for(bool mode:{false,true})for(int t=0;t<=int(2*short_count+13);++t) {
                if(t==int(2*short_count+13)) {run(short_count,mode,false);reset();++aborts;}
                else run(short_count,mode,false,t);
                run(short_count,!mode,true);
            }
            invalid(0);run(1,false,false);
            invalid(max_groups+1);run(1,true,true);
        }
        edge();need(!d.done,"done pulse");
        std::cout<<"{\"status\":\"passed\",\"p\":"<<p<<",\"generator\":"<<FIELD_G
                 <<",\"group_aw\":"<<GROUP_AW<<",\"radix_bits\":32,\"runs\":"<<runs
                 <<",\"aborts\":"<<aborts<<",\"commits\":"<<commits<<",\"checks\":"<<checks
                 <<",\"count_rejections\":"<<rejections<<",\"commit_faults\":"<<faults<<"}\n";
    } catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}
    return 0;
}
