#include "Vgenefer_stream27_mdc_commutator_sync.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#ifndef COMM_DEPTH
#error COMM_DEPTH must be source-bound
#endif
static void need(bool ok,const std::string& s){if(!ok)throw std::runtime_error(s);}
using State=std::array<uint32_t,8>;
static State state(const Vgenefer_stream27_mdc_commutator_sync& d){return {
    d.out_valid,d.out_error,d.upper_out,d.lower_out,d.upper_payload_out,d.lower_payload_out,d.context_out,d.generation_out};}
int main(int argc,char** argv){
    try{
        VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
        Vgenefer_stream27_mdc_commutator_sync d{&context};
        if(argc==2 && std::string(argv[1])=="--runtime-probe"){
            std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
            return context.threads()==1 && d.threads()==1?0:2;
        }
        need(argc==2,"COMM_USAGE");std::ifstream input(argv[1]);need(bool(input),"COMM_OPEN");
        std::string magic;uint64_t depth,T,count;input>>magic>>depth>>T>>count;
        need(magic=="COMM1" && depth==COMM_DEPTH && T==(depth<4?8:2*depth) && count<1000000,"COMM_HEADER");
        uint64_t valid_count=0,error_count=0,reset_count=0;
        d.clk=1;d.rst_n=0;d.in_valid=0;d.frame_start=0;d.eval();
        for(uint64_t tick=0;tick<count;++tick){
            std::array<int64_t,19> row{};
            for(auto& x:row)need(bool(input>>x),"COMM_TRUNCATED");
            need(row[0]>=0 && row[0]<=1 && row[1]>=0 && row[1]<=1 && row[2]>=0 && row[2]<=1 &&
                 row[3]>=0 && row[3]<(1<<27) && row[4]>=0 && row[4]<(1<<27) &&
                 row[5]>=0 && row[5]<65536 && row[6]>=0 && row[6]<65536 &&
                 row[7]>=0 && row[7]<=1 && row[8]>=0 && row[8]<256 && row[9]>=0 && row[9]<4 &&
                 row[10]>=0 && row[10]<65536,"COMM_PORT_RANGE");
            State previous=state(d);
            d.rst_n=row[0];d.in_valid=row[1];d.frame_start=row[2];
            d.upper_in=row[3];d.lower_in=row[4];d.upper_payload=row[5];d.lower_payload=row[6];
            d.context_in=row[7];d.generation_in=row[8];d.context_enabled=row[9];d.live_generations=row[10];
            if(!row[0]){previous[0]=0;previous[1]=0;}
            d.eval();need(state(d)==previous,"COMM_ASYNC_OR_COMBINATIONAL_LEAK");
            d.clk=0;d.eval();need(state(d)==previous,"COMM_FALLING_LEAK");
            d.clk=1;d.eval();const State actual=state(d);
            need(actual[0]==row[11] && actual[1]==row[12],"COMM_FLAG_MISMATCH tick="+std::to_string(tick));
            for(unsigned j=0;j<6;++j)if(row[j+13]>=0)
                need(actual[j+2]==uint64_t(row[j+13]),"COMM_DATA_OR_TAG_MISMATCH tick="+std::to_string(tick));
            valid_count+=actual[0];error_count+=actual[1];reset_count+=!row[0];
        }
        std::string trailing;need(!(input>>trailing),"COMM_TRAILING");
        need(context.threads()==1 && d.threads()==1,"COMM_THREAD_DRIFT");
        std::cout<<"COMM_SYNC_PASS depth="<<depth<<" frame_ticks="<<T<<" events="<<count
                 <<" valid="<<valid_count<<" errors="<<error_count<<" resets="<<reset_count
                 <<" before_checks="<<2*count<<" edge_checks="<<count<<"\n";
        d.final();return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}
}
