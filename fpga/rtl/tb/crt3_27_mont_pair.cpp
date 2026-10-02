#include "Vcrt3_27_mont_pair.h"
#include "verilated.h"
#include <cstdint>
#include <deque>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>
#ifndef CRT27_CANDIDATE_DELAY
#error explicit candidate latency required
#endif
#ifndef CRT27_FROZEN_DELAY
#error explicit frozen latency required
#endif
using I=__int128_t;
static const I HALF=I(243972611374018097ULL)*1000000+905664;
static constexpr uint64_t CD=CRT27_CANDIDATE_DELAY,BD=CRT27_FROZEN_DELAY;
static uint64_t decimal(const std::string& s,uint64_t limit) {
    if(s.empty())throw std::runtime_error("CRT27_MONT_VECTOR_FORMAT");
    uint64_t value=0;
    for(char c:s){if(c<'0'||c>'9'||uint64_t(c-'0')>limit||value>(limit-uint64_t(c-'0'))/10)throw std::runtime_error("CRT27_MONT_VECTOR_FORMAT");value=value*10+uint64_t(c-'0');}
    return value;
}
static I integer(const std::string& s) {
    if(s.empty())throw std::runtime_error("CRT27_MONT_VECTOR_FORMAT");
    const bool negative=s[0]=='-';size_t begin=negative?1:0;I value=0;
    if(begin==s.size())throw std::runtime_error("CRT27_MONT_VECTOR_FORMAT");
    for(size_t i=begin;i<s.size();i++){char c=s[i];if(c<'0'||c>'9'||value>((I(1)<<95)-1-(c-'0'))/10)throw std::runtime_error("CRT27_MONT_VECTOR_FORMAT");value=value*10+c-'0';}
    return negative?-value:value;
}
template<class T>static I signed96(const T& a) {
    const __uint128_t bits=__uint128_t(a[0])|(__uint128_t(a[1])<<32)|(__uint128_t(a[2])<<64);
    return a[2]&0x80000000u?I(bits)-(I(1)<<96):I(bits);
}
struct Pending {uint64_t due,id;I expected;};
struct Record {I expected,baseline=0,candidate=0;bool seen_baseline=false,seen_candidate=false;};
int main(int argc,char** argv) {try {
    VerilatedContext* const context=Verilated::threadContextp();context->threads(1);context->commandArgs(argc,argv);
    Vcrt3_27_mont_pair d{context};
    if(argc==2 && std::string(argv[1])=="--runtime-probe") {
        d.eval();
        std::cout<<"{\"context_threads\":"<<context->threads()<<",\"model_threads\":"<<d.threads()
            <<",\"candidate_delay\":"<<d.probe_candidate_delay<<",\"frozen_delay\":"<<d.probe_frozen_delay
            <<",\"coefficient_bits\":"<<d.probe_coefficient_bits<<",\"p1\":"<<d.probe_p1
            <<",\"p2\":"<<d.probe_p2<<",\"p3\":"<<d.probe_p3<<"}\n";
        return context->threads()==1 && d.threads()==1 ? 0 : 2;
    }
    if(argc==5 && std::string(argv[1])=="--reject") {
        const std::string role=argv[2];if(role!="baseline"&&role!="candidate")throw std::runtime_error("CRT27_MONT_CLI");
        const unsigned port=decimal(argv[3],2);const uint32_t value=decimal(argv[4],0xffffffffu);
        d.clk=1;d.rst_n=0;d.in_valid=0;d.test_mode=role=="baseline"?1:2;d.r1=d.r2=d.r3=0;d.eval();
        d.rst_n=1;d.eval();d.clk=0;d.in_valid=1;
        if(port==0)d.r1=value;if(port==1)d.r2=value;if(port==2)d.r3=value;
        d.eval();d.clk=1;d.eval();
        throw std::runtime_error("CRT27_MONT_INPUT_ASSERTION_MISSING");
    }
    if(argc!=3 || std::string(argv[1])!="--normal")throw std::runtime_error("CRT27_MONT_CLI");
    std::ifstream stream(argv[2]);if(!stream)throw std::runtime_error("CRT27_MONT_VECTOR_OPEN");
    std::string line;if(!std::getline(stream,line)||line!="CRT27_MONT_V1 candidate_delay=15 frozen_delay=60 coefficient_bits=96")throw std::runtime_error("CRT27_MONT_VECTOR_HEADER");
    d.clk=1;d.rst_n=0;d.in_valid=0;d.test_mode=0;d.r1=d.r2=d.r3=0;d.eval();
    std::deque<Pending> baseline,candidate;std::unordered_map<uint64_t,Record> records;
    uint64_t cycles=0,accepted=0,baseline_checked=0,candidate_checked=0,matched=0;
    uint64_t baseline_canceled=0,candidate_canceled=0,hold_checks=0,async_checks=0,port_checks=0,resets=0,bubbles=0,discarded_partial=0;
    I held_baseline=0,held_candidate=0;bool previous_baseline=false,previous_candidate=false;
    auto reset_outputs=[&](){
        port_checks+=2;async_checks+=2;
        if(!d.baseline_ready||!d.candidate_ready||d.baseline_valid||d.candidate_valid||
           signed96(d.baseline_coefficient)!=0||signed96(d.candidate_coefficient)!=0)
            throw std::runtime_error("CRT27_MONT_ASYNC_RESET_MISMATCH");
    };
    auto observe=[&](bool is_candidate){
        port_checks++;auto& queue=is_candidate?candidate:baseline;I& held=is_candidate?held_candidate:held_baseline;
        bool& previous=is_candidate?previous_candidate:previous_baseline;
        const bool ready=is_candidate?d.candidate_ready:d.baseline_ready;
        const bool valid=is_candidate?d.candidate_valid:d.baseline_valid;
        const I actual=is_candidate?signed96(d.candidate_coefficient):signed96(d.baseline_coefficient);
        const bool expected=!queue.empty()&&queue.front().due==cycles;
        if(!ready||valid!=expected||(!queue.empty()&&queue.front().due<cycles))throw std::runtime_error("CRT27_MONT_LATENCY_READY_MISMATCH");
        if(expected){
            const auto item=queue.front();queue.pop_front();
            if(actual!=item.expected||actual < -HALF||actual>HALF)throw std::runtime_error("CRT27_MONT_ARITHMETIC_SIGN_MISMATCH");
            auto it=records.find(item.id);if(it==records.end())throw std::runtime_error("CRT27_MONT_TRANSACTION_INDEX_MISMATCH");
            auto& record=it->second;
            if(is_candidate){if(record.seen_candidate)throw std::runtime_error("CRT27_MONT_TRANSACTION_INDEX_MISMATCH");record.candidate=actual;record.seen_candidate=true;candidate_checked++;}
            else{if(record.seen_baseline)throw std::runtime_error("CRT27_MONT_TRANSACTION_INDEX_MISMATCH");record.baseline=actual;record.seen_baseline=true;baseline_checked++;}
            if(record.seen_baseline&&record.seen_candidate){
                if(record.baseline!=record.candidate||record.candidate!=record.expected)throw std::runtime_error("CRT27_MONT_TRANSACTION_INDEX_MISMATCH");
                matched++;records.erase(it);
            }
            held=actual;
        }else{if(actual!=held)throw std::runtime_error("CRT27_MONT_INVALID_HOLD_MISMATCH");hold_checks++;}
        previous=valid;
    };
    while(std::getline(stream,line)) {
        if(line=="RESET") {
            d.in_valid=0;d.rst_n=0;d.eval();reset_outputs();
            baseline_canceled+=baseline.size();candidate_canceled+=candidate.size();discarded_partial+=records.size();
            baseline.clear();candidate.clear();records.clear();held_baseline=held_candidate=0;previous_baseline=previous_candidate=false;
            d.rst_n=1;d.eval();reset_outputs();resets++;continue;
        }
        std::istringstream row(line);std::vector<std::string> fields;std::string field;while(row>>field)fields.push_back(field);
        if(fields.size()!=6||fields[0]!="STEP")throw std::runtime_error("CRT27_MONT_VECTOR_FORMAT");
        const bool valid=decimal(fields[1],1);const uint32_t r1=decimal(fields[2],0xffffffffu),r2=decimal(fields[3],0xffffffffu),r3=decimal(fields[4],0xffffffffu);
        const I expected=integer(fields[5]);
        if(valid&&(r1>=104857601u||r2>=69206017u||r3>=67239937u||expected < -HALF||expected>HALF))throw std::runtime_error("CRT27_MONT_VECTOR_CANONICAL");
        d.clk=0;d.in_valid=valid;d.r1=r1;d.r2=r2;d.r3=r3;d.eval();port_checks+=2;
        if(!d.baseline_ready||!d.candidate_ready||bool(d.baseline_valid)!=previous_baseline||bool(d.candidate_valid)!=previous_candidate||
           signed96(d.baseline_coefficient)!=held_baseline||signed96(d.candidate_coefficient)!=held_candidate)
            throw std::runtime_error("CRT27_MONT_COMBINATIONAL_PORT_MISMATCH");
        if(valid){
            const uint64_t id=accepted++;records.emplace(id,Record{expected});baseline.push_back({cycles+BD,id,expected});candidate.push_back({cycles+CD,id,expected});
        }else bubbles++;
        d.clk=1;d.eval();observe(false);observe(true);cycles++;
    }
    if(!stream.eof()||!baseline.empty()||!candidate.empty()||!records.empty()||matched<1000000||resets<61)
        throw std::runtime_error("CRT27_MONT_INCOMPLETE_COVERAGE");
    if(context->threads()!=1||d.threads()!=1)throw std::runtime_error("CRT27_MONT_THREAD_MISMATCH");
    std::cout<<"PASS cycles="<<cycles<<" accepted="<<accepted<<" baseline_checked="<<baseline_checked<<" candidate_checked="<<candidate_checked
        <<" matched="<<matched<<" baseline_canceled="<<baseline_canceled<<" candidate_canceled="<<candidate_canceled
        <<" hold_checks="<<hold_checks<<" async_checks="<<async_checks<<" port_checks="<<port_checks<<" resets="<<resets
        <<" bubbles="<<bubbles<<" discarded_partial="<<discarded_partial<<"\n";
    return 0;
}catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}}
