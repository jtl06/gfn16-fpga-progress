// Native-only full-size arithmetic reference. No Boost/GMP/runtime dependency.
// Frozen iterative NTT is included in independent per-prime namespaces;
// canonical reduction is direct integer mod b^N+1, NOT the DUT 3-pass RAM FSM.
#pragma once
#include <algorithm>
#include <array>
#include <cstdint>
#include <stdexcept>
#include <utility>
#include <vector>

namespace s4_full_reference {
using I=__int128_t;using U=__uint128_t;
inline void need(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
namespace f0 {constexpr uint32_t PRIME=104857601,GENERATOR=3;
#include "stream27_shared_reference_ntt_v1.h"
}
namespace f1 {constexpr uint32_t PRIME=69206017,GENERATOR=5;
#include "stream27_shared_reference_ntt_v1.h"
}
namespace f2 {constexpr uint32_t PRIME=67239937,GENERATOR=10;
#include "stream27_shared_reference_ntt_v1.h"
}
constexpr I MODULUS=I(f0::PRIME)*f1::PRIME*f2::PRIME,HALF=MODULUS/2;
inline std::pair<I,uint32_t> euclidean(I x,uint32_t base){I q=x/base,r=x%base;if(r<0){r+=base;--q;}return {q,uint32_t(r)};}
inline std::vector<I> coefficients(const std::vector<int32_t>& input,bool twice){
    std::vector<int64_t> x(input.begin(),input.end());
    auto a=f0::ref_negacyclic_square(x),b=f1::ref_negacyclic_square(x),c=f2::ref_negacyclic_square(x);
    const uint32_t inverse01=f1::ref_power(f0::PRIME%f1::PRIME,f1::PRIME-2);
    const uint64_t p01=uint64_t(f0::PRIME)*f1::PRIME;
    const uint32_t inverse012=f2::ref_power(p01%f2::PRIME,f2::PRIME-2);
    std::vector<I> out(input.size());
    for(unsigned j=0;j<input.size();++j){
        if(twice){a[j]=uint64_t(a[j])*2%f0::PRIME;b[j]=uint64_t(b[j])*2%f1::PRIME;c[j]=uint64_t(c[j])*2%f2::PRIME;}
        uint32_t delta01=(uint64_t(b[j])+f1::PRIME-a[j]%f1::PRIME)%f1::PRIME;
        uint64_t lower=uint64_t(a[j])+uint64_t(f0::PRIME)*(uint64_t(delta01)*inverse01%f1::PRIME);
        uint32_t delta012=(uint64_t(c[j])+f2::PRIME-lower%f2::PRIME)%f2::PRIME;
        I value=I(lower)+I(p01)*(uint64_t(delta012)*inverse012%f2::PRIME);
        out[j]=value>HALF?value-MODULUS:value;
    }return out;
}
inline std::vector<int32_t> canonical(const std::vector<I>& values,uint32_t base){
    const unsigned n=values.size();need(n>=32 && !(n&(n-1)) && base>=2 && base<=1000000000u,"S4_FULL_REFERENCE_DOMAIN");
    const I B=base-1,A=I(2)*n*B*B,Q=I(2)*n*B;
    need(A<HALF && Q<(I(1)<<47),"S4_FULL_REFERENCE_CRT_Q_BOUND");
    std::vector<int32_t> digits(n);I terminal=0;
    for(unsigned j=0;j<n;++j){need(values[j]>=-A && values[j]<=A,"S4_FULL_REFERENCE_COEFFICIENT_BOUND");auto z=euclidean(values[j]+terminal,base);terminal=z.first;digits[j]=z.second;need(terminal>=-Q && terminal<=Q,"S4_FULL_REFERENCE_SERIAL_Q_BOUND");}
    // X=D+q*b^N, hence residue is Y=D-q. Q=2N(b-1)<b^N for
    // N>=32,b>=2, so Y lies strictly between -b^N and 2*b^N.
    // One base-N subtraction and ONE explicit +/-M wrap suffice; there is
    // no recurrence controller, block correction split or three-pass fold.
    I carry=-terminal;
    for(auto& d:digits){auto z=euclidean(I(d)+carry,base);carry=z.first;d=z.second;}
    need(carry>=-1 && carry<=1,"S4_FULL_REFERENCE_SINGLE_MODULUS_WRAP");
    if(carry==-1){
        bool all_max=true;for(auto d:digits)all_max&=uint32_t(d)==base-1;
        if(all_max){std::fill(digits.begin(),digits.end(),0);digits[0]=-1;return digits;}
        uint32_t add=1;for(auto& d:digits){uint32_t v=uint32_t(d)+add;d=v==base?0:v;add=v==base;}
        need(!add,"S4_FULL_REFERENCE_NEGATIVE_ADJUST");
    }else if(carry==1){
        bool zero=true;for(auto d:digits)zero&=!d;
        if(zero){digits[0]=-1;return digits;}
        unsigned borrow=1;for(auto& d:digits){if(borrow){if(!d)d=base-1;else{--d;borrow=0;}}}
        need(!borrow,"S4_FULL_REFERENCE_POSITIVE_ADJUST");
    }
    return digits;
}
inline std::vector<int32_t> square(const std::vector<int32_t>& x,uint32_t base,bool twice){
    for(auto d:x)need(d>=-1 && int64_t(d)<base,"S4_FULL_REFERENCE_SIGNED_INPUT");
    return canonical(coefficients(x,twice),base);
}

// Small-only independent complete-integer limb oracle. It is NEVER used for
// the full-N array. Horner builds signed magnitudes, then ordinary binary
// long division reduces modulo b^N+1 and small-base divisions decode digits.
struct SmallMagnitude{
    std::vector<uint32_t> w;
    explicit SmallMagnitude(U v=0){while(v){w.push_back(uint32_t(v));v>>=32;}}
    void trim(){while(!w.empty()&&!w.back())w.pop_back();}
    int compare(const SmallMagnitude& b)const{if(w.size()!=b.w.size())return w.size()<b.w.size()?-1:1;for(size_t i=w.size();i;--i)if(w[i-1]!=b.w[i-1])return w[i-1]<b.w[i-1]?-1:1;return 0;}
    void add(const SmallMagnitude& b){size_t n=std::max(w.size(),b.w.size());w.resize(n,0);uint64_t c=0;for(size_t i=0;i<n;++i){uint64_t v=uint64_t(w[i])+c+(i<b.w.size()?b.w[i]:0);w[i]=uint32_t(v);c=v>>32;}if(c)w.push_back(c);}
    void subtract(const SmallMagnitude& b){need(compare(b)>=0,"S4_FULL_SMALL_SUBTRACT");uint64_t borrow=0;for(size_t i=0;i<w.size();++i){uint64_t v=borrow+(i<b.w.size()?b.w[i]:0),old=w[i];w[i]=uint32_t(old-v);borrow=old<v;}need(!borrow,"S4_FULL_SMALL_BORROW");trim();}
    void multiply(uint32_t b){uint64_t c=0;for(auto& d:w){uint64_t v=uint64_t(d)*b+c;d=uint32_t(v);c=v>>32;}if(c)w.push_back(c);trim();}
    uint32_t divide(uint32_t b){uint64_t r=0;for(size_t i=w.size();i;--i){uint64_t v=(r<<32)|w[i-1];w[i-1]=uint32_t(v/b);r=v%b;}trim();return r;}
    unsigned bits()const{if(w.empty())return 0;unsigned b=0;for(uint32_t v=w.back();v;v>>=1)++b;return unsigned(32*(w.size()-1))+b;}
    SmallMagnitude shifted(unsigned bits)const{SmallMagnitude r;r.w.resize(w.size()+bits/32+1,0);uint64_t carry=0;for(size_t i=0;i<w.size();++i){uint64_t v=(uint64_t(w[i])<<(bits%32))|carry;r.w[i+bits/32]=uint32_t(v);carry=v>>32;}r.w[w.size()+bits/32]=uint32_t(carry);r.trim();return r;}
    void right(){uint32_t c=0;for(size_t i=w.size();i;--i){uint32_t old=w[i-1];w[i-1]=(old>>1)|(c<<31);c=old&1;}trim();}
    void modulo(const SmallMagnitude& m){need(!m.w.empty(),"S4_FULL_SMALL_MODULUS");if(compare(m)<0)return;unsigned shift=bits()-m.bits();auto divisor=m.shifted(shift);for(unsigned i=0;i<=shift;++i){if(compare(divisor)>=0)subtract(divisor);divisor.right();}}
};
inline std::vector<int32_t> small_whole_integer(const std::vector<I>& c,uint32_t base){
    need(c.size()<=256 && c.size()>=32,"S4_FULL_SMALL_ORACLE_ONLY");SmallMagnitude positive,negative,power(1);
    for(size_t j=c.size();j;--j){positive.multiply(base);negative.multiply(base);I v=c[j-1];(v<0?negative:positive).add(SmallMagnitude(v<0?U(-v):U(v)));power.multiply(base);}
    auto modulus=power;modulus.add(SmallMagnitude(1));bool minus=positive.compare(negative)<0;auto r=minus?negative:positive;r.subtract(minus?positive:negative);r.modulo(modulus);
    if(minus&&!r.w.empty()){auto a=modulus;a.subtract(r);r=a;}
    std::vector<int32_t> out(c.size(),0);if(r.compare(power)==0){out[0]=-1;return out;}
    for(auto& d:out)d=r.divide(base);need(r.w.empty(),"S4_FULL_SMALL_CANONICAL_DECODE");return out;
}
inline void self_check(){
    f0::ref_self_check();f1::ref_self_check();f2::ref_self_check();
    for(unsigned n:{32u,256u})for(uint32_t base:{2u,1000000000u})for(unsigned kind=0;kind<3;++kind){
        std::vector<int32_t> x(n);uint32_t state=0x1928eaf1u+kind;
        for(unsigned j=0;j<n;++j){state=1664525u*state+1013904223u;x[j]=state%base;}
        x[3]=-1;x[n-1]=-1;bool twice=kind&1;
        std::vector<I> direct(n,0);for(unsigned i=0;i<n;++i)for(unsigned j=0;j<n;++j)direct[(i+j)%n]+=I(x[i])*x[j]*(i+j<n?1:-1)*(twice?2:1);
        auto actual=coefficients(x,twice);need(actual==direct,"S4_FULL_REFERENCE_THREEFIELD_SCHOOLBOOK");
        need(canonical(actual,base)==small_whole_integer(direct,base),"S4_FULL_REFERENCE_SMALL_WHOLE_INTEGER");
        std::vector<I> special(n,0);special[0]=-1;need(canonical(special,base)==small_whole_integer(special,base),"S4_FULL_REFERENCE_NEGATIVE_SPECIAL");
        special.assign(n,0);special[n-1]=base;need(canonical(special,base)==small_whole_integer(special,base),"S4_FULL_REFERENCE_POSITIVE_SPECIAL");
    }
}
} // namespace s4_full_reference
