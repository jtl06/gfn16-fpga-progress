#include "Vgenefer_stream27_mdc_slots_chain_v2.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
static void need(bool ok,const std::string& s){if(!ok)throw std::runtime_error(s);}
using State=std::array<uint32_t,19>;
static State state(const Vgenefer_stream27_mdc_slots_chain_v2& d){return {
    d.out_slot_valid,d.out_frame_start,d.out_eligible,d.out_error,d.stage_errors,
    d.upper_out,d.lower_out,d.upper_payload_out,d.lower_payload_out,d.context_out,d.generation_out,
    d.commit_valid,d.commit_frame_start,d.commit_upper,d.commit_lower,
    d.commit_upper_payload,d.commit_lower_payload,d.commit_context,d.commit_generation};}
int main(int argc,char** argv){
    try{
        VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
        Vgenefer_stream27_mdc_slots_chain_v2 d{&context};
        if(argc==2 && std::string(argv[1])=="--runtime-probe"){
            std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
            return context.threads()==1 && d.threads()==1?0:2;
        }
        need(argc==2,"SLOTS_USAGE");std::ifstream input(argv[1]);need(bool(input),"SLOTS_OPEN");
        std::string magic;uint64_t d1,d2,T,count;input>>magic>>d1>>d2>>T>>count;
        need(magic=="SLOTS2" && d1==1 && d2==2 && T==8 && count<1000000,"SLOTS_HEADER");
        uint64_t slots=0,commits=0,errors=0,resets=0;
        d.clk=1;d.rst_n=0;d.in_slot_valid=0;d.frame_start=0;d.eval();
        for(uint64_t tick=0;tick<count;++tick){
            std::array<int64_t,31> row{};
            for(auto& x:row)need(bool(input>>x),"SLOTS_TRUNCATED");
            need(row[0]>=0 && row[0]<=1 && row[1]>=0 && row[1]<=1 && row[2]>=0 && row[2]<=1 &&
                 row[3]>=0 && row[3]<(1<<27) && row[4]>=0 && row[4]<(1<<27) &&
                 row[5]>=0 && row[5]<65536 && row[6]>=0 && row[6]<65536 &&
                 row[7]>=0 && row[7]<=1 && row[8]>=0 && row[8]<256 && row[9]>=0 && row[9]<4 &&
                 row[10]>=0 && row[10]<65536,"SLOTS_PORT_RANGE");
            State previous=state(d);
            d.rst_n=row[0];d.in_slot_valid=row[1];d.frame_start=row[2];
            d.upper_in=row[3];d.lower_in=row[4];d.upper_payload=row[5];d.lower_payload=row[6];
            d.context_in=row[7];d.generation_in=row[8];d.context_enabled=row[9];d.live_generations=row[10];
            if(!row[0]){for(unsigned j=0;j<5;++j)previous[j]=0;previous[11]=0;previous[12]=0;}
            d.eval();need(state(d)==previous,"SLOTS_ASYNC_OR_COMBINATIONAL_LEAK tick="+std::to_string(tick));
            if(row[11]>=0)need(d.fault_pending==uint64_t(row[11]),"SLOTS_PENDING_FAULT_MISMATCH tick="+std::to_string(tick));
            d.clk=0;d.eval();need(state(d)==previous,"SLOTS_FALLING_LEAK tick="+std::to_string(tick));
            d.clk=1;d.eval();const State actual=state(d);
            for(unsigned j=0;j<19;++j)if(row[j+12]>=0){
                const std::string typed=j<5?"SLOTS_FLAG_MISMATCH":j<11?"SLOTS_PHYSICAL_DATA_MISMATCH":
                    j<13?"SLOTS_COMMIT_FLAG_MISMATCH":"SLOTS_COMMIT_DATA_MISMATCH";
                need(actual[j]==uint64_t(row[j+12]),typed+" tick="+std::to_string(tick)+" port="+std::to_string(j));
            }
            slots+=actual[0];commits+=actual[11];errors+=actual[3];resets+=!row[0];
        }
        std::string trailing;need(!(input>>trailing),"SLOTS_TRAILING");
        need(context.threads()==1 && d.threads()==1,"SLOTS_THREAD_DRIFT");
        std::cout<<"SLOTS_V2_PASS events="<<count<<" slots="<<slots<<" commits="<<commits
                 <<" errors="<<errors<<" resets="<<resets<<" before_checks="<<2*count<<" edge_checks="<<count<<"\n";
        d.final();return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}
}
