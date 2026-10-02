#include "Vgenefer_stream27_field_square_aw5_warm_v3.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
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
using State=std::array<uint32_t,27>;
static State state(const Vgenefer_stream27_field_square_aw5_warm_v3& d){
    State result{d.out_slot_valid,d.out_frame_start,d.out_eligible,d.out_error,d.generation_out};
    const auto physical=unpack(d.data_out),commit=unpack(d.commit_data);
    for(unsigned i=0;i<8;++i)result[5+i]=physical[i];
    result[13]=d.commit_valid;result[14]=d.commit_frame_start;result[15]=d.commit_generation;
    for(unsigned i=0;i<8;++i)result[16+i]=commit[i];
    result[24]=d.out_epoch;result[25]=d.commit_epoch;result[26]=d.owner_count;
    return result;
}
int main(int argc,char** argv){
    std::string expected_negative;
    try{
        VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
        Vgenefer_stream27_field_square_aw5_warm_v3 d{&context};
        if(argc==2 && std::string(argv[1])=="--runtime-probe"){
            std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
            return context.threads()==1 && d.threads()==1?0:2;
        }
        need(argc==2 || argc==4,"FIELD_USAGE");
        if(argc==4){
            need(std::string(argv[2])=="--expect-negative","FIELD_NEGATIVE_USAGE");
            expected_negative=argv[3];
            need(expected_negative=="FIELD_PHYSICAL_DATA_MISMATCH" ||
                 expected_negative=="FIELD_SLOT_MISMATCH" || expected_negative=="FIELD_COMMIT_FLAG_MISMATCH","FIELD_NEGATIVE_KIND");
        }
        std::ifstream input(argv[1]);need(bool(input),"FIELD_OPEN");
        std::string magic;uint64_t count;input>>magic>>count;
        need(magic=="FIELDWARM3" && count<1000000,"FIELD_HEADER");
        uint64_t slots=0,commits=0,errors=0,resets=0,frames=0,corrections=0,peak_owners=0;
        d.clk=1;d.rst_n=0;d.in_slot_valid=0;d.frame_start=0;d.correction_valid=0;d.eval();
        for(uint64_t tick=0;tick<count;++tick){
            std::array<int64_t,65> row{};
            for(auto& x:row)need(bool(input>>x),"FIELD_TRUNCATED");
            for(unsigned i=0;i<4;++i)need(row[i]>=0 && row[i]<=1,"FIELD_BOOLEAN_RANGE");
            need(row[4]>=0 && row[4]<256 && row[5]>=0 && row[5]<256,"FIELD_GENERATION_RANGE");
            need(row[6]>=0 && uint64_t(row[6])<=UINT32_MAX,"FIELD_BASE_PORT_RANGE");
            for(unsigned i=0;i<8;++i){
                need(row[7+i]>=0 && uint64_t(row[7+i])<=UINT32_MAX,"FIELD_DIGIT_PORT_RANGE");
                need(row[15+i]>=INT32_MIN && row[15+i]<=INT32_MAX &&
                     row[23+i]>=INT32_MIN && row[23+i]<=INT32_MAX,"FIELD_CORRECTION_PORT_RANGE");
            }
            need(row[56]>=0 && row[56]<65536 && row[57]>=0 && row[57]<=1 &&
                 row[58]>=0 && row[58]<65536 && row[59]>=0 && row[59]<256,"WARM_TAG_INPUT_RANGE");
            State previous=state(d);
            d.rst_n=row[0];d.in_slot_valid=row[1];d.frame_start=row[2];d.context_enabled=row[3];
            d.generation_in=row[4];d.live_generation=row[5];d.base_in=row[6];
            d.epoch_in=row[56];d.correction_valid=row[57];d.correction_epoch=row[58];d.correction_generation=row[59];
            for(unsigned i=0;i<8;++i){
                d.data_in[i]=uint32_t(row[7+i]);d.c0_in[i]=uint32_t(int32_t(row[15+i]));
                d.c1_in[i]=uint32_t(int32_t(row[23+i]));
            }
            if(!row[0]){
                for(unsigned j=0;j<4;++j)previous[j]=0;
                for(unsigned j=5;j<13;++j)previous[j]=0; // final arithmetic helper payloads reset
                previous[13]=0;previous[14]=0;previous[24]=0;previous[26]=0;
            }else previous[2]=previous[0] && row[3] && previous[4]==uint64_t(row[5]);
            d.eval();
            if(!row[0])previous[4]=d.generation_out; // generation is irrelevant on reset; valid must clear
            need(state(d)==previous,"FIELD_ASYNC_OR_COMBINATIONAL_LEAK tick="+std::to_string(tick));
            if(row[31]>=0)need(d.fault_pending==uint64_t(row[31]),"FIELD_PENDING_FAULT_MISMATCH tick="+std::to_string(tick));
            need(d.frame_accept==uint64_t(row[63]) && d.correction_accept==uint64_t(row[64]),
                 "WARM_ADMISSION_MISMATCH tick="+std::to_string(tick));
            const auto frame_accept=d.frame_accept,correction_accept=d.correction_accept;
            d.clk=0;d.eval();need(state(d)==previous,"FIELD_FALLING_LEAK tick="+std::to_string(tick));
            need(d.frame_accept==frame_accept && d.correction_accept==correction_accept,
                 "WARM_FALLING_ADMISSION_LEAK tick="+std::to_string(tick));
            d.clk=1;d.eval();const auto actual=state(d);
            for(unsigned j=0;j<24;++j)if(row[32+j]>=0){
                const std::string kind=j==0?"FIELD_SLOT_MISMATCH":j<5?"FIELD_PHYSICAL_FLAG_MISMATCH":
                    j<13?"FIELD_PHYSICAL_DATA_MISMATCH":j<16?"FIELD_COMMIT_FLAG_MISMATCH":"FIELD_COMMIT_DATA_MISMATCH";
                need(actual[j]==uint64_t(row[32+j]),kind+" tick="+std::to_string(tick)+" port="+std::to_string(j));
            }
            for(unsigned j=24;j<27;++j)if(row[j+36]>=0)
                need(actual[j]==uint64_t(row[j+36]),"WARM_EPOCH_OWNER_MISMATCH tick="+std::to_string(tick)+" port="+std::to_string(j));
            slots+=actual[0];commits+=actual[13];errors+=actual[3];resets+=!row[0];
            frames+=frame_accept;corrections+=correction_accept;
            if(actual[26]>peak_owners)peak_owners=actual[26];
        }
        std::string trailing;need(!(input>>trailing),"FIELD_TRAILING");
        need(expected_negative.empty(),"FIELD_NEGATIVE_NOT_DETECTED");
        need(context.threads()==1 && d.threads()==1,"FIELD_THREAD_DRIFT");
        std::cout<<"FIELD_WARM_V3_PASS events="<<count<<" slots="<<slots<<" commits="<<commits
                 <<" errors="<<errors<<" resets="<<resets<<" frame_accepts="<<frames<<" correction_accepts="<<corrections<<" peak_owners="<<peak_owners<<" before_checks="<<2*count<<" edge_checks="<<count<<"\n";
        d.final();return 0;
    }catch(const std::exception& error){
        const std::string detail=error.what();std::cerr<<detail<<"\n";
        if(!expected_negative.empty() && detail.rfind(expected_negative+" tick=",0)==0){
            std::cout<<"FIELD_WARM_V3_NEGATIVE_PASS kind="<<expected_negative<<"\n";return 0;
        }
        return 1;
    }
}
