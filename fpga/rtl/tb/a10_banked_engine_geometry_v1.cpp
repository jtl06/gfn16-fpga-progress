// Additive AW5/8/16 native geometry harness, no frozen RTL change; independent ordinary oracle.
#include "Vgenefer_a10_banked27_host16_engine_v1.h"
#include "verilated.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#ifndef A10_P
#define A10_P 104857601
#endif
#ifndef A10_G
#define A10_G 3
#endif
using DUT=Vgenefer_a10_banked27_host16_engine_v1;
#ifndef A10_AW
#define A10_AW 8
#endif
constexpr uint32_t P=A10_P,AW=A10_AW,N=1u<<AW;
static_assert(AW==5 || AW==8 || AW==16,"separately admitted geometry only");
static void require(bool b,const std::string& s){if(!b)throw std::runtime_error(s);}
static uint32_t mul(uint32_t a,uint32_t b){return uint64_t(a)*b%P;}
static uint32_t power(uint32_t a,uint32_t e){uint32_t r=1;while(e){if(e&1)r=mul(r,a);a=mul(a,a);e>>=1;}return r;}
static unsigned reverse(unsigned x){unsigned r=0;for(unsigned k=0;k<AW;++k){r=(r<<1)|(x&1);x>>=1;}return r;}
static void idle(DUT& d){d.start=0;d.load_we=0;d.read_en=0;d.vector_load_we=0;d.vector_read_en=0;
    d.profile_begin=0;d.profile_we=0;d.profile_commit=0;d.profile_abort=0;}

// Independent conventional negacyclic construction. Its cyclic twiddles depend
// on LOWER position bits, unlike the merged RTL's UPPER group-bit roots.
static std::vector<uint32_t> conventional(std::vector<uint32_t> data,bool inverse){
    const uint32_t psi=power(A10_G,(P-1)/(2*N)),omega=mul(psi,psi);
    if(!inverse){
        uint32_t weight=1;
        for(unsigned j=0;j<N;++j){data[j]=mul(data[j],weight);weight=mul(weight,psi);}
        for(unsigned span=N;span>=2;span>>=1){
            const unsigned half=span/2;const uint32_t step=power(omega,N/span);
            for(unsigned start=0;start<N;start+=span){
                uint32_t w=1;
                for(unsigned j=0;j<half;++j){
                    const uint32_t u=data[start+j],v=data[start+j+half];
                    data[start+j]=(uint64_t(u)+v)%P;
                    data[start+j+half]=mul((uint64_t(u)+P-v)%P,w);w=mul(w,step);
                }
            }
        }
    }else{
        const uint32_t inverse_omega=power(omega,P-2);
        for(unsigned span=2;span<=N;span<<=1){
            const unsigned half=span/2;const uint32_t step=power(inverse_omega,N/span);
            for(unsigned start=0;start<N;start+=span){
                uint32_t w=1;
                for(unsigned j=0;j<half;++j){
                    const uint32_t u=data[start+j],t=mul(data[start+j+half],w);
                    data[start+j]=(uint64_t(u)+t)%P;
                    data[start+j+half]=(uint64_t(u)+P-t)%P;w=mul(w,step);
                }
            }
        }
        uint32_t weight=power(N,P-2);const uint32_t inverse_psi=power(psi,P-2);
        for(unsigned j=0;j<N;++j){data[j]=mul(data[j],weight);weight=mul(weight,inverse_psi);}
    }
    return data;
}
static std::vector<uint32_t> spectrum_oracle(const std::vector<uint32_t>& a){
    if constexpr(AW<=8){
        std::vector<uint32_t> out(N);const uint32_t psi=power(A10_G,(P-1)/(2*N));
        for(unsigned k=0;k<N;++k)for(unsigned j=0;j<N;++j)
            out[k]=(out[k]+uint64_t(a[j])*power(psi,(2*reverse(k)+1)*j))%P;
        require(out==conventional(a,false),"A10_INDEPENDENT_SMALL_ORACLE_AGREEMENT");
        return out;
    }else return conventional(a,false);
}
static std::vector<uint32_t> convolution_oracle(const std::vector<uint32_t>& a,const std::vector<uint32_t>& spectrum){
    if constexpr(AW<=8){
        std::vector<uint32_t> out(N);
        for(unsigned i=0;i<N;++i)for(unsigned j=0;j<N;++j){
            const unsigned sum=i+j,k=sum%N;const uint32_t term=mul(a[i],a[j]);
            out[k]=sum<N?(uint64_t(out[k])+term)%P:(uint64_t(out[k])+P-term)%P;
        }
        auto ordinary_square=spectrum;for(auto& x:ordinary_square)x=mul(x,x);
        require(out==conventional(ordinary_square,true),"A10_INDEPENDENT_SMALL_CONVOLUTION_AGREEMENT");
        return out;
    }else{
        auto ordinary_square=spectrum;for(auto& x:ordinary_square)x=mul(x,x);
        return conventional(ordinary_square,true);
    }
}

