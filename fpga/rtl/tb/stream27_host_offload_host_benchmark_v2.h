/* Private synthetic CPU benchmark. Include in the source-pinned Linux native
 * harness and expose as a SEPARATE --host-benchmark command. It never accepts
 * a DUT object, evaluates HDL, or claims transport/overlap/PRP equivalence.
 */
#ifndef GFN16_HOST_OFFLOAD_BENCHMARK_V2_H
#define GFN16_HOST_OFFLOAD_BENCHMARK_V2_H
#include "stream27_host_offload_host_v2.h"
#include <algorithm>
#include <array>
#include <chrono>
#include <ctime>
#include <iomanip>
#include <initializer_list>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#if defined(__linux__)
#include <unistd.h>
#endif

static inline void r14_host_need(bool ok,const char *why) {
    if(!ok)throw std::runtime_error(std::string("R14_HOST_CPU_")+why);
}
static inline std::string r14_host_hex(const std::vector<uint8_t>& bytes) {
    static const char hex[]="0123456789abcdef";std::string out;out.reserve(2*bytes.size());
    for(uint8_t b:bytes){out.push_back(hex[b>>4]);out.push_back(hex[b&15]);}return out;
}
static inline unsigned r14_host_selfcheck() {
    const uint32_t n=32,base=1009,generation=7;const uint64_t owner=(UINT64_C(19)<<24)|(UINT64_C(65535)<<8)|7;
    std::array<uint8_t,32> profile;std::vector<uint8_t> digits(4*n),correction(128),raw(4*(n+32));
    std::vector<uint8_t> numeric(4*(3*n+96),0xa5),canonical(4*n,0xa5);
    gfn16_b_final_info info={{77,78,79},80};unsigned checks=0;
    auto make_profile=[&](){r14_host_need(gfn16_b_profile_make(n,base,generation,profile.data(),32)==0,"PROFILE");};
    make_profile();
    for(unsigned j=0;j<n;++j)gfn16_b_store32(digits.data()+4*j,j==11 ? UINT32_MAX : j*17);
    for(unsigned j=0;j<32;++j)gfn16_b_store32(correction.data()+4*j,uint32_t(int(j%5)-2));
    r14_host_need(gfn16_b_cold_write(n,profile.data(),32,1,1,owner,owner,digits.data(),digits.size(),
        correction.data(),correction.size(),numeric.data(),numeric.size())==0,"COLD");
    static const uint32_t prime[3]={104857601,69206017,67239937};
    size_t at=0;
    for(unsigned f=0;f<3;++f)for(unsigned row=0;row<n/16;++row)for(unsigned lane=0;lane<16;++lane){
        unsigned block=0;for(unsigned bit=0;bit<4;++bit)block|=((lane>>bit)&1)<<(3-bit);
        unsigned j=block*(n/16)+row;
        uint32_t want=j==11 ? prime[f]-1 : j*17%prime[f];
        r14_host_need(gfn16_b_load32(numeric.data()+4*at++)==want,"COLD_FIELD_ROW");++checks;
    }
    for(unsigned high=0;high<2;++high)for(unsigned f=0;f<3;++f)for(unsigned lane=0;lane<16;++lane){
        int64_t value=int((16*high+lane)%5)-2,rem=value%prime[f];if(rem<0)rem+=prime[f];
        r14_host_need(gfn16_b_load32(numeric.data()+4*at++)==uint32_t(rem),"UNSCALED_CORRECTION");++checks;
    }
    auto final=[&](uint64_t actual,uint64_t expected,size_t bytes=0){
        return gfn16_b_final_decode(n,profile.data(),32,1,1,actual,expected,raw.data(),
            bytes ? bytes:raw.size(),canonical.data(),canonical.size(),&info);};
    for(unsigned representation=0;representation<2;++representation){
        std::fill(raw.begin(),raw.end(),0);
        if(representation)for(unsigned j=0;j<n;++j)gfn16_b_store32(raw.data()+4*j,base-1);
        gfn16_b_store32(raw.data()+4*n,representation ? 1:UINT32_MAX);
        r14_host_need(final(owner,owner)==0 && info.special==1,"SPECIAL_RESULT");
        for(unsigned j=0;j<n;++j){r14_host_need(gfn16_b_load32(canonical.data()+4*j)==(j ? 0:UINT32_MAX),"SPECIAL_WORD");++checks;}
        const int sign=representation ? 1:-1;
        r14_host_need(info.carry[0]==sign && info.carry[1]==-sign && info.carry[2]==sign,"SPECIAL_CARRIES");++checks;
    }
    std::fill(raw.begin(),raw.end(),0);
    for(unsigned row=0;row<n/16;++row)for(unsigned lane=0;lane<16;++lane)
        gfn16_b_store32(raw.data()+4*(row*16+lane),lane*(n/16)+row+1);
    r14_host_need(final(owner,owner)==0 && !info.special,"NORMAL_FINAL");
    for(unsigned j=0;j<n;++j){r14_host_need(gfn16_b_load32(canonical.data()+4*j)==j+1,"NATURAL_CARRY_TRANSPOSE");++checks;}
    const std::vector<uint8_t> goodraw=raw;
    auto rejected=[&](int expected,int actual){
        r14_host_need(actual==expected,"TYPED_REJECTION");
        r14_host_need(std::all_of(canonical.begin(),canonical.end(),[](uint8_t b){return b==0xa5;}),"ATOMIC_OUTPUT");
        r14_host_need(info.carry[0]==77 && info.carry[1]==78 && info.carry[2]==79 && info.special==80,"ATOMIC_INFO");++checks;
    };
    auto sentinel=[&](){std::fill(canonical.begin(),canonical.end(),0xa5);info={{77,78,79},80};};
    for(uint64_t bit:{UINT64_C(1),UINT64_C(1)<<8,UINT64_C(1)<<24,UINT64_C(1)<<56}){
        sentinel();rejected(GFN16_B_OWNER,final(owner^bit,owner));}
    sentinel();rejected(GFN16_B_OWNER,final(owner,owner^1)); // reset changes expected generation.
    sentinel();rejected(GFN16_B_LENGTH,final(owner,owner,raw.size()-4));
    sentinel();rejected(GFN16_B_LENGTH,final(owner,owner,raw.size()+4));
    gfn16_b_store32(raw.data()+4*(n-1),base);sentinel();rejected(GFN16_B_DIGIT,final(owner,owner));raw=goodraw;
    gfn16_b_store32(raw.data()+4*(n+31),2*n+385);sentinel();rejected(GFN16_B_CORRECTION,final(owner,owner));raw=goodraw;
    profile[31]^=0x80;sentinel();rejected(GFN16_B_PROFILE,final(owner,owner));make_profile();
    std::fill(numeric.begin(),numeric.end(),0x5a);gfn16_b_store32(digits.data()+4*(n-1),UINT32_MAX-1);
    r14_host_need(gfn16_b_cold_write(n,profile.data(),32,1,1,owner,owner,digits.data(),digits.size(),
        correction.data(),correction.size(),numeric.data(),numeric.size())==GFN16_B_DIGIT,"COLD_LAST_INVALID");
    r14_host_need(std::all_of(numeric.begin(),numeric.end(),[](uint8_t b){return b==0x5a;}),"COLD_ATOMIC");++checks;
    return checks;
}

