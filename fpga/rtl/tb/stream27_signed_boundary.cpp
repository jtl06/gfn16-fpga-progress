#include "Vstream27_signed_boundary_probe.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

#ifndef SBRED_AW
#error SBRED_AW must be fixed by approved compile command
#endif
static_assert(SBRED_AW==5 || SBRED_AW==16,"explicit signed boundary profile");
static void need(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
struct Sample{unsigned valid,error;std::array<uint32_t,3> residue,tag;};
static Sample sample(const Vstream27_signed_boundary_probe& d){
    return {unsigned(d.out_valid),unsigned(d.out_error),{d.residue[0],d.residue[1],d.residue[2]},
        {uint32_t(d.payload_out&65535),uint32_t((d.payload_out>>16)&65535),uint32_t((d.payload_out>>32)&65535)}};
}
static bool equal(const Sample& a,const Sample& b){return a.valid==b.valid && a.error==b.error && a.residue==b.residue && a.tag==b.tag;}
int main(int argc,char** argv){
    try{
        VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
        Vstream27_signed_boundary_probe d{&context};
        if(argc==2 && std::string(argv[1])=="--runtime-probe"){
            std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
            return context.threads()==1 && d.threads()==1?0:2;
        }
        need(argc==2,"usage: signed_boundary vectors | --runtime-probe");
        std::ifstream input(argv[1]);need(bool(input),"SBRED_VECTOR_OPEN");
        std::string magic;unsigned aw,blocks,pw;uint64_t count;
        need(bool(input>>magic>>aw>>blocks>>pw>>count),"SBRED_VECTOR_HEADER");
        need(magic=="SBRED1" && aw==SBRED_AW && blocks==8 && pw==16 && count>0 && count<100000,"SBRED_VECTOR_PROFILE");
        uint64_t accepted=0,responses=0,errors=0,bubbles=0,resets=0,idle=0;
        const std::array<uint32_t,3> primes={104857601,69206017,67239937};
        d.clk=1;d.rst_n=0;d.in_valid=0;d.eval();
        for(uint64_t index=0;index<count;++index){
            unsigned rst,valid,kind,tag,ev,ee,expected_tag;uint64_t base,word;
            std::array<uint64_t,3> expected_residue;
            need(bool(input>>rst>>valid>>kind>>base>>word>>tag>>ev>>ee>>expected_residue[0]>>expected_residue[1]>>expected_residue[2]>>expected_tag),"SBRED_VECTOR_TRUNCATED");
            need(rst<=1 && valid<=1 && kind<=1 && ev<=1 && ee<=1 && !(ev && ee) && base<=0xffffffffu && word<=0xffffffffu && tag<=65535 && expected_tag<=65535,"SBRED_VECTOR_PORT_RANGE");
            for(unsigned f=0;f<3;++f)need(expected_residue[f]<primes[f],"SBRED_VECTOR_EXPECTED_RANGE");
            Sample previous=sample(d);
            d.rst_n=rst;d.in_valid=valid;d.boundary_high=kind;d.base=uint32_t(base);d.correction=uint32_t(word);d.payload_in=tag;
            d.eval();if(!rst)previous={0,0,{0,0,0},{0,0,0}};
            need(equal(sample(d),previous),"SBRED_ASYNC_OR_COMBINATIONAL_LEAK index="+std::to_string(index));
            d.clk=0;d.eval();need(equal(sample(d),previous),"SBRED_FALLING_EDGE_LEAK index="+std::to_string(index));
            d.clk=1;d.eval();Sample actual=sample(d);
            need(actual.valid==7*ev && actual.error==7*ee,"SBRED_VALID_OR_LATENCY_MISMATCH index="+std::to_string(index));
            for(unsigned f=0;f<3;++f)need(actual.residue[f]==expected_residue[f] && actual.tag[f]==expected_tag,
                "SBRED_INTEGER_OR_HOLD_MISMATCH field="+std::to_string(f)+" index="+std::to_string(index));
            if(!rst)++resets;else {accepted+=valid;bubbles+=!valid;}
            responses+=ev;errors+=ee;idle+=!(ev || ee);
        }
        std::string trailing;need(!(input>>trailing),"SBRED_VECTOR_TRAILING");
        need(context.threads()==1 && d.threads()==1,"SBRED_THREAD_DRIFT");
        std::cout<<"SIGNED_BOUNDARY_PASS aw="<<aw<<" blocks="<<blocks<<" events="<<count<<" accepted="<<accepted
            <<" responses="<<responses<<" errors="<<errors<<" bubbles="<<bubbles<<" resets="<<resets<<" output_idle="<<idle
            <<" before_checks="<<2*count<<" edge_checks="<<count<<" field_checks="<<3*count<<"\n";
        d.final();return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}
}
