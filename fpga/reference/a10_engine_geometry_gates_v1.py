"""Extend the exact AW5 harness, not RTL, to nontrivial/full bank geometries.

N<=256 uses direct polynomial evaluation and schoolbook convolution. Full-size
native C++ uses an independent ordinary twist + cyclic DIF/DIT oracle, not the
merged CT/GS/root delivery algorithm. No HDL/native/full-N numeric run here.
"""
from pathlib import Path
import hashlib
from fpga.reference import a10_banked_engine_generate_v1 as gen

ROOT=gen.ROOT/'fpga'
PARENT='rtl/tb/a10_banked_engine_aw5_v1.cpp'
PARENT_SHA='13fe22f4a8a40836fe09930827068a9b8286f80da491efce3a3c7c51903ccab1'
BENCH='rtl/tb/a10_banked_engine_geometry_v1.cpp'

ORACLE=r'''
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
'''

def need(ok,message):
    if not ok:raise ValueError(message)

def source_guard():
    gen.source_guard()
    need(hashlib.sha256((ROOT/PARENT).read_bytes()).hexdigest()==PARENT_SHA,'A10_AW5_BENCH_DRIFT')

def bench_source():
    source_guard();s=(ROOT/PARENT).read_text()
    s=gen.once(s,'// Independent small arithmetic/host/profile oracle, not a numeric NTT model.',
        '// Additive AW5/8/16 native geometry harness, no frozen RTL change; independent ordinary oracle.')
    s=gen.once(s,'constexpr uint32_t P=A10_P,N=32,AW=5;',
        '#ifndef A10_AW\n#define A10_AW 8\n#endif\nconstexpr uint32_t P=A10_P,AW=A10_AW,N=1u<<AW;\nstatic_assert(AW==5 || AW==8 || AW==16,"separately admitted geometry only");')
    s=gen.once(s,'int main(int argc,char** argv){',ORACLE+'\nint main(int argc,char** argv){')
    s=gen.once(s,'unsigned elapsed=0;while(!d.done && elapsed<8192){tick();++elapsed;}',
        'unsigned elapsed=0;while(!d.done && elapsed<AW*((N+127)/128+9)+64){tick();++elapsed;}')
    old=gen.region(s,'            require(d.cycles==(op?8:AW*10)', '            auto cycles=d.cycles;')
    new=r'''            const uint64_t groups=(N+127)/128,point_groups=(N+63)/64;
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
'''
    s=gen.once(s,old,new)
    old=gen.region(s,'            for(unsigned k=0;k<N;++k)for(unsigned j=0;j<N;++j)', '            total+=run(0,false);')
    s=gen.once(s,old,'            spectrum=spectrum_oracle(a);\n')
    old=gen.region(s,'            for(unsigned i=0;i<N;++i)for(unsigned j=0;j<N;++j){', '            total+=run(0,true);')
    s=gen.once(s,old,'            convolution=convolution_oracle(a,spectrum);\n')
    s=gen.once(s,'"A10_ENGINE_PASS aw=5 field="','"A10_ENGINE_PASS aw="<<AW<<" field="')
    return s

def ledger(aw=8):
    need(type(aw) is int and aw in (5,8,16),'A10_NATIVE_GEOMETRY')
    n=1<<aw;groups=(n+127)//128
    roots=groups*sum(1<<max(0,min(aw,7)-s-1) for s in range(aw))
    rom=groups*sum((s<7 and groups>1) or (s>=7 and s<aw-1) for s in range(aw))
    transform=aw*(groups+9);point=(n+63)//64+7
    return dict(aw=aw,n=n,groups=groups,transform_cycles=transform,point_cycles=point,
        roots_per_transform=roots,ROM_reads_per_transform=rom,normalization_products=n//2,
        frames=5,operations=15,residues=15*n,engine_work_cycles=5*(2*transform+point),
        whole_controller_ntt_cycles=2*transform+point+6,
        oracle='direct polynomial + schoolbook' if aw<=8 else 'ordinary twist + conventional cyclic DIF/DIT',
        status='source_prediction_not_native_measurement')