static inline int r14_host_cpu_benchmark(unsigned repetitions=3) {
#if !defined(__linux__)
    throw std::runtime_error("R14_HOST_CPU_ADMITTED_LINUX_ONLY");
#else
    r14_host_need(repetitions>=1 && repetitions<=5,"FINITE_REPETITIONS");
    const unsigned selfchecks=r14_host_selfcheck();
    const uint32_t n=65536,base=604832956,generation=7;const size_t T=n/16;
    const uint64_t cold_owner=(UINT64_C(65535)<<8)|generation;
    const uint64_t final_owner=(UINT64_C(31)<<24)|(UINT64_C(65535)<<8)|generation;
    std::vector<uint8_t> profile(32),digits(4*n),correction(128),raw(4*(n+32));
    std::vector<uint8_t> numeric(4*(3*n+96)),canonical(4*n),first_numeric,first_canonical;
    for(uint32_t j=0;j<n;++j)gfn16_b_store32(digits.data()+4*j,uint32_t((uint64_t(j)*104729+17)%base));
    for(unsigned lane=0;lane<16;++lane){
        gfn16_b_store32(correction.data()+4*lane,uint32_t((int(lane)-8)*997));
        gfn16_b_store32(correction.data()+4*(16+lane),uint32_t((int(lane)-8)*991));
    }
    for(unsigned row=0;row<T;++row)for(unsigned lane=0;lane<16;++lane)
        gfn16_b_store32(raw.data()+4*(row*16+lane),gfn16_b_load32(digits.data()+4*(lane*T+row)));
    memcpy(raw.data()+4*n,correction.data(),128);
    std::array<std::vector<double>,6> samples;gfn16_b_final_info info;
    using clock=std::chrono::steady_clock;const auto deadline=clock::now()+std::chrono::seconds(60);
    auto timed=[&](unsigned phase,auto work){
        const auto wall=clock::now();const auto cpu=std::clock();const int rc=work();
        const double cpu_seconds=double(std::clock()-cpu)/CLOCKS_PER_SEC;
        const double wall_seconds=std::chrono::duration<double>(clock::now()-wall).count();
        r14_host_need(rc==0,"TIMED_OPERATION");samples[phase].push_back(wall_seconds);samples[phase+3].push_back(cpu_seconds);
    };
    for(unsigned repeat=0;repeat<repetitions;++repeat){
        r14_host_need(clock::now()<deadline,"INNER_DEADLINE");
        timed(0,[&](){return gfn16_b_profile_make(n,base,generation,profile.data(),profile.size());});
        timed(1,[&](){return gfn16_b_cold_write(n,profile.data(),32,1,1,cold_owner,cold_owner,
            digits.data(),digits.size(),correction.data(),correction.size(),numeric.data(),numeric.size());});
        timed(2,[&](){return gfn16_b_final_decode(n,profile.data(),32,1,1,final_owner,final_owner,
            raw.data(),raw.size(),canonical.data(),canonical.size(),&info);});
        if(!repeat){first_numeric=numeric;first_canonical=canonical;}
        else r14_host_need(numeric==first_numeric && canonical==first_canonical,"REPEATED_BYTE_IDENTITY");
    }
    r14_host_need(clock::now()<deadline,"INNER_DEADLINE");
    char host[256]={};r14_host_need(gethostname(host,sizeof(host)-1)==0,"HOSTNAME");
    const std::string hostname=std::string(host).substr(0,std::string(host).find('.'));
    r14_host_need(hostname=="aethia" || hostname=="gfn16-pilot-c4d","ADMITTED_HOSTNAME");
    std::cout<<std::setprecision(17)<<"R14_HOST_CPU_PASS {\"status\":\"PASS_C_host_measurement_only\",\"host\":\""<<hostname
        <<"\",\"n\":65536,\"p\":16,\"base\":604832956,\"generation\":7,\"repetitions\":"<<repetitions
        <<",\"selfchecks\":"<<selfchecks<<",\"header_sha256\":\"7679e85713662635476124b0bad2e91954a08d8a27dd3f25db127b23da9d0720\",\"profile_wire_hex\":\""<<r14_host_hex(profile)
        <<"\",\"final_wire_hex\":\""<<r14_host_hex(canonical)<<"\",\"special\":"<<(info.special ? "true":"false")
        <<",\"carry\":["<<info.carry[0]<<','<<info.carry[1]<<','<<info.carry[2]<<']';
    static const char* names[6]={"profile_wall","cold_wall","final_wall","profile_cpu","cold_cpu","final_cpu"};
    for(unsigned phase=0;phase<6;++phase){std::cout<<",\""<<names[phase]<<"\":[";
        for(unsigned j=0;j<repetitions;++j){if(j)std::cout<<',';std::cout<<samples[phase][j];}std::cout<<']';}
    std::cout<<",\"backend_seconds\":null,\"transport_seconds\":null,\"overlap_seconds\":null,\"prp_wall_seconds\":null,\"native_core_equivalence\":false,\"promotion_allowed\":false}\n";
    return 0;
#endif
}
#endif
