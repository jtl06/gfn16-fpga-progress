#include "Vgenefer_root_profile27_rom.h"
#include "verilated.h"
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>
static Vgenefer_root_profile27_rom d;
static uint64_t checks=0,words=0,aborts=0,runs=0;
static const std::vector<uint32_t>* consumer_expected=nullptr;
static unsigned consumed=0;
static void need(bool ok,const char* why){if(!ok)throw std::runtime_error(why);++checks;}
static void edge(){
    // A downstream synchronous loader consumes OLD outputs on this edge.
    if(d.rst_n&&d.word_valid){
        need(consumer_expected&&consumed<consumer_expected->size(),"unexpected downstream word");
        need(d.word_addr==consumed&&d.word_data==(*consumer_expected)[consumed],"downstream mismatch");++consumed;
    }
    d.clk=1;d.eval();d.clk=0;d.eval();
}
static void reset(){d.start=0;d.rst_n=0;consumer_expected=nullptr;consumed=0;d.eval();edge();need(!d.busy&&!d.done&&!d.word_valid,"reset leak");d.rst_n=1;d.eval();}
static void run(const std::vector<uint32_t>& expected,int abort_at=-1){
    d.start=1;edge();d.start=0;d.eval();need(d.busy&&!d.done&&!d.word_valid,"start boundary");
    if(consumer_expected)need(consumed==consumer_expected->size(),"previous stream not consumed");
    consumer_expected=&expected;consumed=0;
    for(unsigned index=0;index<expected.size();++index){
        if(int(index)==abort_at){reset();++aborts;return;}
        d.start=index%13==5;edge();d.start=0;d.eval();
        need(d.word_valid&&d.word_addr==index,"ordered address mismatch");
        need(d.word_data==expected[index],"profile value mismatch");
        bool last=index+1==expected.size();
        need(bool(d.done)==last&&bool(d.busy)==!last,"done/busy edge mismatch");++words;
    }
    need(consumed+1==expected.size(),"last-word availability/consumption boundary");++runs;
}
int main(int argc,char**argv){
    Verilated::commandArgs(argc,argv);
    try{
        if(argc!=2)throw std::runtime_error("expected profile vector file");
        std::ifstream input(argv[1]);std::vector<uint32_t> expected;uint32_t word;
        while(input>>word)expected.push_back(word);
        need(!expected.empty(),"empty profile");reset();
        run(expected);run(expected); // no reset between coherent full uploads
        std::vector<unsigned> stops={0,1,2,3,4,7,15,63,127,unsigned(expected.size()-2),unsigned(expected.size()-1)};
        for(unsigned when:stops)if(when<expected.size()){run(expected,when);run(expected);}
        edge();need(!d.done&&!d.word_valid&&!d.busy,"idle leak");
        need(consumed==expected.size(),"final word not consumed");
        std::cout<<"PASS profile_words="<<expected.size()<<" runs="<<runs<<" aborts="<<aborts<<" checked_words="<<words<<" checks="<<checks<<"\n";
    }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}
    return 0;
}
