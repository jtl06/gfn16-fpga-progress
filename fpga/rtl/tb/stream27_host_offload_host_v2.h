/* Private R14 host boundary, C99/C++ compatible. No HDL/transport implementation.
 * All wire buffers are exact little-endian uint32 words. Output buffers and
 * final_info are unchanged on every rejected call. Caller owns live-owner
 * synchronization; a reset must replace expected_owner before publication.
 * Full-N calls belong only in authorized Linux worker tests/benchmarks.
 */
#ifndef GFN16_HOST_OFFLOAD_HOST_V2_H
#define GFN16_HOST_OFFLOAD_HOST_V2_H
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#if !defined(__SIZEOF_INT128__)
#error "R14 host profile requires the native compiler's unsigned128 integer"
#endif

enum gfn16_b_error {
    GFN16_B_OK=0, GFN16_B_GEOMETRY=1, GFN16_B_PROFILE=2,
    GFN16_B_OWNER=3, GFN16_B_LENGTH=4, GFN16_B_DIGIT=5,
    GFN16_B_CORRECTION=6, GFN16_B_INTERNAL_RANGE=7,
    GFN16_B_ALLOCATION=8, GFN16_B_ALIAS=9
};
typedef struct gfn16_b_final_info {
    int32_t carry[3];
    uint32_t special;
} gfn16_b_final_info;

static inline uint32_t gfn16_b_load32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1]<<8) | ((uint32_t)p[2]<<16) | ((uint32_t)p[3]<<24);
}
static inline void gfn16_b_store32(uint8_t *p,uint32_t x) {
    p[0]=(uint8_t)x;p[1]=(uint8_t)(x>>8);p[2]=(uint8_t)(x>>16);p[3]=(uint8_t)(x>>24);
}
static inline int64_t gfn16_b_signed32(uint32_t x) {
    return (x&UINT32_C(0x80000000)) ? (int64_t)x-INT64_C(4294967296) : (int64_t)x;
}
static inline int gfn16_b_geometry(uint32_t n) {
    return n==32 || n==256 || n==65536;
}
static inline uint32_t gfn16_b_minimum_base(uint32_t n) {
    uint32_t k=2*n+24*16, proof=(2*k+2)/3+1, ordinary=2*n+5;
    return proof>ordinary ? proof : ordinary;
}
static inline int gfn16_b_overlap(const void *a,size_t an,const void *b,size_t bn) {
    uintptr_t av=(uintptr_t)a,bv=(uintptr_t)b;
    if(an>UINTPTR_MAX-av || bn>UINTPTR_MAX-bv)return 1;
    return an && bn && av<bv+bn && bv<av+an;
}
static inline int gfn16_b_profile_make(uint32_t n,uint32_t base,uint32_t generation,
                                      uint8_t *profile_le,size_t profile_bytes) {
    __uint128_t B,K,A,Q,R,one;
    uint32_t words[8];uint8_t temporary[32];unsigned j;
    if(!gfn16_b_geometry(n))return GFN16_B_GEOMETRY;
    if(!profile_le || profile_bytes!=32)return GFN16_B_LENGTH;
    if(base<gfn16_b_minimum_base(n) || base>UINT32_C(1000000000) || generation>=256)
        return GFN16_B_PROFILE;
    B=base-1;K=2*n+24*16;
    A=2*((n+3*16)*B*B+4*16*B*K+16*K*K);
    Q=(A+B-1)/B;
    if(A>=((__uint128_t)1<<77) || Q>=((__uint128_t)1<<47) ||
       A>((__uint128_t)104857601*69206017*67239937)/2)return GFN16_B_PROFILE;
    one=(__uint128_t)1<<96;R=one/base;
    words[0]=base;words[1]=generation;
    for(j=0;j<3;++j){words[2+j]=(uint32_t)(R>>(32*j));words[5+j]=(uint32_t)(A>>(32*j));}
    for(j=0;j<8;++j)gfn16_b_store32(temporary+4*j,words[j]);
    memcpy(profile_le,temporary,32);
    return GFN16_B_OK;
}
static inline int gfn16_b_profile_validate(uint32_t n,const uint8_t *profile_le,
                                          size_t profile_bytes,uint32_t *base,uint32_t *generation) {
    uint8_t expected[32];int rc;uint32_t b,g;
    if(!gfn16_b_geometry(n))return GFN16_B_GEOMETRY;
    if(!profile_le || profile_bytes!=32)return GFN16_B_LENGTH;
    b=gfn16_b_load32(profile_le);g=gfn16_b_load32(profile_le+4);
    rc=gfn16_b_profile_make(n,b,g,expected,sizeof(expected));
    if(rc)return rc;
    if(memcmp(profile_le,expected,32))return GFN16_B_PROFILE;
    *base=b;*generation=g;return GFN16_B_OK;
}
static inline int gfn16_b_owner_validate(uint32_t context,uint32_t expected_context,
                                        uint64_t owner,uint64_t expected_owner,uint32_t generation) {
    return context<=1 && expected_context<=1 && context==expected_context &&
        (owner>>56)==0 && (expected_owner>>56)==0 && owner==expected_owner &&
        (owner&255)==generation ? GFN16_B_OK : GFN16_B_OWNER;
}
static inline uint32_t gfn16_b_residue(int64_t value,uint32_t prime) {
    int64_t r=value%(int64_t)prime;
    return (uint32_t)(r<0 ? r+prime : r);
}

