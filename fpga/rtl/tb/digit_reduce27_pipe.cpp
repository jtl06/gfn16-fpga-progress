#include "Vgenefer_digit_reduce27_pipe.h"
#include "verilated.h"
#include <cstdint>
#include <deque>
#include <fstream>
#include <iostream>
#include <stdexcept>
struct Expected {uint64_t due;uint32_t tag,value;bool error;};
int main(int argc,char** argv){try{
    Verilated::commandArgs(argc,argv);if(argc!=2)throw std::runtime_error("vectors required");
    std::ifstream f(argv[1]);if(!f)throw std::runtime_error("input open");
    Vgenefer_digit_reduce27_pipe d;std::deque<Expected> q;
    uint64_t cycle=0,valids=0,errors=0,canceled=0,holds=0;
    uint32_t last_value=0,last_tag=0,rst,valid,digit,tag,error,value;
    while(f>>rst>>valid>>digit>>tag>>error>>value){
        d.clk=0;d.rst_n=rst;d.in_valid=valid;d.digit=digit;d.payload_in=tag;d.eval();
        if(rst&&(d.residue!=last_value||d.payload_out!=last_tag))throw std::runtime_error("combinational output mismatch");
        if(!rst){canceled+=q.size();q.clear();}
        else if(valid)q.push_back({cycle+3,tag,value,bool(error)});
        d.clk=1;d.eval();
        if(!rst){
            if(d.out_valid||d.out_error||d.residue||d.payload_out)throw std::runtime_error("reset mismatch");
            last_value=0;last_tag=0;
        }else{
            bool response=!q.empty()&&q.front().due==cycle;
            bool good=response&&!q.front().error,bad=response&&q.front().error;
            if(d.out_valid!=good||d.out_error!=bad)throw std::runtime_error("valid/error latency mismatch cycle="+std::to_string(cycle));
            if(response){
                auto e=q.front();q.pop_front();
                if(d.payload_out!=e.tag)throw std::runtime_error("payload mismatch");
                last_tag=e.tag;
                if(good){if(d.residue!=e.value)throw std::runtime_error("residue mismatch cycle="+std::to_string(cycle));last_value=e.value;valids++;}
                else errors++;
            }
            if(!good){holds++;if(d.residue!=last_value)throw std::runtime_error("invalid/error residue hold mismatch");}
            if(d.payload_out!=last_tag)throw std::runtime_error("payload hold mismatch");
        }
        cycle++;
    }
    if(!f.eof()||!q.empty()||!valids||!errors)throw std::runtime_error("incomplete vectors");
    std::cout<<"PASS valid="<<valids<<" errors="<<errors<<" canceled="<<canceled<<" holds="<<holds<<" cycles="<<cycle<<"\n";
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
