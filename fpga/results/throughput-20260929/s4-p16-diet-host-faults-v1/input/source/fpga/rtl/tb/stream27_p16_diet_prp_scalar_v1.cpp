#include "stream27_p16_diet_prp_config_v1.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

static void need(bool ok,const std::string& label){if(!ok)throw std::runtime_error(label);}
using Image=std::array<int32_t,N>;
struct Job{uint32_t base,count,mask,twice,batch;std::vector<std::pair<unsigned,int32_t>> changes;Image expected;};
struct Case{unsigned id;Image initial;std::vector<Job> jobs;};
struct Counts{unsigned cases=0,jobs=0,frames=0,reads=0,mutations=0,faults=0,resets=0,recoveries=0;};
static std::vector<Case> corpus(const char* path){
    std::ifstream file(path);unsigned aw=0,count=0;file>>aw>>count;need(file.good()&&aw==AW&&count==5,"S4_HOST_CORPUS_HEADER");
    std::vector<Case> result;
    for(unsigned k=0;k<count;++k){Case c{};unsigned jobs=0;file>>c.id>>jobs;need(c.id==k&&jobs==2,"S4_HOST_CORPUS_CASE");
        for(auto& x:c.initial){int64_t v;file>>v;need(v>=-1&&v<=1000000000,"S4_HOST_CORPUS_SIGNED_INPUT");x=int32_t(v);}
        for(unsigned j=0;j<jobs;++j){Job job{};unsigned mutations=0;file>>job.base>>job.count>>job.mask>>job.twice>>job.batch>>mutations;
            need(job.count>=1&&job.count<=32&&job.base>=MIN_BASE&&job.base<=1000000000,"S4_HOST_CORPUS_JOB");
            for(unsigned m=0;m<mutations;++m){unsigned a;int64_t v;file>>a>>v;need(a<N&&v>=-1&&v<int64_t(job.base),"S4_HOST_CORPUS_CHANGE");job.changes.emplace_back(a,int32_t(v));}
            for(auto& x:job.expected){int64_t v;file>>v;need(v>=-1&&v<int64_t(job.base),"S4_HOST_CORPUS_OUTPUT");x=int32_t(v);}
            c.jobs.push_back(job);
        }result.push_back(c);
    }need(!file.fail(),"S4_HOST_CORPUS_PARSE");std::string extra;need(!(file>>extra),"S4_HOST_CORPUS_TRAILING");return result;
}
static void clear(DUT& d){d.feed_mode=0;d.command_valid=0;d.command_double=0;d.command_index=0;d.command_generation=0;d.load_we=0;d.read_en=0;d.start=0;d.host_addr=0;d.write_data=0;d.double_bit=0;
    d.batch_mode=0;d.warm_count=1;d.double_mask=0;d.t5b_load_we=0;d.t5b_read_en=0;d.t5b_start=0;
    d.t5b_host_addr=0;d.t5b_write_data=0;d.t5b_double_bit=0;}
static void edge(DUT& d){d.clk=0;d.eval();d.clk=1;d.eval();d.clk=0;d.eval();}
template<class W>static int32_t word(const W& x){uint32_t sign=(x[0]&0x80000000u)?0xffffffffu:0;
    need(x[1]==sign&&x[2]==sign,"S4_HOST_FULL96_SIGN_EXTENSION");return int32_t(x[0]);}
static void reset(DUT& d){clear(d);d.rst_n=0;edge(d);
    need(!d.busy&&!d.done&&!d.error&&!d.read_valid&&!d.warm_done&&!d.canonical_ready&&!d.t5b_read_valid&&!d.t5b_done&&!d.t5b_busy,"S4_HOST_RESET_FLUSH");
    d.rst_n=1;edge(d);need(!d.error&&!d.profile_cache_valid,"S4_HOST_RESET_CACHE");}
static void load(DUT& d,const Image& x){for(unsigned a=0;a<N;++a){clear(d);d.load_we=1;d.t5b_load_we=1;
    d.host_addr=a;d.t5b_host_addr=a;d.write_data=uint32_t(x[a]);d.t5b_write_data=uint32_t(x[a]);edge(d);
    need(!d.read_valid&&!d.t5b_read_valid&&!d.busy&&!d.error&&!d.t5b_error&&!d.canonical_ready,"S4_HOST_LOAD_IDLE");}clear(d);edge(d);}