int main(int argc,char** argv){
    try{
        VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);DUT d{&context};
        if(argc==2 && std::string(argv[1])=="--runtime-probe"){
            std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
            return context.threads()==1 && d.threads()==1 ? 0 : 2;
        }
        require(argc==1 || argc==2,"A10_ARGUMENTS");
        const std::string fault=argc==2 ? argv[1] : "normal";
        require(fault=="normal" || fault=="--fault-root" || fault=="--fault-normalization" || fault=="--fault-form","A10_FAULT_ARGUMENT");
        auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();};
        auto reset=[&](){idle(d);d.rst_n=0;tick();d.rst_n=1;tick();
            require(!d.profile_loaded && !d.profile_loading && !d.busy && !d.done && !d.read_valid && !d.vector_read_valid,"A10_RESET");};
        const uint32_t r=(uint64_t(1)<<32)%P,ri=power(r,P-2),psi=power(A10_G,(P-1)/(2*N));
        const uint32_t norm=mul(mul(r,r),power(N,P-2));
        const std::array<uint32_t,4> header={0x41313000u,N,norm,psi};
        reset();d.size_log2=AW;d.profile_size_log2=AW;d.profile_modulus=P;d.profile_format=3;
        // Strict incompatible size/field/format cannot preserve cache eligibility.
        for(unsigned bad=0;bad<3;++bad){
            idle(d);d.profile_begin=1;d.profile_size_log2=bad==0?AW-1:AW;
            d.profile_modulus=bad==1?P+1:P;d.profile_format=bad==2?2:3;
            auto epoch=d.profile_epoch;tick();
            require(d.profile_error && !d.profile_loaded && !d.profile_loading && d.profile_epoch==epoch+1,"A10_BAD_BEGIN");
        }
        d.profile_size_log2=AW;d.profile_modulus=P;d.profile_format=3;
        auto begin=[&](){idle(d);d.profile_begin=1;tick();require(d.profile_loading && !d.profile_loaded && !d.profile_error && d.profile_next_addr==0,"A10_BEGIN");};
        auto load_header=[&](){begin();for(unsigned k=0;k<4;++k){idle(d);d.profile_we=1;d.profile_addr=k;d.profile_data=header[k];tick();
            require(!d.profile_error && d.profile_next_addr==k+1,"A10_HEADER_WRITE");}
            idle(d);d.profile_commit=1;tick();require(d.profile_loaded && !d.profile_loading && !d.profile_error && d.profile_loaded_size==AW,"A10_COMMIT");idle(d);tick();};
        // Domain/N/normalization/psi corruption, wrong order and partial commit.
        for(unsigned bad=0;bad<6;++bad){begin();
            for(unsigned k=0;k<(bad<4?bad:0);++k){idle(d);d.profile_we=1;d.profile_addr=k;d.profile_data=header[k];tick();}
            idle(d);d.profile_we=bad!=5;d.profile_commit=bad==5;
            d.profile_addr=bad<4?bad:1;d.profile_data=bad<4?header[bad]^1:header[1];tick();
            require(d.profile_error && !d.profile_loaded && !d.profile_loading,"A10_BAD_HEADER_NOT_ABORTED");
            idle(d);d.start=1;d.op=0;d.inverse=0;d.dif=0;d.root_phase=1;d.scale=0;tick();
            require(d.done && d.error && !d.busy,"A10_PARTIAL_PROFILE_START");idle(d);tick();
        }
        load_header();auto committed_epoch=d.profile_epoch;idle(d);d.profile_abort=1;tick();
        require(!d.profile_loaded && !d.profile_loading && !d.profile_error && d.profile_epoch==committed_epoch+1,"A10_ABORT_EPOCH");load_header();
        // Malformed profile requests suppress host read/write as in G4 adapter.
        idle(d);d.load_we=1;d.host_addr=0;d.write_data=19;tick();idle(d);d.profile_we=1;d.profile_addr=4;d.profile_data=0;
        d.load_we=1;d.read_en=1;d.host_addr=0;d.write_data=23;d.vector_load_we=1;d.vector_read_en=1;d.vector_addr=1;tick();
        require(d.profile_error && !d.host_error && !d.read_valid && !d.vector_read_valid,"A10_PROFILE_HOST_PRIORITY");
        idle(d);d.read_en=1;tick();require(d.read_valid && d.read_data==19,"A10_PROFILE_HOST_CORRUPTION");idle(d);tick();load_header();
        auto run=[&](unsigned op,bool inverse){
            idle(d);d.op=op;d.inverse=inverse;d.dif=inverse;d.root_phase=op?0:(inverse?2:1);d.scale=0;d.size_log2=AW;
            d.start=1;tick();idle(d);require(d.busy && !d.error && !d.done,"A10_START");
            unsigned elapsed=0;while(!d.done && elapsed<AW*((N+127)/128+9)+64){tick();++elapsed;}
            require(d.done && !d.busy && !d.error && d.cycles==elapsed,"A10_TERMINAL");
            const uint64_t bf=op?0:N*AW/2;
            // Derived RTL ledger, validated here natively; not a measured record until execution.
            const uint64_t groups=(N+127)/128,point_groups=(N+63)/64;
            uint64_t expected_roots=0,expected_rom_reads=0;
            for(unsigned st=0;st<AW;++st){
                const unsigned bits=std::min(AW,7u)>st+1 ? std::min(AW,7u)-st-1 : 0;
                expected_roots+=groups*(1u<<bits);
                if((st<7 && groups>1) || (st>=7 && st<AW-1))expected_rom_reads+=groups;
            }
            require(d.cycles==(op?point_groups+7:AW*(groups+9)) && d.wait_cycles==(op?7:AW*8) && d.seed_setup_cycles==0 &&
                d.butterflies==bf && d.data_reads==(op?N:2*bf) && d.data_writes==(op?N:2*bf) &&
                d.root_reads==(op?0:expected_roots) && d.root_rom_reads==(op?0:expected_rom_reads) &&
                d.normalization_products==(inverse?N/2:0),"A10_CYCLE_LEDGER");
            auto cycles=d.cycles;tick();require(!d.done,"A10_DONE_PULSE");return cycles;
        };
        auto read_compare=[&](const std::vector<uint32_t>& expected,const std::string& phase){
            idle(d);for(unsigned k=0;k<N;++k){d.read_en=1;d.host_addr=k;tick();
                require(d.read_valid && !d.host_error && d.read_data<P,"A10_READ_FLAGS");
                if(d.read_data!=expected[k]){
                    std::string kind=fault=="--fault-root"?"ROOT":fault=="--fault-normalization"?"NORMALIZATION":fault=="--fault-form"?"FORM":"CONTROL";
                    throw std::runtime_error("A10_NUMERIC_"+kind+"_MISMATCH phase="+phase+" index="+std::to_string(k));
                }
            }idle(d);tick();require(!d.read_valid,"A10_STALE_READ");};
        uint64_t total=0;unsigned cases=0;
        for(unsigned trial=0;trial<5;++trial){
            std::vector<uint32_t> a(N),spectrum(N),squared(N),convolution(N);
            for(unsigned k=0;k<N;++k)a[k]=trial==0?(k==0?1:0):trial==1?(k==N-1?P-1:0):
                trial==2?P-1:uint32_t((uint64_t(k+1)*2654435761u+uint64_t(trial)*104729u)%P);
            idle(d);for(unsigned k=0;k<N;k+=16){d.vector_load_we=1;d.vector_addr=k;d.vector_lane_mask=0xffff;
                for(unsigned lane=0;lane<16;++lane)d.vector_write_data[lane]=a[k+lane];tick();require(!d.host_error,"A10_VECTOR_LOAD");}
            idle(d);tick();
            spectrum=spectrum_oracle(a);
            total+=run(0,false);read_compare(spectrum,"forward");
            for(unsigned k=0;k<N;++k)squared[k]=mul(mul(spectrum[k],spectrum[k]),ri);
            total+=run(1,false);read_compare(squared,"square");
            convolution=convolution_oracle(a,spectrum);
            total+=run(0,true);read_compare(convolution,"inverse");++cases;
        }
        // Reset midtransform invalidates root/header and suppresses delayed outputs.
        idle(d);d.op=0;d.inverse=0;d.dif=0;d.root_phase=1;d.start=1;tick();idle(d);for(unsigned k=0;k<5;++k)tick();reset();
        for(unsigned k=0;k<12;++k){tick();require(!d.done && !d.busy && !d.read_valid && !d.vector_read_valid,"A10_RESET_CONTINUITY");}
        require(fault=="normal","A10_FAULT_NOT_DETECTED");
        std::cout<<"A10_ENGINE_PASS aw="<<AW<<" field="<<P<<" cases="<<cases<<" operations="<<3*cases<<" residues="<<3*cases*N<<" cycles="<<total<<" profile_words=4\n";
        d.final();return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
