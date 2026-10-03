#include <algorithm>
#include <cstdint>
#include "Vgenefer_stream27_p16_c2_full_observer_v1.h"
using DUT=Vgenefer_stream27_p16_c2_full_observer_v1;
constexpr unsigned AW=16,P=16,N=65536,T=N/P,COUNT=2,INTERVAL=8459,FIRST_DIGIT=8458,CARRY_DONE=12557;
constexpr uint64_t MAX_EDGES=3*11ull*N+100000;
constexpr uint32_t BASES[2]={604832956,999999937},SEEDS[2]={0x9135ba27u,0x6a09e667u};
constexpr unsigned EPOCHS[2]={65534,42},BITS[2][2]={{0,1},{1,0}};
