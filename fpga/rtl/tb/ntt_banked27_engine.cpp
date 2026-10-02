#include "Vgenefer_ntt_banked27_engine.h"
#include "verilated.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdlib>
#include <limits>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#ifndef NTT_LANES
#define NTT_LANES 4
#endif
#ifndef NTT_AW
#define NTT_AW 16
#endif
using DUT=Vgenefer_ntt_banked27_engine;
#ifndef NTT_P
#define NTT_P 104857601u
#endif
constexpr uint32_t MODULUS=NTT_P;
constexpr unsigned W=NTT_LANES;
static_assert(W>=1 && W<=64 && !(W&(W-1)), "supported lane width");
constexpr uint64_t ALL=std::numeric_limits<uint64_t>::max()>>(64-W);
using Beat=std::array<uint32_t,W>;
void put(DUT&d,const Beat&a) {
#if NTT_LANES == 1
    d.vector_write_data=a[0];
#else
    for(unsigned i=0;i<W;++i)d.vector_write_data[i]=a[i];
#endif
}
uint32_t get(DUT&d,unsigned i) {
#if NTT_LANES == 1
    return d.vector_read_data;
#else
    return d.vector_read_data[i];
#endif
}
void clear_host(DUT&d) {d.load_we=0;d.root_we=0;d.read_en=0;d.vector_load_we=0;d.vector_read_en=0;d.start=0;}
void require(bool condition,const std::string&message) {if(!condition)throw std::runtime_error(message);}
uint32_t rng(uint32_t&x) {x^=x<<13;x^=x>>17;x^=x<<5;return x;}

template<class Tick> void host_fuzz(DUT&d,Tick&tick,unsigned normal_lg) {
    const unsigned physical=1u<<NTT_AW;std::vector<uint32_t> model(physical);
    clear_host(d);d.size_log2=normal_lg;
    for(unsigned i=0;i<physical;++i) {
        model[i]=(0xa5a50000u^(i*2654435761u))%MODULUS;d.load_we=1;d.read_en=1;d.host_addr=i;d.write_data=model[i];tick();
        require(!d.read_valid&&!d.vector_read_valid&&!d.vector_read_mask&&!d.host_error,"fuzz initial scalar write flags");
    }
    clear_host(d);d.vector_load_we=1;d.vector_addr=0;d.vector_lane_mask=0;
    Beat ignored{};ignored.fill(MODULUS);put(d,ignored);d.load_we=1;d.root_we=1;d.write_data=MODULUS;tick();
    require(!d.read_valid&&!d.vector_read_valid&&!d.vector_read_mask&&!d.host_error,"masked noncanonical payload was not ignored");
    uint32_t random=0x781291u+NTT_AW+W;uint64_t checked=0;bool highest_lane_seen=false;
    for(unsigned round=0;round<4000;++round) {
        clear_host(d);
        unsigned sizes[5]={0,1,unsigned(NTT_AW),unsigned(NTT_AW+1),std::min(4u,unsigned(NTT_AW))};
        d.size_log2=sizes[rng(random)%5];d.host_addr=rng(random)%physical;d.vector_addr=rng(random)%physical;
        if(round&1)d.vector_addr=unsigned(d.vector_addr)&~(W-1);
        d.load_we=rng(random)&1;d.read_en=rng(random)&1;
        d.vector_load_we=rng(random)&1;d.vector_read_en=rng(random)&1;
        d.write_data=rng(random)%MODULUS;d.vector_lane_mask=(round%11==0)?0:((uint64_t{rng(random)}<<32)|rng(random))&ALL;
        Beat payload;for(auto&v:payload)v=rng(random)%MODULUS;put(d,payload);
        const bool request=d.vector_load_we||d.vector_read_en;
        d.root_we=request&&(rng(random)&1);d.root_phase=rng(random)&3;
        unsigned n=d.size_log2>=1&&d.size_log2<=NTT_AW ? 1u<<d.size_log2:0;
        bool okay=n && !(unsigned(d.vector_addr)&(W-1)) && unsigned(d.vector_addr)<n;
        bool vec_read=request&&okay&&d.vector_read_en&&!d.vector_load_we;
        bool scalar_read=!request&&d.read_en&&!d.load_we;
        uint64_t mask=0;for(unsigned i=0;i<W;++i)if((d.vector_lane_mask>>i&1)&&unsigned(d.vector_addr)+i<n)mask|=uint64_t{1}<<i;
        if(request&&okay&&(mask>>(W-1)&1))highest_lane_seen=true;
        if(request&&okay&&d.vector_load_we)for(unsigned i=0;i<W;++i)if(mask>>i&1)model[unsigned(d.vector_addr)+i]=payload[i];
        if(!request&&d.load_we)model[d.host_addr]=d.write_data;
        tick();
        require(bool(d.host_error)==(request&&!okay),"vector host_error mismatch");
        require(bool(d.read_valid)==scalar_read,"vector/scalar priority mismatch");
        require(bool(d.vector_read_valid)==vec_read,"vector read-valid mismatch");
        require(d.vector_read_mask==(vec_read?mask:0),"vector returned mask mismatch");
        require(!d.error&&!d.busy&&!d.done,"host traffic changed arithmetic state");
        if(scalar_read)require(d.read_data==model[d.host_addr],"fuzz scalar value mismatch");
        if(vec_read)for(unsigned i=0;i<W;++i)if(mask>>i&1)require(get(d,i)==model[unsigned(d.vector_addr)+i],"fuzz vector value mismatch");
        ++checked;
    }
    require(physical<W||highest_lane_seen,"highest vector lane never exercised");
    clear_host(d);d.size_log2=normal_lg;d.read_en=1;
    for(unsigned i=0;i<physical;++i) {d.host_addr=i;tick();require(d.read_valid&&d.read_data==model[i]&&!d.host_error&&!d.vector_read_valid&&!d.vector_read_mask,"fuzz storage corruption");++checked;}
    clear_host(d);tick();std::cout<<"HOST_FUZZ PASS checks="<<checked<<"\n";
}

