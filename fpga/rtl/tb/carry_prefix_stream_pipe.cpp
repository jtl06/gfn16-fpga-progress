#include "Vgenefer_carry_prefix_stream_pipe.h"
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
    Vgenefer_carry_prefix_stream_pipe d;std::vector<I> memory(1u<<AW);
    uint64_t host_checks=0,stream_checks=0,stalls=0;unsigned cases=0,runs=0,rejects=0,aborts=0,protocol=0;
    auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();};
    auto idle=[&](){d.start=0;d.stream_valid=0;d.load_we=0;d.read_en=0;d.vector_load_we=0;d.vector_read_en=0;};
    auto reset=[&](){idle();d.rst_n=0;tick();d.rst_n=1;tick();
        if(d.busy||d.done||d.error||d.read_valid||d.vector_read_valid||d.vector_read_mask||d.host_error||d.stream_ready)throw std::runtime_error("reset mismatch");};
    auto host=[&](const Request& r,unsigned lg){
        unsigned oldsv=d.read_valid,oldvv=d.vector_read_valid,oldmask=d.vector_read_mask,olderr=d.host_error,aritherr=d.error;
        idle();d.size_log2=lg;d.load_we=r.sw;d.read_en=r.sr;d.host_addr=r.sa;put(d.write_data,r.scalar);
        d.vector_load_we=r.vw;d.vector_read_en=r.vr;d.vector_addr=r.va;d.vector_lane_mask=r.mask;
        for(unsigned g=0;g<W;g++)put(d.vector_write_data,r.data[g],g);
        d.clk=0;d.eval();
        if(d.read_valid!=oldsv||d.vector_read_valid!=oldvv||d.vector_read_mask!=oldmask||d.host_error!=olderr)throw std::runtime_error("combinational response leaked");
        unsigned n=lg>=1&&lg<=AW ? 1u<<lg : 0;
        bool vreq=r.vw||r.vr,ok=n&&(r.va&(W-1))==0&&r.va<n,wok=r.scalar==I(int32_t(r.scalar));
        unsigned mask=0;for(unsigned g=0;g<W;g++)if((r.mask>>g&1)&&r.va+g<n)mask|=1u<<g;
        if(vreq){wok=true;for(unsigned g=0;g<W;g++)if((mask>>g&1)&&r.data[g]!=I(int32_t(r.data[g])))wok=false;}
        bool sv=!vreq&&r.sr&&!r.sw,vv=vreq&&ok&&r.vr&&!r.vw;
        bool err=vreq?(!ok||(r.vw&&!wok)):(r.sw&&!wok);
        if(vreq&&ok&&r.vw&&wok){for(unsigned g=0;g<W;g++)if(mask>>g&1)memory[r.va+g]=r.data[g];}
        else if(!vreq&&r.sw&&wok)memory[r.sa]=r.scalar;
        d.clk=1;d.eval();host_checks++;
        if(d.read_valid!=sv||d.vector_read_valid!=vv||d.vector_read_mask!=(vv?mask:0)||d.host_error!=err||d.error!=aritherr)
            throw std::runtime_error("host valid/mask/error/priority mismatch check="+std::to_string(host_checks));
        if(sv&&get(d.read_data)!=memory[r.sa])throw std::runtime_error("scalar host data mismatch");
        if(vv)for(unsigned g=0;g<W;g++)if((mask>>g&1)&&get(d.vector_read_data,g)!=memory[r.va+g])throw std::runtime_error("vector host data mismatch");
    };
    reset();std::mt19937 rng(0x5140cafe);unsigned init=std::min(1u<<AW,512u);
    for(unsigned i=0;i<init;i++){Request r;r.sw=1;r.sa=i;r.scalar=I(i)*-131-7;host(r,1);}
    for(unsigned k=0;k<5000;k++){
        unsigned lg=1+rng()%std::min(AW,8u);if(k%17==0)lg=0;if(k%19==0)lg=AW+1;
        Request r;r.sw=rng()&1;r.sr=rng()&1;r.vw=rng()&1;r.vr=rng()&1;
        r.sa=rng()%init;r.va=rng()%init;if(k%3)r.va&=~(W-1);
        r.mask=k%7?rng()&ALL:0;r.scalar=int32_t(rng());for(auto& x:r.data)x=int32_t(rng());
        if(k%5==0)r.scalar=I(1)<<60;if(k%7==0)r.data[0]=-(I(1)<<80);
        host(r,lg);
    }
    for(unsigned i=0;i<init;i++){Request r;r.sr=1;r.sa=i;host(r,1);}
    {Request r;r.vr=1;host(r,1);reset();}
    std::string mode,label,s;
    while(f>>mode>>label){
        unsigned lg,b;f>>lg>>b;unsigned n=1u<<lg,groups=(n+W-1)/W,mask=n<W?(1u<<n)-1:ALL;
        std::vector<I> a(n),expected(n);for(auto& x:a){f>>s;x=parse(s);}
        if(mode=="OK")for(auto& x:expected){f>>s;x=parse(s);}
        else if(mode!="BAD"&&mode!="ABORT")throw std::runtime_error("bad mode");
        for(unsigned rep=0;rep<(mode=="OK"?3u:1u);rep++){
            idle();d.base=b;d.size_log2=lg;d.start=1;d.stream_valid=1;d.stream_addr=1;d.stream_mask=0;
            d.vector_load_we=1;d.vector_read_en=1;d.vector_addr=1;tick();
            if(d.stream_ready||d.read_valid||d.vector_read_valid||d.host_error)throw std::runtime_error("start suppression mismatch");
            uint64_t elapsed=0,bubbles=0;unsigned row=0,emit_ticks=0;bool seen_ready=false;
            while(!d.done&&elapsed<4*groups+180){
                d.start=elapsed&1;d.load_we=1;d.read_en=1;d.base=0;d.host_addr=0;put(d.write_data,I(1)<<80);
                d.vector_load_we=1;d.vector_read_en=1;d.vector_addr=1;d.vector_lane_mask=ALL;
                d.clk=0;d.eval();bool ready=d.stream_ready;
                if(seen_ready&&row<groups&&!ready)throw std::runtime_error("downstream stream stall");
                if(row==groups&&ready)throw std::runtime_error("ready after final row");
                bool bubble=ready&&rep&&(rep==1?elapsed%4==0:rng()%3==0);
                d.stream_valid=!bubble;d.stream_addr=ready?row*W:1;d.stream_mask=ready?mask:0;
                for(unsigned g=0;g<W;g++)put(d.stream_data,ready&&row*W+g<n?a[row*W+g]:(I(1)<<94),g);
                // Also exercise a well-behaved producer holding its first
                // valid group stable throughout all setup backpressure.
                if(rep==1&&!seen_ready&&!ready){d.stream_addr=0;d.stream_mask=mask;
                    for(unsigned g=0;g<W;g++)put(d.stream_data,g<n?a[g]:(I(1)<<94),g);}
                if(ready){seen_ready=true;stream_checks++;if(bubble)bubbles++;else row++;}
                tick();elapsed++;
                if(d.read_valid||d.vector_read_valid||d.vector_read_mask||d.host_error)throw std::runtime_error("busy host response leaked");
                if(mode=="ABORT"&&(label=="drain"?elapsed>=2*groups+116:
                    label.rfind("emit",0)==0?d.passes==2&&++emit_ticks>=(label=="emit"?3u:unsigned(std::stoul(label.substr(4)))):elapsed>=std::stoul(label))){
                    bool before_emit=d.passes!=2;reset();aborts++;
                    if(before_emit){Request r;r.vr=1;host(r,lg);}
                    break;}
            }
            idle();d.base=b;
            if(mode=="ABORT")break;
            if(!d.done||d.busy||d.cycles!=elapsed)throw std::runtime_error("completion mismatch "+label);
            if(mode=="BAD"){if(!d.error)throw std::runtime_error("domain rejection missing "+label);rejects++;tick();break;}
            if(d.error||d.passes!=2)throw std::runtime_error("unexpected error "+label);
            if(d.cycles!=2*groups+125+3*unsigned(__builtin_ctz(W))+bubbles)throw std::runtime_error("carry cycle regression "+label+" got="+std::to_string(d.cycles));
            for(unsigned i=0;i<n;i++)memory[i]=expected[i];
            if(rep==1){for(unsigned i=0;i<n;i++){Request r;r.sr=1;r.sa=i;host(r,lg);}}
            else for(unsigned i=0;i<n;i+=W){Request r;r.vr=1;r.sw=1;r.sr=1;r.scalar=123;r.va=i;host(r,lg);}
            idle();runs++;stalls+=bubbles;a=expected;
            if(lg==16&&rep==0)std::cout<<label<<" cycles="<<elapsed<<"\n";
        }
        cases++;
    }
    if(!f.eof()||!runs)throw std::runtime_error("incomplete vectors");
    // Malformed accepted rows must abort. No whole coefficient row may enter
    // the divider unless its address, exact mask and every active lane pass.
    unsigned plg=std::min(AW,5u),pn=1u<<plg,pg=(pn+W-1)/W,pm=pn<W?(1u<<pn)-1:ALL;
    for(unsigned fault=0;fault<9;fault++){
        idle();d.base=604832956;d.size_log2=plg;d.start=1;tick();d.start=0;
        for(unsigned wait=0;!d.stream_ready&&wait<100;wait++)tick();
        if(!d.stream_ready)throw std::runtime_error("stream readiness timeout");
        if(fault==7||fault==8){
            // A truncated stream and reset in the divider pipeline must not
            // invent completion. For N2 there is only one group to issue.
            if(fault==8){d.stream_valid=1;d.stream_addr=0;d.stream_mask=pm;for(unsigned g=0;g<W;g++)put(d.stream_data,3,g);tick();}
            d.stream_valid=0;for(unsigned j=0;j<(fault==7?30u:3u);j++){tick();if(d.done)throw std::runtime_error("truncated stream completed");}
            reset();aborts++;continue;
        }
        d.stream_valid=1;d.stream_addr=0;d.stream_mask=pm;for(unsigned g=0;g<W;g++)put(d.stream_data,0,g);
        if(fault==0)d.stream_addr=1;
        if(fault==1)d.stream_mask=pm^1;
        if(fault==2)d.stream_mask=0;
        if(fault==3)put(d.stream_data,I(1)<<94,std::min(W,pn)-1);
        if(fault==4)put(d.stream_data,-(I(1)<<94),0);
        if(fault==5){if(pg>1){tick();d.stream_addr=0;}else d.stream_mask=pm^(1u<<(W-1));}
        if(fault==6){if(pg>1)d.stream_addr=W;else d.stream_mask=pm^(1u<<(W-1));}
        tick();if(!d.done||!d.error||d.busy)throw std::runtime_error("protocol rejection missing fault="+std::to_string(fault));
        protocol++;idle();
        if(fault==5){
            // Restart on the very next edge with a different base and N.
            // For AW16, a legal earlier row is still inside the dividers
            // when the repeated address aborts the prior operation.
            d.base=97;d.size_log2=1;d.start=1;tick();d.start=0;
            for(unsigned j=0;!d.stream_ready&&j<100;j++)tick();
            if(!d.stream_ready)throw std::runtime_error("immediate restart readiness failed");
            d.stream_valid=1;d.stream_addr=0;d.stream_mask=3;
            for(unsigned g=0;g<W;g++)put(d.stream_data,0,g);tick();d.stream_valid=0;
            for(unsigned j=0;!d.done&&j<100;j++)tick();
            if(!d.done||d.error||d.cycles!=127+3*unsigned(__builtin_ctz(W)))throw std::runtime_error("immediate restart failed");
            memory[0]=0;memory[1]=0;Request r;r.vr=1;host(r,1);idle();runs++;
        }else tick();
    }
    // Verify recovery without a reset after rejection and after canceled data.
    idle();d.base=97;d.size_log2=1;d.start=1;tick();d.start=0;
    for(unsigned j=0;!d.stream_ready&&j<100;j++)tick();
    d.stream_valid=1;d.stream_addr=0;d.stream_mask=3;
    for(unsigned g=0;g<W;g++)put(d.stream_data,g==0?-1:0,g);tick();d.stream_valid=0;
    for(unsigned j=0;!d.done&&j<100;j++)tick();
    if(!d.done||d.error)throw std::runtime_error("recovery failed");
    memory[0]=-1;memory[1]=0;Request r;r.vr=1;host(r,1);if(get(d.vector_read_data)!=-1||get(d.vector_read_data,1)!=0)throw std::runtime_error("recovery digits mismatch");
    std::cout<<"PASS lanes="<<W<<" aw="<<AW<<" cases="<<cases<<" completed="<<runs+1<<" rejected="<<rejects
        <<" aborted="<<aborts<<" protocol="<<protocol<<" host_checks="<<host_checks<<" stream_checks="<<stream_checks<<" bubbles="<<stalls<<"\n";
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
