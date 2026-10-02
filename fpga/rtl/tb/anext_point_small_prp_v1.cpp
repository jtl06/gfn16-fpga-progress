#include "Vgenefer_anext_point_core_v1.h"
#include "verilated.h"
#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
static void need(bool x,const std::string& s){if(!x)throw std::runtime_error(s);}
int main(int argc,char** argv){try{
    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
    Vgenefer_anext_point_core_v1 d{&context};
    if(argc==2 && std::string(argv[1])=="--runtime-probe"){
        std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
        return context.threads()==1 && d.threads()==1?0:2;
    }
    const std::string mode=argc==3?argv[2]:"normal";
    need((argc==2 || argc==3) && (mode=="normal" || mode=="--negative-comparator" || mode=="--negative-schedule"),"E2E_ARGUMENTS");
    std::ifstream input(argv[1]);need(bool(input),"E2E_MISSING_CORPUS");
    std::string magic;unsigned aw,count;need(bool(input>>magic>>aw>>count) && magic=="GFNPRP1" && aw==5 && count==8,"E2E_HEADER");
    d.cmd_valid=0;d.rsp_ready=0;d.clk=0;d.rst_n=0;d.cmd_opcode=0;d.cmd_address=0;d.cmd_word=0;d.cmd_base=300;d.cmd_double=0;
    auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();};
    auto command=[&](unsigned opcode,unsigned address,uint32_t word,unsigned base,bool bit){
        need(d.cmd_ready && !d.rsp_valid,"E2E_COMMAND_READY");
        d.cmd_opcode=opcode;d.cmd_address=address;d.cmd_word=word;d.cmd_base=base;d.cmd_double=bit;d.cmd_valid=1;tick();d.cmd_valid=0;
        unsigned latency=0;while(!d.rsp_valid && latency<65536){need(!d.cmd_ready,"E2E_COMMAND_BACKPRESSURE");tick();++latency;}
        need(d.rsp_valid && !d.rsp_error && !d.fault_sticky && d.rsp_opcode==opcode,"E2E_COMMAND_RESPONSE");
        const int32_t result=int32_t(d.rsp_word);const auto generation=d.rsp_generation;
        if(opcode==5)need(latency==d.square_cycles+2,"E2E_COMMAND_CYCLE_ALIGNMENT");
        tick();need(d.rsp_valid && d.rsp_generation==generation && int32_t(d.rsp_word)==result && !d.rsp_error,"E2E_RESPONSE_HOLD");
        d.rsp_ready=1;tick();d.rsp_ready=0;return result;
    };
    uint64_t operations=0,doubles=0,cycles=0,prefills=0,roots=0;
    for(unsigned index=0;index<count;++index){
        std::string tag,label,bits;unsigned id,base,steps,ones;
        need(bool(input>>tag>>id>>base>>label>>steps>>ones>>bits) && tag=="CASE" && id==index && base>=300 && base<=1000000000 && (label=="prime" || label=="composite") && bits.size()==steps && steps>0 && steps<=957 && bits.front()=='1' && bits.find_first_not_of("01")==std::string::npos && unsigned(std::count(bits.begin(),bits.end(),'1'))==ones,"E2E_CASE");
        std::vector<int64_t> expected(32),actual(32);for(auto& x:expected)need(bool(input>>x),"E2E_EXPECTED_EXTENT");
        d.cmd_valid=0;d.rsp_ready=0;d.rst_n=0;tick();d.rst_n=1;tick();
        need(!d.rsp_valid && !d.busy && !d.image_valid && !d.prefill_valid,"E2E_RESET");
        command(0,0,0,base,false);for(unsigned i=0;i<32;++i)command(1,i,i==0,base,false);
        uint64_t case_cycles=0,case_prefill=0,case_roots=0;unsigned actual_ones=0;
        for(unsigned k=0;k<steps;++k){
            const bool bit=(bits[k]=='1') ^ (mode=="--negative-schedule" && index==0 && k+1==steps);actual_ones+=bit;
            // No intermediate host reads/reloads: each square uses retained RAM.
            command(5,0,0,base,bit);
            need(d.image_valid && d.prefill_valid && d.profile_loads==(k==0) && d.profile_hits==(k!=0),"E2E_RETAINED_IMAGE");
            need(d.square_cycles==(k==0?207u:184u) && d.prefill_cycles==(k==0?12u:0u) && d.root_cycles==(k==0?9u:0u) && d.ntt_cycles==115 && d.post_cycles==64 && d.seed_setup_cycles==0,"E2E_PHASE_ACCOUNTING");
            case_cycles+=d.square_cycles;case_prefill+=d.prefill_cycles;case_roots+=d.root_cycles;
        }
        for(unsigned i=0;i<32;++i){actual[i]=command(2,i,0,base,false);need(actual[i]>=-1 && actual[i]<int64_t(base),"E2E_FINAL_DIGIT_RANGE");}
        const bool minus_one=actual[0]==-1;
        for(unsigned i=0;i<32;++i)need(minus_one?actual[i]==(i==0?-1:0):actual[i]>=0,"E2E_CANONICAL_ENCODING");
        const bool prp=actual[0]==1 && std::all_of(actual.begin()+1,actual.end(),[](int64_t x){return x==0;});
        std::cout<<"E2E_RESULT case="<<index<<" base="<<base<<" class="<<label<<" steps="<<steps<<" doubles="<<actual_ones<<" cycles="<<case_cycles<<" cold=1 warm="<<steps-1<<" conversion="<<case_prefill<<" roots="<<case_roots<<" prp="<<prp<<" digits=";
        for(unsigned i=0;i<32;++i)std::cout<<(i?",":"")<<actual[i];std::cout<<"\n";
        if(mode=="--negative-comparator" && index==0)expected[0]=(expected[0]+1)%base;
        for(unsigned i=0;i<32;++i)need(actual[i]==expected[i],"E2E_RESIDUE_MISMATCH case="+std::to_string(index)+" digit="+std::to_string(i));
        need(label!="prime" || prp,"E2E_PROVEN_PRIME_NOT_PRP");
        operations+=steps;doubles+=actual_ones;cycles+=case_cycles;prefills+=case_prefill;roots+=case_roots;
    }
    std::string trailing;need(!(input>>trailing) && input.eof(),"E2E_TRAILING_INPUT");need(mode=="normal","E2E_NEGATIVE_NOT_DETECTED");
    need(context.threads()==1 && d.threads()==1,"E2E_THREADS");
    std::cout<<"E2E_PASS aw=5 cases="<<count<<" operations="<<operations<<" doubles="<<doubles<<" readbacks="<<count<<" cycles="<<cycles<<" cold="<<count<<" warm="<<operations-count<<" conversion="<<prefills<<" roots="<<roots<<"\n";
    d.final();return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