int main(int argc,char**argv) {
    try {
        require(argc==3,"command-file output-file required");std::ifstream in(argv[1]);std::ofstream out(argv[2]);require(bool(in)&&bool(out),"file open failed");
        DUT d;auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();};
        auto reset=[&](){clear_host(d);d.root_phase=0;d.rst_n=0;tick();
            require(!d.busy&&!d.done&&!d.read_valid&&!d.vector_read_valid&&!d.vector_read_mask&&!d.host_error,"reset flags");d.rst_n=1;tick();};
        reset();
        if(std::getenv("NTT_NONCANON")) {
            clear_host(d);d.size_log2=1;d.host_addr=0;d.write_data=MODULUS;
            std::string mode=std::getenv("NTT_NONCANON");
            if(mode=="root")d.root_we=1;
            else if(mode=="vector") {Beat payload{};payload[0]=MODULUS;put(d,payload);d.vector_load_we=1;d.vector_addr=0;d.vector_lane_mask=1;}
            else d.load_we=1;
            tick();throw std::runtime_error("missing canonical-input assertion");
        }
        for(unsigned bad:{0u,17u,31u}) {d.size_log2=bad;d.start=1;tick();d.start=0;require(d.done&&d.error&&!d.busy,"invalid size accepted");tick();reset();}
        for(unsigned phase:{1u,2u}) {d.root_phase=phase;d.op=2;d.size_log2=1;d.start=1;tick();d.start=0;require(d.done&&d.error&&!d.busy,"half table vector op accepted");tick();reset();}
        unsigned lg;require(bool(in>>lg)&&lg>=1&&lg<=NTT_AW,"bad size");unsigned n=1u<<lg;
        if(!std::getenv("NTT_SKIP_HOST_FUZZ"))host_fuzz(d,tick,lg);d.size_log2=lg;
        std::string cmd;unsigned runs=0,checks=0,resets=0,order=0,phase=0,loads=0,readouts=0;
        while(in>>cmd) {
            if(cmd=="PHASE")require(bool(in>>phase)&&phase<4,"bad phase");
            else if(cmd=="ORDER")require(bool(in>>order)&&order<2,"bad order");
            else if(cmd=="POISON_HALF") {
                clear_host(d);d.root_phase=phase;d.root_we=1;d.write_data=0;
                for(unsigned i=n/2;i<n;++i){d.host_addr=i;tick();}clear_host(d);tick();
            } else if(cmd=="LOAD"||cmd=="ROOTS"||cmd=="ROOTS_HALF") {
                unsigned count=cmd=="ROOTS_HALF"?n/2:n;std::vector<uint32_t> words(count);
                for(auto&v:words)require(bool(in>>v),"short load");clear_host(d);d.root_phase=phase;
                if(cmd=="LOAD" && (loads++%3)!=0) {
                    bool split=loads%2==0;
                    for(unsigned base=0;base<n;base+=W) {
                        Beat payload{};uint64_t mask=0;
                        for(unsigned i=0;i<W&&base+i<n;++i){payload[i]=words[base+i];mask|=uint64_t{1}<<i;}put(d,payload);
                        for(unsigned pass=0;pass<(split?2u:1u);++pass) {
                            d.vector_load_we=1;d.vector_read_en=1;d.vector_addr=base;
                            d.vector_lane_mask=split?mask&(pass?0xaaaaaaaaaaaaaaaaull:0x5555555555555555ull):mask;
                            // Suppress simultaneous scalar writes/reads AND root writes.
                            d.load_we=1;d.read_en=1;d.root_we=1;d.host_addr=base;d.write_data=0;tick();
                            require(!d.read_valid&&!d.vector_read_valid&&!d.vector_read_mask&&!d.host_error,"vector load arbitration");
                        }
                    }
                } else for(unsigned i=0;i<count;++i) {
                    d.host_addr=i;d.write_data=words[i];d.load_we=cmd=="LOAD";d.root_we=cmd!="LOAD";d.read_en=d.load_we;tick();
                    require(!d.read_valid&&!d.vector_read_valid&&!d.vector_read_mask&&!d.host_error,"scalar load arbitration");
                }
                clear_host(d);tick();
            } else if(cmd=="RUN"||cmd=="ABORT"||cmd=="ABORT_AT") {
                unsigned op,inv,abort_at=13;uint32_t scale;require(bool(in>>op>>inv>>scale)&&op<4&&inv<2,"bad run");
                if(cmd=="ABORT_AT")require(bool(in>>abort_at),"missing abort time");
                clear_host(d);d.root_phase=phase;d.dif=order;d.op=op;d.inverse=inv;d.scale=scale;
                d.vector_load_we=1;d.vector_read_en=1;d.vector_addr=1;d.vector_lane_mask=ALL;d.start=1;tick();
                require(!d.host_error&&!d.vector_read_valid&&!d.vector_read_mask,"start vector suppression");d.start=0;
                unsigned ticks=0;
                while(!d.done) {
                    d.load_we=1;d.root_we=1;d.read_en=1;d.write_data=0;d.host_addr=ticks%n;
                    d.vector_load_we=1;d.vector_read_en=1;d.vector_addr=1;d.vector_lane_mask=ALL;
                    d.root_phase=(phase+1)%4;d.start=ticks%3==0;d.op=3;d.scale=0;d.inverse=!inv;d.dif=!order;d.size_log2=0;
                    tick();++ticks;require(!d.read_valid&&!d.vector_read_valid&&!d.vector_read_mask&&!d.host_error,"busy vector suppression");
                    if(cmd!="RUN"&&ticks==abort_at){reset();++resets;for(unsigned i=0;i<12;++i){tick();require(!d.done&&!d.busy&&!d.vector_read_valid&&!d.host_error,"late reset result");}break;}
                    require(ticks<=12ull*n*(lg+2),"NTT timeout");
                }
                clear_host(d);d.size_log2=lg;
                if(cmd=="RUN") {
                    require(!d.error&&!d.busy&&d.cycles==ticks,"NTT completion status");
                    uint64_t bf=op==0?uint64_t(n/2)*lg:0,mul=(op!=0||inv)?n:0;
                    uint64_t groups=(uint64_t(n)+2*W-1)/(2*W),drain=(op==0?7*lg:0)+(mul?7:0);
                    uint64_t expected=(op==0?(groups+1)*lg:0)+(mul?(n+W-1)/W:0)+drain,roots=0;
                    if(op==0)for(unsigned s=0;s<lg;++s)roots+=groups*std::min(W,1u<<s);if(op==2)roots=n;
                    require(d.cycles==expected&&d.butterflies==bf&&d.data_reads==2*bf+mul&&d.data_writes==2*bf+mul&&d.root_reads==roots&&d.wait_cycles==drain,"operation accounting mismatch");
                    std::cout<<"RUN phase="<<phase<<" dif="<<order<<" op="<<op<<" inv="<<inv<<" n="<<n<<" cycles="<<d.cycles<<"\n";++runs;
                } else require(ticks==abort_at,"operation ended before reset injection");
                tick();require(!d.done,"done not a pulse");
            } else if(cmd=="CHECK"||cmd=="DUMP") {
                clear_host(d);
                if(readouts++%2) {
                    for(unsigned base=0;base<n;base+=W) {
                        uint64_t mask=0;for(unsigned i=0;i<W&&base+i<n;++i)mask|=uint64_t{1}<<i;
                        d.vector_read_en=1;d.vector_addr=base;d.vector_lane_mask=ALL;
                        d.load_we=1;d.read_en=1;d.root_we=1;d.root_phase=phase;d.host_addr=base;d.write_data=0;tick();
                        require(d.vector_read_valid&&d.vector_read_mask==mask&&!d.read_valid&&!d.host_error,"vector result read flags");
                        for(unsigned i=0;i<W&&base+i<n;++i)if(cmd=="CHECK") {uint32_t want;require(bool(in>>want),"short check");require(get(d,i)==want,"NTT vector mismatch index="+std::to_string(base+i));++checks;}else out<<get(d,i)<<'\n';
                    }
                } else for(unsigned i=0;i<n;++i) {
                    d.host_addr=i;d.read_en=1;tick();require(d.read_valid&&!d.vector_read_valid&&!d.vector_read_mask&&!d.host_error,"scalar result read flags");
                    if(cmd=="CHECK"){uint32_t want;require(bool(in>>want),"short check");require(d.read_data==want,"NTT mismatch index="+std::to_string(i));++checks;}else out<<d.read_data<<'\n';
                }
                clear_host(d);tick();require(!d.read_valid&&!d.vector_read_valid&&!d.vector_read_mask&&!d.host_error,"stale host response");
            } else throw std::runtime_error("unknown command");
        }
        require(in.eof()&&runs&&checks,"incomplete test");d.final();std::cout<<"PASS runs="<<runs<<" checks="<<checks<<" aborts="<<resets<<"\n";
    } catch(const std::exception&e){std::cerr<<"FAIL: "<<e.what()<<'\n';return 1;}
}
