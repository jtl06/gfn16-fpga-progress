// Original test adapter. Upstream source and MIT notices remain byte-exact.
// Calls the REAL pinned genefer22 PL/GL methods with a small GMP transform
// substitute. This is not its CPU/OpenCL engine, BOINC server or FPGA runtime.
#include <bits/stdc++.h>
#include <gmpxx.h>
#include "transform.h"
#include "arith.h"
#include "timer.h"
// Fixture-only access; no upstream source bytes are rewritten.
#define private public
#define protected public
#include "genefer.h"
#undef protected
#undef private

class SmallGmpTransform final : public transform {
public:
    mutable std::vector<mpz_class> registers;
    mpz_class modulus, multiplicand;
    uint32_t base;
    SmallGmpTransform(uint32_t b) : transform(32,5,b,EKind::NTT3cpu),
        registers(32), base(b) {
        mpz_ui_pow_ui(modulus.get_mpz_t(),b,32);modulus+=1;
    }
    void set(uint32_t value) override { registers[0]=value; }
    void squareDup(bool dup) override {
        registers[0]=(registers[0]*registers[0]*(dup?2:1))%modulus;
    }
    void squareMul(int32_t value) override {
        registers[0]=(registers[0]*registers[0]*value)%modulus;
        if(registers[0]<0)registers[0]+=modulus;
    }
    void initMultiplicand(size_t src) override { multiplicand=registers.at(src); }
    void mul() override { registers[0]=(registers[0]*multiplicand)%modulus; }
    void copy(size_t dst,size_t src) const override { registers.at(dst)=registers.at(src); }
    size_t getMemSize() const override {return 0;}
    size_t getCacheSize() const override {return 0;}
    bool readContext(file &,size_t) override {return false;}
    void saveContext(file &,size_t) const override {throw std::runtime_error("NO_CONTEXT_STUB");}
    void getZi(int32_t *data) const override {
        std::fill(data,data+32,0);
        if(registers[0]==modulus-1){data[0]=-1;return;}
        mpz_class remaining=registers[0];
        for(size_t i=0;i<32;i++)
            data[i]=static_cast<int32_t>(mpz_fdiv_q_ui(remaining.get_mpz_t(),remaining.get_mpz_t(),base));
    }
    void setZi(const int32_t *data) override {
        mpz_class value=0;
        for(size_t i=32;i!=0;i--){value*=base;value+=data[i-1];}
        value%=modulus;if(value<0)value+=modulus;registers[0]=value;
    }
};

int main(int argc,char **argv) {
    if(argc!=2)return 2;
    for(uint32_t base:{10U,599U,600U}) {
        SmallGmpTransform backend(base);gint image(32,base);genefer oracle;
        oracle._transform=&backend;oracle._gi=&image;
        oracle.setFilename(std::string(argv[1])+"/base"+std::to_string(base));
        mpz_t exponent;mpz_init(exponent);mpz_ui_pow_ui(exponent,base,32);
        const int depth=3,width=genefer::B_PietrzakLi(mpz_sizeinbase(exponent,2),depth);
        // Independent GMP pow supplies all input checkpoints; no prototype
        // proof-generator code is used to construct the oracle transcript.
        for(int i=0;i<(1<<depth);i++) {
            mpz_class prefix(exponent),two=2;prefix>>=(i*width);
            mpz_powm(backend.registers[3+i].get_mpz_t(),two.get_mpz_t(),
                     prefix.get_mpz_t(),backend.modulus.get_mpz_t());
        }
        double seconds=0;uint64_t key=0;
        if(oracle.PL(depth,true,seconds,key)!=genefer::EReturn::Success)return 3;
        // Exercise exact upstream GL on independent backend checkpoint product.
        const int gl_width=7;
        mpz_class product=1,result=1;
        for(int i=static_cast<int>(mpz_sizeinbase(exponent,2))-1;i>=0;i--) {
            result=(result*result*(mpz_tstbit(exponent,i)?2:1))%backend.modulus;
            if(i%gl_width==0 && i/gl_width!=0)product=(product*result)%backend.modulus;
        }
        backend.registers[0]=result;backend.registers[1]=product;
        if(oracle.GL(exponent,gl_width,seconds)!=genefer::EReturn::Success)return 4;
        // A separate finite numerical corruption, not arbitrary fault immunity.
        backend.registers[0]=(result+1)%backend.modulus;backend.registers[1]=product;
        if(oracle.GL(exponent,gl_width,seconds)!=genefer::EReturn::Failed)return 5;
        std::cout<<"R15_PL_ORACLE base="<<base<<" pkey="<<key<<" gl=1 bad_gl=1\n";
        mpz_clear(exponent);
    }
    return 0;
}
