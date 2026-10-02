// Native-only full-N vector materialization; signed-monomial closed-form oracle.
// No NTT and no large-integer library. This header is source-pinned with bench.
#include <sstream>
#include <vector>
static std::vector<int32_t> a4_monomial(int64_t coefficient,unsigned exponent,uint32_t base,unsigned n){
    std::vector<int32_t> words(n,0);
    if(coefficient==-1 && exponent==0){words[0]=-1;return words;}
    if(coefficient<0){
        const auto magnitude=uint64_t(-coefficient);
        if(!magnitude || magnitude>=base)throw std::runtime_error("A4_REP_NEGATIVE_BOUND");
        if(exponent==0){for(auto& word:words)word=int32_t(base-1);words[0]=int32_t(uint64_t(base)+1-magnitude);}
        else{
            words[0]=1;words.at(exponent)=int32_t(uint64_t(base)-magnitude);
            for(unsigned i=exponent+1;i<n;++i)words[i]=int32_t(base-1);
        }
    }else{
        while(coefficient){
            if(exponent>=n)throw std::runtime_error("A4_REP_POSITIVE_EXTENT");
            words[exponent++]=int32_t(uint64_t(coefficient)%base);coefficient=int64_t(uint64_t(coefficient)/base);
        }
    }
    return words;
}
static std::string a4_representative_vectors(){
    constexpr unsigned n=1u<<A4_CORE_AW;
    const unsigned proof=(2*(2*n+384)+2)/3+1;
    const unsigned minimum=(2*n+5)>proof ? (2*n+5) : proof;
    std::ostringstream out;out<<"A4CORE1 "<<A4_CORE_AW<<" "<<12*n+20<<"\n";
    for(unsigned which=0;which<4;++which){
        const uint32_t base=which==3 ? 1000000000u : minimum;
        int64_t coefficient=which==0 ? -1 : which==1 ? 1 : -2;
        unsigned exponent=which==1 ? n-1 : 0;
        auto values=a4_monomial(coefficient,exponent,base,n);
        // All-(b-1) is -2 modulo b**N+1; load the dense representative itself.
        if(which>=2)for(auto& value:values)value=int32_t(base-1);
        auto row=[&](unsigned op,unsigned address,int32_t word,unsigned double_bit,int32_t expected,unsigned valid,unsigned prefilled,int cold,int load){
            out<<op<<' '<<address<<' '<<uint32_t(word)<<' '<<base<<' '<<double_bit<<' '<<uint32_t(expected)<<' '
               <<valid<<' '<<prefilled<<' '<<cold<<' '<<load<<'\n';
        };
        row(0,0,0,0,0,0,0,-1,-1);
        for(unsigned i=0;i<n;++i)row(1,i,values[i],0,0,unsigned(i==n-1),0,-1,-1);
        for(unsigned step=0;step<4;++step){
            const unsigned double_bit=step==1 || step==3;
            // Recipe coefficient never exceeds 2,097,152 in these four steps.
            coefficient=coefficient*coefficient*(int64_t(1)<<double_bit);exponent*=2;
            if(exponent>=n){coefficient=-coefficient;exponent-=n;}
            values=a4_monomial(coefficient,exponent,base,n);
            row(5,0,0,double_bit,0,1,1,int(step==0 || step==3),int(step==0));
            if(step>=2)for(unsigned i=0;i<n;++i)row(2,i,0,0,values[i],1,0,-1,-1);
        }
    }
    return out.str();
}
