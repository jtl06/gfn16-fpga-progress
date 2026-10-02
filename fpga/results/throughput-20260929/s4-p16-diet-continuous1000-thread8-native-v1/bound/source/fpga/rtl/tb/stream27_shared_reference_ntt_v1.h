// Independent radix-2 natural-order reference. Only compiled/executed in the
// finite native gate, never during source preparation on the Mac.
static uint32_t ref_power(uint32_t x,uint32_t e){
    uint32_t y=1;
    while(e){if(e&1)y=uint64_t(y)*x%PRIME;x=uint64_t(x)*x%PRIME;e>>=1;}
    return y;
}
static void ref_cyclic(std::vector<uint32_t>& a,bool inverse){
    const unsigned n=a.size();
    for(unsigned i=1,j=0;i<n;++i){
        unsigned bit=n>>1;
        while(j&bit){j^=bit;bit>>=1;}j^=bit;
        if(i<j)std::swap(a[i],a[j]);
    }
    for(unsigned length=2;length<=n;length<<=1){
        uint32_t root=ref_power(GENERATOR,(PRIME-1)/length);
        if(inverse)root=ref_power(root,PRIME-2);
        for(unsigned begin=0;begin<n;begin+=length){
            uint32_t w=1;
            for(unsigned j=0;j<length/2;++j){
                uint32_t u=a[begin+j],v=uint64_t(a[begin+j+length/2])*w%PRIME;
                uint32_t sum=u+v;
                a[begin+j]=sum>=PRIME?sum-PRIME:sum;
                a[begin+j+length/2]=u>=v?u-v:u+PRIME-v;
                w=uint64_t(w)*root%PRIME;
            }
        }
    }
    if(inverse){uint32_t scale=ref_power(n,PRIME-2);for(auto& x:a)x=uint64_t(x)*scale%PRIME;}
}
static std::vector<uint32_t> ref_negacyclic_square(const std::vector<int64_t>& input){
    unsigned n=input.size();
    uint32_t psi=ref_power(GENERATOR,(PRIME-1)/(2*n)),weight=1;
    std::vector<uint32_t> a(n);
    for(unsigned i=0;i<n;++i){
        int64_t x=input[i]%PRIME;if(x<0)x+=PRIME;
        a[i]=uint64_t(x)*weight%PRIME;weight=uint64_t(weight)*psi%PRIME;
    }
    ref_cyclic(a,false);for(auto& x:a)x=uint64_t(x)*x%PRIME;ref_cyclic(a,true);
    uint32_t inverse_psi=ref_power(psi,PRIME-2);weight=1;
    for(auto& x:a){x=uint64_t(x)*weight%PRIME;weight=uint64_t(weight)*inverse_psi%PRIME;}
    return a;
}
static void ref_self_check(){
    std::vector<int64_t> x(256);std::vector<uint32_t> expected(256);
    for(unsigned i=0;i<x.size();++i)x[i]=int64_t(i*i+7*i+11)-40000;
    for(unsigned i=0;i<x.size();++i)for(unsigned j=0;j<x.size();++j){
        int64_t a=x[i]%PRIME,b=x[j]%PRIME;if(a<0)a+=PRIME;if(b<0)b+=PRIME;
        uint32_t value=uint64_t(a)*b%PRIME,index=(i+j)%x.size();
        if(i+j>=x.size() && value)value=PRIME-value;
        uint32_t sum=expected[index]+value;expected[index]=sum>=PRIME?sum-PRIME:sum;
    }
    need(ref_negacyclic_square(x)==expected,"S4_REFERENCE_NTT_SCHOOLBOOK_SELF_CHECK");
}