/* digits: N block-major raw signed32 wires, accepting only -1 or [0,base).
 * correction: 16 c0 followed by16 c1 signed32, natural contiguous blocks.
 * numeric output: three reverse4 row planes, three low planes, three high
 * planes. HIGH=c1 mod prime, NOT c1*base; the x^1 spectral term is unchanged.
 */
static inline int gfn16_b_cold_write(uint32_t n,const uint8_t *profile_le,size_t profile_bytes,
    uint32_t context,uint32_t expected_context,uint64_t owner,uint64_t expected_owner,
    const uint8_t *digits_le,size_t digit_bytes,const uint8_t *correction_le,size_t correction_bytes,
    uint8_t *numeric_le,size_t numeric_bytes) {
    static const uint32_t primes[3]={104857601,69206017,67239937};
    static const uint8_t reverse4[16]={0,8,4,12,2,10,6,14,1,9,5,13,3,11,7,15};
    uint32_t base,generation,T,k,j,f,row,lane;size_t at=0;int rc;int64_t v;
    rc=gfn16_b_profile_validate(n,profile_le,profile_bytes,&base,&generation);if(rc)return rc;
    rc=gfn16_b_owner_validate(context,expected_context,owner,expected_owner,generation);if(rc)return rc;
    if(!digits_le || !correction_le || !numeric_le || digit_bytes!=(size_t)n*4 ||
       correction_bytes!=128 || numeric_bytes!=(size_t)(3*n+96)*4)return GFN16_B_LENGTH;
    if(gfn16_b_overlap(numeric_le,numeric_bytes,digits_le,digit_bytes) ||
       gfn16_b_overlap(numeric_le,numeric_bytes,correction_le,correction_bytes) ||
       gfn16_b_overlap(numeric_le,numeric_bytes,profile_le,profile_bytes))return GFN16_B_ALIAS;
    /* Complete validation pass BEFORE the first output word. */
    for(j=0;j<n;++j){uint32_t d=gfn16_b_load32(digits_le+4*j);
        if(d!=UINT32_MAX && d>=base)return GFN16_B_DIGIT;}
    k=2*n+24*16;
    for(j=0;j<32;++j){v=gfn16_b_signed32(gfn16_b_load32(correction_le+4*j));
        if(v<-(int64_t)(j<16 ? base-1:k) || v>(int64_t)(j<16 ? base-1:k))return GFN16_B_CORRECTION;}
    T=n/16;
    for(f=0;f<3;++f)for(row=0;row<T;++row)for(lane=0;lane<16;++lane){
        uint32_t d=gfn16_b_load32(digits_le+4*(reverse4[lane]*T+row));
        gfn16_b_store32(numeric_le+4*at++,d==UINT32_MAX ? primes[f]-1 : d%primes[f]);
    }
    for(j=0;j<2;++j)for(f=0;f<3;++f)for(lane=0;lane<16;++lane){
        v=gfn16_b_signed32(gfn16_b_load32(correction_le+4*(16*j+lane)));
        gfn16_b_store32(numeric_le+4*at++,gfn16_b_residue(v,primes[f]));
    }
    return GFN16_B_OK;
}

