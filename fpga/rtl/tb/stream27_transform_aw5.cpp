#include "Vgenefer_stream27_transform_aw5_probe.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#ifndef TRANSFORM_INVERSE
#error TRANSFORM_INVERSE must match the source-bound INVERSE parameter
#endif
static void need(bool ok,const std::string& s){if(!ok)throw std::runtime_error(s);}
using Data=std::array<uint32_t,8>;
template<class Wide>static Data unpack(const Wide& words){
    Data result{};
    for(unsigned lane=0;lane<8;++lane){
        const unsigned bit=27*lane,word=bit/32,shift=bit%32;
        uint64_t value=words[word];
        if(word<6)value|=uint64_t(words[word+1])<<32;
        result[lane]=(value>>shift)&((1u<<27)-1);
    }
    return result;
}
template<class Wide>static void pack(Wide& words,const Data& data){
    for(unsigned word=0;word<7;++word)words[word]=0;
    for(unsigned lane=0;lane<8;++lane){
        const unsigned bit=27*lane,word=bit/32,shift=bit%32;
        words[word]|=data[lane]<<shift;
        if(shift>5)words[word+1]|=data[lane]>>(32-shift);
    }
}
using State=std::array<uint32_t,24>;
static State state(const Vgenefer_stream27_transform_aw5_probe& d){
    State result{d.out_slot_valid,d.out_frame_start,d.out_eligible,d.out_error,d.generation_out};
    const auto physical=unpack(d.data_out),commit=unpack(d.commit_data);
    for(unsigned i=0;i<8;++i)result[5+i]=physical[i];
    result[13]=d.commit_valid;result[14]=d.commit_frame_start;result[15]=d.commit_generation;
    for(unsigned i=0;i<8;++i)result[16+i]=commit[i];
    return result;
}
int main(int argc,char** argv){
    std::string expected_negative;
    try{
        VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
        Vgenefer_stream27_transform_aw5_probe d{&context};
        if(argc==2 && std::string(argv[1])=="--runtime-probe"){
            std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
            return context.threads()==1 && d.threads()==1?0:2;
        }
        need(argc==2 || argc==4,"TRANSFORM_USAGE");
        if(argc==4){
            need(std::string(argv[2])=="--expect-negative","TRANSFORM_NEGATIVE_USAGE");
            expected_negative=argv[3];
            need(expected_negative=="TRANSFORM_PHYSICAL_DATA_MISMATCH" ||
                 expected_negative=="TRANSFORM_SLOT_MISMATCH","TRANSFORM_NEGATIVE_KIND");
        }
        std::ifstream input(argv[1]);need(bool(input),"TRANSFORM_OPEN");
        std::string magic;uint64_t inverse,count;input>>magic>>inverse>>count;
        need(magic=="TRAW5" && inverse==TRANSFORM_INVERSE && count<1000000,"TRANSFORM_HEADER");
        uint64_t slots=0,commits=0,errors=0,resets=0;
        d.clk=1;d.rst_n=0;d.in_slot_valid=0;d.frame_start=0;d.eval();
        for(uint64_t tick=0;tick<count;++tick){
            std::array<int64_t,39> row{};
            for(auto& x:row)need(bool(input>>x),"TRANSFORM_TRUNCATED");
            for(unsigned i=0;i<4;++i)need(row[i]>=0 && row[i]<=1,"TRANSFORM_BOOLEAN_RANGE");
            need(row[4]>=0 && row[4]<256 && row[5]>=0 && row[5]<256,"TRANSFORM_GENERATION_RANGE");
            Data data{};
            for(unsigned i=0;i<8;++i){
                need(row[6+i]>=0 && row[6+i]<104857601,"TRANSFORM_CANONICAL_INPUT");
                data[i]=row[6+i];
            }
            State previous=state(d);
            d.rst_n=row[0];d.in_slot_valid=row[1];d.frame_start=row[2];d.context_enabled=row[3];
            d.generation_in=row[4];d.live_generation=row[5];pack(d.data_in,data);
            if(!row[0]){
                for(unsigned j=0;j<4;++j)previous[j]=0;
                for(unsigned j=5;j<13;++j)previous[j]=0; // frozen BF payloads reset
                previous[13]=0;previous[14]=0;
            }else previous[2]=previous[0] && row[3] && previous[4]==uint64_t(row[5]);
            d.eval();need(state(d)==previous,"TRANSFORM_ASYNC_OR_COMBINATIONAL_LEAK tick="+std::to_string(tick));
            if(row[14]>=0)need(d.fault_pending==uint64_t(row[14]),"TRANSFORM_PENDING_FAULT_MISMATCH tick="+std::to_string(tick));
            d.clk=0;d.eval();need(state(d)==previous,"TRANSFORM_FALLING_LEAK tick="+std::to_string(tick));
            d.clk=1;d.eval();const auto actual=state(d);
            for(unsigned j=0;j<24;++j)if(row[15+j]>=0){
                const std::string kind=j==0?"TRANSFORM_SLOT_MISMATCH":j<5?"TRANSFORM_PHYSICAL_FLAG_MISMATCH":
                    j<13?"TRANSFORM_PHYSICAL_DATA_MISMATCH":j<16?"TRANSFORM_COMMIT_FLAG_MISMATCH":"TRANSFORM_COMMIT_DATA_MISMATCH";
                need(actual[j]==uint64_t(row[15+j]),kind+" tick="+std::to_string(tick)+" port="+std::to_string(j));
            }
            slots+=actual[0];commits+=actual[13];errors+=actual[3];resets+=!row[0];
        }
        std::string trailing;need(!(input>>trailing),"TRANSFORM_TRAILING");
        need(expected_negative.empty(),"TRANSFORM_NEGATIVE_NOT_DETECTED");
        need(context.threads()==1 && d.threads()==1,"TRANSFORM_THREAD_DRIFT");
        std::cout<<"TRANSFORM_AW5_PASS inverse="<<inverse<<" events="<<count<<" slots="<<slots<<" commits="<<commits
                 <<" errors="<<errors<<" resets="<<resets<<" before_checks="<<2*count<<" edge_checks="<<count<<"\n";
        d.final();return 0;
    }catch(const std::exception& error){
        const std::string detail=error.what();std::cerr<<detail<<"\n";
        if(!expected_negative.empty() && detail.rfind(expected_negative+" tick=",0)==0){
            std::cout<<"TRANSFORM_AW5_NEGATIVE_PASS kind="<<expected_negative<<"\n";return 0;
        }
        return 1;
    }
}
