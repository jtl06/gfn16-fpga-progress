#include "Vgenefer_root_stream32_r2.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <iostream>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

static constexpr uint64_t RADIX=uint64_t(1)<<32;
static uint32_t power(uint32_t a,uint32_t e,uint32_t p) {
    uint64_t r=1,x=a;
    while(e) {if(e&1)r=r*x%p;x=x*x%p;e>>=1;}
    return uint32_t(r);
}
static void require(bool condition,const std::string& text) {
    if(!condition)throw std::runtime_error(text);
}
int main(int argc,char** argv) {
    try {
        Verilated::commandArgs(argc,argv);
        require(argc==4,"prime generator log2N required");
        const uint32_t p=std::stoul(argv[1]),g=std::stoul(argv[2]);
        const unsigned aw=std::stoul(argv[3]),n=1u<<aw;
        require(p<(1u<<27) && aw>=1 && aw<=16,"atomic27 profile required");
        const uint64_t r=RADIX%p,r2=r*r%p,ri=power(uint32_t(r),p-2,p);
        const uint32_t psi=power(g,(p-1)/(2*n),p),omega=uint64_t(psi)*psi%p;
        require(power(psi,n,p)==p-1 && power(psi,2*n,p)==1,"root order mismatch");
        const std::array<uint32_t,4> step={psi,omega,power(omega,p-2,p),power(psi,p-2,p)};
        const std::array<uint32_t,4> first={uint32_t(r2),uint32_t(r),uint32_t(r),power(n,p-2,p)};
        std::array<std::vector<uint32_t>,4> oracle;
        std::vector<uint32_t> ordinary(n);ordinary[0]=1;
        for(unsigned i=1;i<n;++i)ordinary[i]=uint64_t(ordinary[i-1])*psi%p;
        for(unsigned phase=0;phase<4;++phase) {
            oracle[phase].resize(n);oracle[phase][0]=first[phase];
            for(unsigned i=1;i<n;++i)oracle[phase][i]=uint64_t(oracle[phase][i-1])*step[phase]%p;
        }
        Vgenefer_root_stream32_r2 dut;
        uint64_t checked=0,tables=0,aborts=0,reset_boundaries=0,identities=0,busy_mutations=0;
        auto tick=[&](){dut.clk=0;dut.eval();dut.clk=1;dut.eval();};
        auto idle=[&](unsigned clocks) {
            dut.start=0;
            for(unsigned i=0;i<clocks;++i) {
                dut.phase=i%4;tick();
                require(!dut.busy&&!dut.done&&!dut.root_valid&&!dut.error,"stale result after idle/reset");
            }
        };
        auto reset=[&]() {
            dut.start=0;dut.rst_n=0;tick();
            require(!dut.busy&&!dut.done&&!dut.root_valid&&!dut.error&&!dut.root_addr&&!dut.root_data,"reset flags/data mismatch");
            dut.rst_n=1;idle(8);
        };
        auto begin=[&](unsigned phase) {
            dut.phase=phase;dut.start=1;tick();dut.start=0;
            require(dut.busy&&!dut.done&&!dut.error&&!dut.root_valid,"start contract mismatch");
        };
        auto output=[&](unsigned phase,unsigned i,bool twist_check) {
            dut.phase=(phase+1+i%3)%4;dut.start=(i&1)==0;tick();++busy_mutations;
            require(dut.root_valid&&!dut.error&&dut.root_addr==i&&dut.root_data==oracle[phase][i]&&dut.root_data<p,
                    "root mismatch phase="+std::to_string(phase)+" index="+std::to_string(i));
            require(bool(dut.done)==(i==n-1)&&bool(dut.busy)==(i!=n-1),"done cycle mismatch");
            ++checked;
            if(twist_check && phase==0) {
                const std::array<int64_t,10> raw={-1,0,1,int64_t(p)-1,p,int64_t(p)+1,134217727,134217728,604832955,999999999};
                for(int64_t digit:raw) {
                    // Future RTL still needs digit_reduce27. The multiplier
                    // identity is applied only to its canonical residue.
                    const uint64_t canonical=digit==-1?p-1:uint64_t(digit)%p;
                    const uint64_t fused=canonical*dut.root_data%p*ri%p;
                    const uint64_t separate=canonical*r%p*ordinary[i]%p;
                    require(fused==separate,"canonical twist identity mismatch");++identities;
                }
            }
        };
        auto table=[&](unsigned phase,bool twist_check) {
            begin(phase);for(unsigned i=0;i<n;++i)output(phase,i,twist_check);++tables;
        };
        reset();
        // No idle edge between tables: start immediately after prior done.
        for(unsigned repeat=0;repeat<3;++repeat)for(unsigned phase=0;phase<4;++phase)table(phase,true);
        idle(3);
        std::set<unsigned> cuts;
        if(n<=16)for(unsigned i=0;i<=n;++i)cuts.insert(i);
        else {
            for(unsigned i=0;i<=10;++i)cuts.insert(i);
            for(unsigned i:{n/2-1,n/2,n-2,n-1,n})cuts.insert(i);
        }
        for(unsigned phase=0;phase<4;++phase)for(unsigned cut:cuts) {
            begin(phase);for(unsigned i=0;i<cut;++i)output(phase,i,false);
            reset();++reset_boundaries;if(cut<n)++aborts;
            table((phase+2)%4,false);
        }
        idle(9);dut.final();
        std::cout<<"{\"status\":\"passed\",\"prime\":"<<p<<",\"generator\":"<<g
                 <<",\"aw\":"<<aw<<",\"n\":"<<n<<",\"radix_bits\":32,\"checked_roots\":"<<checked
                 <<",\"completed_tables\":"<<tables<<",\"reset_boundaries\":"<<reset_boundaries
                 <<",\"aborted_tables\":"<<aborts<<",\"canonical_twist_identities\":"<<identities
                 <<",\"busy_input_mutations\":"<<busy_mutations<<",\"cycles_per_table\":"<<n<<"}\n";
        return 0;
    } catch(const std::exception& error) {std::cerr<<"FAIL "<<error.what()<<"\n";return 1;}
}