/* Exact natural-carry row wire -> canonical block-major signed32 LE.
 * Scratch is private and never published until ALL three folds/special checks
 * succeed. All int64 intermediates are within [-2b,3b) under profile bounds.
 */
static inline int gfn16_b_final_decode(uint32_t n,const uint8_t *profile_le,size_t profile_bytes,
    uint32_t context,uint32_t expected_context,uint64_t owner,uint64_t expected_owner,
    const uint8_t *raw_le,size_t raw_bytes,uint8_t *canonical_le,size_t canonical_bytes,
    gfn16_b_final_info *info) {
    uint32_t base,generation,T,k,j,row,lane,phase;uint32_t *image;
    int32_t c0[16],c1[16];int64_t carry=0,value,q;int rc,special;gfn16_b_final_info result;
    rc=gfn16_b_profile_validate(n,profile_le,profile_bytes,&base,&generation);if(rc)return rc;
    rc=gfn16_b_owner_validate(context,expected_context,owner,expected_owner,generation);if(rc)return rc;
    if(!raw_le || !canonical_le || !info || raw_bytes!=(size_t)(n+32)*4 ||
       canonical_bytes!=(size_t)n*4)return GFN16_B_LENGTH;
    if(gfn16_b_overlap(canonical_le,canonical_bytes,info,sizeof(*info)) ||
       gfn16_b_overlap(canonical_le,canonical_bytes,raw_le,raw_bytes) ||
       gfn16_b_overlap(canonical_le,canonical_bytes,profile_le,profile_bytes) ||
       gfn16_b_overlap(info,sizeof(*info),raw_le,raw_bytes) ||
       gfn16_b_overlap(info,sizeof(*info),profile_le,profile_bytes))return GFN16_B_ALIAS;
    k=2*n+24*16;
    for(j=0;j<n;++j)if(gfn16_b_load32(raw_le+4*j)>=base)return GFN16_B_DIGIT;
    for(j=0;j<32;++j){value=gfn16_b_signed32(gfn16_b_load32(raw_le+4*(n+j)));
        if(value<-(int64_t)(j<16 ? base-1:k) || value>(int64_t)(j<16 ? base-1:k))return GFN16_B_CORRECTION;
        if(j<16)c0[j]=(int32_t)value;else c1[j-16]=(int32_t)value;}
    image=(uint32_t*)malloc((size_t)n*sizeof(*image));if(!image)return GFN16_B_ALLOCATION;
    T=n/16;
    for(row=0;row<T;++row)for(lane=0;lane<16;++lane)image[lane*T+row]=gfn16_b_load32(raw_le+4*(row*16+lane));
    for(phase=0;phase<3;++phase){
        for(j=0;j<n;++j){
            value=(int64_t)image[j]+carry;
            if(phase==0){row=j%T;lane=j/T;if(row==0)value+=c0[lane];else if(row==1)value+=c1[lane];}
            if(value<-(int64_t)2*base || value>=(int64_t)3*base){free(image);return GFN16_B_INTERNAL_RANGE;}
            q=value>=(int64_t)2*base ? 2 : value>=(int64_t)base ? 1 : value>=0 ? 0 : value>=-(int64_t)base ? -1 : -2;
            carry=q;image[j]=(uint32_t)(value-q*base);
            if(carry<-(phase==0 ? 2:1) || carry>(phase==0 ? 2:1)){free(image);return GFN16_B_INTERNAL_RANGE;}
        }
        result.carry[phase]=(int32_t)carry;
        if(phase<2)carry=-carry;
    }
    special=result.carry[2]!=0;
    if(special){
        uint32_t required=result.carry[2]==1 ? 0 : base-1;
        if(result.carry[2]!=1 && result.carry[2]!=-1){free(image);return GFN16_B_INTERNAL_RANGE;}
        for(j=0;j<n;++j)if(image[j]!=required){free(image);return GFN16_B_INTERNAL_RANGE;}
        image[0]=UINT32_MAX;for(j=1;j<n;++j)image[j]=0;
    }
    result.special=(uint32_t)special;
    for(j=0;j<n;++j)gfn16_b_store32(canonical_le+4*j,image[j]);
    *info=result;free(image);return GFN16_B_OK;
}
#endif
