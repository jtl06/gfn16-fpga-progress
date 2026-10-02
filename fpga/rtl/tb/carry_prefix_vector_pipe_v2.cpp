#include "Vgenefer_carry_prefix_vector_pipe_v2.h"
#include "verilated.h"
#include <cstdint>
#include <fstream>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>
#ifndef TEST_LANES
#define TEST_LANES 4
#endif
#ifndef TEST_AW
#define TEST_AW 16
#endif
using I=__int128_t;
static constexpr unsigned W=TEST_LANES,AW=TEST_AW,ALL=(1u<<W)-1;
static I parse(const std::string& s){I x=0;size_t i=s[0]=='-'?1:0;for(;i<s.size();i++)x=x*10+s[i]-'0';return s[0]=='-'?-x:x;}
template<class T>static void put(T& a,I x,unsigned lane=0){for(unsigned j=0;j<3;j++)a[3*lane+j]=uint32_t(__uint128_t(x)>>(32*j));}
template<class T>static I get(const T& a,unsigned lane=0){unsigned k=3*lane;__uint128_t x=__uint128_t(a[k])|(__uint128_t(a[k+1])<<32)|(__uint128_t(a[k+2])<<64);return a[k+2]&0x80000000u?I(x)-(I(1)<<96):I(x);}
struct Request {bool sw=0,sr=0,vw=0,vr=0;unsigned sa=0,va=0,mask=ALL;I scalar=0;std::vector<I> data=std::vector<I>(W);};
int main(int argc,char** argv){try{
    Verilated::commandArgs(argc,argv);if(argc!=2)throw std::runtime_error("vectors required");
    std::ifstream f(argv[1]);if(!f)throw std::runtime_error("input open");
    Vgenefer_carry_prefix_vector_pipe_v2 d;std::vector<I> memory(1u<<AW);
    uint64_t host_checks=0;unsigned cases=0,runs=0,rejects=0,aborts=0;
    auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();};
    auto idle=[&](){d.start=0;d.load_we=0;d.read_en=0;d.vector_load_we=0;d.vector_read_en=0;};
    auto drive=[&](const Request& r){idle();d.load_we=r.sw;d.read_en=r.sr;d.host_addr=r.sa;put(d.write_data,r.scalar);
        d.vector_load_we=r.vw;d.vector_read_en=r.vr;d.vector_addr=r.va;d.vector_lane_mask=r.mask;
        for(unsigned g=0;g<W;g++)put(d.vector_write_data,r.data[g],g);};
    auto reset=[&](){idle();d.rst_n=0;tick();d.rst_n=1;tick();
        if(d.busy||d.done||d.error||d.read_valid||d.vector_read_valid||d.vector_read_mask||d.host_error)throw std::runtime_error("reset mismatch");};
    auto host=[&](const Request& r,unsigned lg){
        unsigned oldsv=d.read_valid,oldvv=d.vector_read_valid,oldmask=d.vector_read_mask,olderr=d.host_error,aritherr=d.error;
        d.size_log2=lg;drive(r);d.clk=0;d.eval();
        if(d.read_valid!=oldsv||d.vector_read_valid!=oldvv||d.vector_read_mask!=oldmask||d.host_error!=olderr)throw std::runtime_error("combinational response leaked");
        unsigned n=lg>=1&&lg<=AW ? 1u<<lg : 0;
        bool vreq=r.vw||r.vr,ok=n&&(r.va&(W-1))==0&&r.va<n;
        unsigned mask=0;for(unsigned g=0;g<W;g++)if((r.mask>>g&1)&&r.va+g<n)mask|=1u<<g;
        bool sv=!vreq&&r.sr&&!r.sw,vv=vreq&&ok&&r.vr&&!r.vw;
        if(vreq&&ok&&r.vw){for(unsigned g=0;g<W;g++)if(mask>>g&1)memory[r.va+g]=r.data[g];}
        else if(!vreq&&r.sw)memory[r.sa]=r.scalar;
        d.clk=1;d.eval();host_checks++;
        if(d.read_valid!=sv||d.vector_read_valid!=vv||d.vector_read_mask!=(vv?mask:0)||d.host_error!=(vreq&&!ok)||d.error!=aritherr)
            throw std::runtime_error("host valid/mask/error/priority mismatch check="+std::to_string(host_checks));
        if(sv&&get(d.read_data)!=memory[r.sa])throw std::runtime_error("scalar host data mismatch");
        if(vv)for(unsigned g=0;g<W;g++)if((mask>>g&1)&&get(d.vector_read_data,g)!=memory[r.va+g])throw std::runtime_error("vector host data mismatch lane="+std::to_string(g));
    };
    reset();std::mt19937 rng(0x5140cafe);unsigned init=std::min(1u<<AW,512u);
    for(unsigned i=0;i<init;i++){Request r;r.sw=1;r.sa=i;r.scalar=I(i)*-131-7;host(r,1);}
    // Random back-to-back host transactions include every arbitration class,
    // invalid vector size/address, partial/empty masks and changing active N.
    for(unsigned k=0;k<4000;k++){
        unsigned lg=1+rng()%std::min(AW,8u);if(k%17==0)lg=0;if(k%19==0)lg=AW+1;
        Request r;r.sw=rng()&1;r.sr=rng()&1;r.vw=rng()&1;r.vr=rng()&1;
        r.sa=rng()%init;r.va=rng()%init;if(k%3)r.va&=~(W-1);
        r.mask=k%7?rng()&ALL:0;r.scalar=-I(rng());for(auto& x:r.data)x=I(rng())-I(1ULL<<31);
        host(r,lg);
    }
    // Check all initialized storage after invalid writes and zero-mask accesses.
    for(unsigned i=0;i<init;i++){Request r;r.sr=1;r.sa=i;host(r,1);}
    // Reset with a valid vector response pending; valid/mask must be canceled.
    {Request r;r.vr=1;host(r,1);reset();}
    std::string mode,label,s;
    while(f>>mode>>label){
        unsigned lg,b;f>>lg>>b;unsigned n=1u<<lg;d.base=b;d.size_log2=lg;
        std::vector<I> a(n),expected(n);for(auto& x:a){f>>s;x=parse(s);}
        if(mode=="OK")for(auto& x:expected){f>>s;x=parse(s);}
        else if(mode!="BAD"&&mode!="ABORT")throw std::runtime_error("bad mode");
        if(cases%3==1){
            for(unsigned i=0;i<n;i++){Request r;r.sw=1;r.sr=1;r.sa=i;r.scalar=a[i];host(r,lg);}
        }else{
            for(unsigned i=0;i<n;i+=W){
                Request r;r.vw=1;r.vr=1;r.sw=1;r.sr=1;r.va=i;r.scalar=999;r.sa=0;
                for(unsigned g=0;g<W;g++)r.data[g]=i+g<n?a[i+g]:-999;
                if(cases%3==2){r.mask=ALL&0xaaaa;host(r,lg);r.mask=ALL&0x5555;}
                host(r,lg);
            }
        }
        idle();
        for(unsigned rep=0;rep<(mode=="OK"?3u:1u);rep++){
            // A start suppresses even malformed higher-priority host requests.
            d.base=b;d.start=1;d.vector_load_we=1;d.vector_read_en=1;d.vector_addr=1;d.vector_lane_mask=ALL;tick();
            if(d.read_valid||d.vector_read_valid||d.vector_read_mask||d.host_error)throw std::runtime_error("start host suppression mismatch");
            d.start=0;uint64_t elapsed=0;unsigned emit_ticks=0;
            while(!d.done&&elapsed<2*((n+W-1)/W)+150){
                d.start=elapsed&1;d.load_we=1;d.read_en=1;d.base=0;d.host_addr=0;put(d.write_data,0);
                d.vector_load_we=1;d.vector_read_en=1;d.vector_addr=1;d.vector_lane_mask=ALL;
                for(unsigned g=0;g<W;g++)put(d.vector_write_data,0,g);
                tick();elapsed++;
                if(d.read_valid||d.vector_read_valid||d.vector_read_mask||d.host_error)throw std::runtime_error("busy host response leaked");
                if(mode=="ABORT"&&(label=="drain"?elapsed>=2*((n+W-1)/W)+117:
                 label.rfind("emit",0)==0?d.passes==2&&++emit_ticks>=(label=="emit"?3u:unsigned(std::stoul(label.substr(4)))):elapsed>=std::stoul(label))){reset();aborts++;break;}
            }
            idle();d.base=b;
            if(mode=="ABORT")break;
            if(!d.done||d.busy||d.cycles!=elapsed)throw std::runtime_error("completion mismatch "+label);
            if(mode=="BAD"){if(!d.error)throw std::runtime_error("domain rejection missing "+label);rejects++;tick();break;}
            if(d.error||d.passes!=2)throw std::runtime_error("unexpected error "+label);
            if(d.cycles!=2*((n+W-1)/W)+118)throw std::runtime_error("carry cycle regression");
            for(unsigned i=0;i<n;i++)memory[i]=expected[i];
            std::cout<<label<<" repeat="<<rep<<" cycles="<<d.cycles<<"\n";
            if(rep==1){for(unsigned i=0;i<n;i++){Request r;r.sr=1;r.sa=i;host(r,lg);}}
            else for(unsigned i=0;i<n;i+=W){Request r;r.vr=1;r.sw=1;r.sr=1;r.scalar=123;r.va=i;r.sa=0;host(r,lg);}
            idle();runs++;
        }
        cases++;
    }
    if(!f.eof()||!runs)throw std::runtime_error("incomplete vectors");
    std::cout<<"PASS lanes="<<W<<" aw="<<AW<<" cases="<<cases<<" completed="<<runs<<" rejected="<<rejects<<" aborted="<<aborts<<" host_checks="<<host_checks<<"\n";
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