static void mutate(DUT& d,unsigned address,int32_t value,Counts& c){
    clear(d);d.load_we=1;d.read_en=1;d.host_addr=address;d.write_data=uint32_t(value);
    d.t5b_load_we=1;d.t5b_read_en=1;d.t5b_host_addr=address;d.t5b_write_data=uint32_t(value);edge(d);
    need(!d.read_valid&&!d.t5b_read_valid&&!d.error&&!d.t5b_error&&!d.canonical_ready,"S4_HOST_LOAD_WINS_READ");
    clear(d);d.read_en=1;d.host_addr=address;d.t5b_read_en=1;d.t5b_host_addr=address;edge(d);
    need(d.read_valid&&d.t5b_read_valid&&word(d.read_data)==value&&word(d.t5b_read_data)==value,"S4_HOST_PARTIAL_WRITE_E0_READ");
    clear(d);edge(d);need(!d.read_valid&&!d.t5b_read_valid,"S4_HOST_READ_CLEAR");++c.mutations;
}
static unsigned expected_done(const Job& job,bool hit){
    unsigned barrier=(job.expected[0]==-1?10u:9u)*N;
    return (hit?3u:102u)+(job.count-1)*INTERVAL+CARRY_DONE+2+barrier+N+4;
}
static void candidate(DUT& d,const Job& job,bool hit,unsigned kind,unsigned index){
    clear(d);d.base=job.base;d.batch_mode=job.batch;d.warm_count=job.batch?job.count:33;
    d.double_mask=job.mask;d.double_bit=job.twice;
    // Idle start has priority over host mutations; the old image must survive.
    d.start=1;d.load_we=1;d.read_en=1;d.host_addr=0;d.write_data=uint32_t(-2);edge(d);
    need(d.busy&&!d.done&&!d.error&&!d.read_valid&&!d.canonical_ready,"S4_HOST_START_PRIORITY");
    unsigned last=expected_done(job,hit),warm=(hit?3u:102u)+(job.count-1)*INTERVAL+CARRY_DONE+1;
    for(unsigned elapsed=1;elapsed<=last;++elapsed){clear(d);d.base=job.base;
        if(elapsed>=10&&elapsed<=20){d.load_we=1;d.read_en=1;d.start=1;d.host_addr=N-1;d.write_data=uint32_t(-2);
            d.base=job.base+1;d.batch_mode=1;d.warm_count=0;d.double_mask=0xffffffffu;d.double_bit=!job.twice;}
        edge(d);need(!d.error,"S4_HOST_NATIVE_ERROR case="+std::to_string(kind)+" job="+std::to_string(index)+" elapsed="+std::to_string(elapsed));
        need(bool(d.done)==(elapsed==last),"S4_HOST_DONE_CYCLE elapsed="+std::to_string(elapsed)+" expected="+std::to_string(last));
        need(bool(d.warm_done)==(elapsed==warm),"S4_HOST_WARM_DIAGNOSTIC_CYCLE elapsed="+std::to_string(elapsed));
        need(bool(d.busy)==(elapsed!=last)&&!d.read_valid,"S4_HOST_BUSY_READ_QUARANTINE");
    }
    need(d.canonical_ready&&d.completed_squares==job.count&&d.cycles==last,"S4_HOST_CANONICAL_COPIED_COMMIT");
    need(d.canonical_cycles==(job.expected[0]==-1?10u:9u)*N&&d.image_copy_cycles==N+3,"S4_HOST_FINALIZATION_COST");
    need(bool(d.profile_hits)==hit&&bool(d.profile_loads)==!hit&&d.profile_cache_valid&&d.profile_words_loaded==0,"S4_HOST_SETUP_CACHE_DIAGNOSTIC");
    need(d.root_cycles==(hit?0u:99u)&&d.conversion_cycles==N/P&&d.crt_cycles==0&&
        d.cycles==d.root_cycles+d.conversion_cycles+d.ntt_cycles+d.carry_cycles,"S4_HOST_DISJOINT_PHASE_CYCLES");
    clear(d);d.base=job.base;edge(d);need(!d.done&&!d.busy&&!d.error,"S4_HOST_DONE_SINGLE_PULSE");
}
static void production(DUT& d,const Job& job){
    for(unsigned s=0;s<job.count;++s){clear(d);d.base=job.base;d.t5b_start=1;
        d.t5b_double_bit=s?((job.mask>>s)&1u):job.twice;
        d.t5b_load_we=1;d.t5b_read_en=1;d.t5b_host_addr=0;d.t5b_write_data=uint32_t(-2);edge(d);
        need(d.t5b_busy&&!d.t5b_done&&!d.t5b_error&&!d.t5b_read_valid,"S4_HOST_T5B_START");
        unsigned elapsed=0;while(!d.t5b_done&&elapsed<100000){clear(d);edge(d);need(!d.t5b_error&&!d.error,"S4_HOST_T5B_ERROR");++elapsed;}
        need(d.t5b_done&&!d.t5b_busy&&!d.t5b_error,"S4_HOST_T5B_COMPLETION");clear(d);edge(d);
    }
}
static void compare(DUT& d,const Job& job,unsigned kind,unsigned index,bool negative,Counts& counts){
    for(unsigned address=0;address<N;++address){clear(d);d.read_en=1;d.host_addr=address;
        d.t5b_read_en=1;d.t5b_host_addr=address;edge(d);
        need(d.read_valid&&d.t5b_read_valid&&!d.error&&!d.t5b_error,"S4_HOST_PAIRED_E0_READ");
        int32_t actual=word(d.read_data),old=word(d.t5b_read_data),expected=job.expected[address];
        if(negative&&kind==0&&index==0&&address==0)++expected;
        need(actual==expected,"S4_HOST_ORACLE_TYPED aw="+std::to_string(AW)+" case="+std::to_string(kind)+" job="+std::to_string(index)+" address="+std::to_string(address)+" expected="+std::to_string(expected)+" actual="+std::to_string(actual));
        need(actual==old,"S4_HOST_T5B_BIT_IDENTITY");++counts.reads;
    }clear(d);edge(d);need(!d.read_valid&&!d.t5b_read_valid,"S4_HOST_READ_II1_CLEAR");
}
static void quarantine(DUT& d,unsigned type,Counts& counts){
    reset(d);Image zero{};load(d,zero);d.base=MIN_BASE;
    if(type==3){clear(d);d.load_we=1;d.host_addr=0;d.write_data=uint32_t(-2);edge(d);need(!d.error,"S4_HOST_IDLE_SIGNED_STORE_NOT_START_VALIDATION");}
    clear(d);d.base=type==0?MIN_BASE-1:MIN_BASE;d.batch_mode=type==1||type==2;
    d.warm_count=type==1?0:(type==2?33:1);d.start=1;edge(d);
    unsigned elapsed=0;while(!d.error&&elapsed<120){clear(d);edge(d);++elapsed;}
    need(d.error&&d.done&&!d.busy&&!d.read_valid,"S4_HOST_REGISTERED_FAULT_COMPLETION");
    for(unsigned k=0;k<5;++k){clear(d);d.start=1;d.load_we=1;d.read_en=1;d.write_data=0;edge(d);
        need(d.error&&!d.done&&!d.busy&&!d.read_valid,"S4_HOST_STICKY_QUARANTINE");}++counts.faults;
}
static void abort(DUT& d,unsigned delay,Counts& counts){
    reset(d);Image zero{};load(d,zero);clear(d);d.base=MIN_BASE;d.start=1;edge(d);need(d.busy,"S4_HOST_ABORT_START");
    for(unsigned k=0;k<delay;++k){clear(d);edge(d);need(d.busy&&!d.done&&!d.error,"S4_HOST_ABORT_BUSY");}
    reset(d);for(unsigned k=0;k<8;++k){clear(d);edge(d);need(!d.busy&&!d.done&&!d.error&&!d.warm_done&&!d.read_valid,"S4_HOST_RESET_NO_STALE_TOKEN");}++counts.resets;
}
int main(int argc,char** argv){try{
    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);DUT d{&context};
    if(argc==2&&std::string(argv[1])=="--runtime-probe"){
        std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
        return context.threads()==1&&d.threads()==1?0:2;
    }
    need(argc==2||(argc==3&&std::string(argv[2])=="--negative"),"S4_HOST_ARGUMENTS");bool negative=argc==3;
    auto cases=corpus(argv[1]);Counts counts;
    for(const auto& c:cases){reset(d);d.base=c.jobs.front().base;load(d,c.initial);uint32_t cache=0;
        for(unsigned j=0;j<c.jobs.size();++j){const auto& job=c.jobs[j];d.base=job.base;
            for(const auto& mutation:job.changes)mutate(d,mutation.first,mutation.second,counts);
            candidate(d,job,cache==job.base,c.id,j);cache=job.base;production(d,job);compare(d,job,c.id,j,negative,counts);
            ++counts.jobs;counts.frames+=job.count;
        }++counts.cases;
    }
    for(unsigned type=0;type<4;++type){quarantine(d,type,counts);
        reset(d);Image zero{};load(d,zero);Job recovered{};recovered.base=MIN_BASE;recovered.count=1;
        candidate(d,recovered,false,9,type);production(d,recovered);compare(d,recovered,9,type,false,counts);
        ++counts.jobs;++counts.frames;++counts.recoveries;}
    abort(d,10,counts);abort(d,102+CARRY_DONE+8,counts);
    need(context.threads()==1&&d.threads()==1,"S4_HOST_THREADS");
    std::cout<<PASS_LABEL<<" cases="<<counts.cases<<" jobs="<<counts.jobs<<" frames="<<counts.frames<<" paired_reads="<<counts.reads
        <<" mutations="<<counts.mutations<<" faults="<<counts.faults<<" reset_aborts="<<counts.resets<<" copied_words="<<counts.reads<<" recovery_jobs="<<counts.recoveries<<"\n";
    d.final();return 0;
}catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}}
